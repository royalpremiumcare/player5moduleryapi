import Foundation
import Security

/// Live Activity install id and device secret, stored as generic-password items in the app's
/// own Keychain (no access group, no App Group). Readable after the first unlock, so background
/// launches that deliver push tokens can use the secret. This-device-only: a backup restored to
/// another device must not clone the device id and secret (it registers as a new device).
/// Items carry no explicit access group, so they land in the default group: the FIRST entry of
/// `keychain-access-groups` in App.entitlements. That entry must stay the app's own group
/// (`$(AppIdentifierPrefix)co.plannapp.app`), listed before the widget-shared group, or new
/// secrets would become readable by the widget extension.
final class KeychainSecretStore: SecretStore {
    static let service = "co.plannapp.app.la"

    private func query(_ key: String) -> [String: Any] {
        [kSecClass as String: kSecClassGenericPassword,
         kSecAttrService as String: Self.service,
         kSecAttrAccount as String: key]
    }

    func read(_ key: String) -> String? {
        var q = query(key)
        q[kSecReturnData as String] = true
        q[kSecMatchLimit as String] = kSecMatchLimitOne
        var out: CFTypeRef?
        guard SecItemCopyMatching(q as CFDictionary, &out) == errSecSuccess, let data = out as? Data else {
            return nil
        }
        return String(data: data, encoding: .utf8)
    }

    func write(_ key: String, _ value: String) {
        let attrs: [String: Any] = [kSecValueData as String: Data(value.utf8),
                                    kSecAttrAccessible as String: kSecAttrAccessibleAfterFirstUnlockThisDeviceOnly]
        let status = SecItemUpdate(query(key) as CFDictionary, attrs as CFDictionary)
        if status == errSecItemNotFound {
            let add = query(key).merging(attrs) { _, new in new }
            _ = SecItemAdd(add as CFDictionary, nil)
        }
    }

    func delete(_ key: String) {
        _ = SecItemDelete(query(key) as CFDictionary)
    }
}
