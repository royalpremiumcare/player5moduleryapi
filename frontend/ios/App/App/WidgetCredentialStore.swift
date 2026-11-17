import Foundation
import Security

/// The Home Screen widget's credential (widget key + API origin), stored as two generic-password
/// items in the Keychain access group shared by the app and the PlannWidgets extension
/// (`$(AppIdentifierPrefix)co.plannapp.app.shared`, spec §5.1). Readable after the first unlock so
/// the widget can refresh while the device is locked; this-device-only so a restored backup never
/// carries a key to another device. The Live Activity secret stays in KeychainSecretStore (app-only).
///
/// The concrete group is built from the `AppIdentifierPrefix` Info.plist value, which both targets
/// set to `$(AppIdentifierPrefix)`: the same build setting the entitlement expands, so the app and
/// the extension always resolve the same group. Every query names the group explicitly, so the
/// result does not depend on which group the Keychain treats as the default. If the prefix is
/// missing or unexpanded, reads return nil and writes throw (the widget shows the signed-out state).
/// Self-contained on purpose: if shared-group signing fails, only this file changes.
enum WidgetCredentialStore {
    enum StoreError: Error {
        case noAccessGroup
        case keychain(OSStatus)
    }

    private static var accessGroup: String? {
        WidgetBridge.accessGroup(
            appIdentifierPrefix: Bundle.main.object(forInfoDictionaryKey: "AppIdentifierPrefix") as? String)
    }

    private static func query(_ account: String, group: String) -> [String: Any] {
        [kSecClass as String: kSecClassGenericPassword,
         kSecAttrService as String: WidgetBridge.keychainService,
         kSecAttrAccount as String: account,
         kSecAttrAccessGroup as String: group]
    }

    /// Both items, or nil when either is missing (signed out).
    static func read() -> (key: String, baseURL: String)? {
        guard let group = accessGroup,
              let key = readItem(WidgetBridge.keyAccount, group: group), !key.isEmpty,
              let baseURL = readItem(WidgetBridge.baseURLAccount, group: group), !baseURL.isEmpty else {
            return nil
        }
        return (key, baseURL)
    }

    /// Writes both items and returns the key it replaced (nil when none, or the same key), so the
    /// app can revoke that key on the server. On any failure both are removed, so a half-written
    /// pair never pairs a new key with an old origin (or the reverse).
    @discardableResult
    static func write(key: String, baseURL: String) throws -> String? {
        guard let group = accessGroup else { throw StoreError.noAccessGroup }
        let previous = readItem(WidgetBridge.keyAccount, group: group)
        do {
            try writeItem(WidgetBridge.keyAccount, key, group: group)
            try writeItem(WidgetBridge.baseURLAccount, baseURL, group: group)
        } catch {
            clear()
            throw error
        }
        guard let previous, !previous.isEmpty, previous != key else { return nil }
        return previous
    }

    /// Removes both items and returns the key that was stored (nil when none), so logout can
    /// revoke exactly this device's key on the server.
    @discardableResult
    static func clear() -> String? {
        guard let group = accessGroup else { return nil }
        let key = readItem(WidgetBridge.keyAccount, group: group)
        _ = SecItemDelete(query(WidgetBridge.keyAccount, group: group) as CFDictionary)
        _ = SecItemDelete(query(WidgetBridge.baseURLAccount, group: group) as CFDictionary)
        return key?.isEmpty == false ? key : nil
    }

    private static func readItem(_ account: String, group: String) -> String? {
        var q = query(account, group: group)
        q[kSecReturnData as String] = true
        q[kSecMatchLimit as String] = kSecMatchLimitOne
        var out: CFTypeRef?
        guard SecItemCopyMatching(q as CFDictionary, &out) == errSecSuccess, let data = out as? Data else {
            return nil
        }
        return String(data: data, encoding: .utf8)
    }

    private static func writeItem(_ account: String, _ value: String, group: String) throws {
        let attrs: [String: Any] = [kSecValueData as String: Data(value.utf8),
                                    kSecAttrAccessible as String: kSecAttrAccessibleAfterFirstUnlockThisDeviceOnly]
        var status = SecItemUpdate(query(account, group: group) as CFDictionary, attrs as CFDictionary)
        if status == errSecItemNotFound {
            let add = query(account, group: group).merging(attrs) { _, new in new }
            status = SecItemAdd(add as CFDictionary, nil)
        }
        guard status == errSecSuccess else { throw StoreError.keychain(status) }
    }
}
