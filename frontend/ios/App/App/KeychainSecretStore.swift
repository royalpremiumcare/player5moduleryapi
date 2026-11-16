import Foundation
import Security

/// Live Activity install id and device secret, stored as generic-password items in the app's
/// own Keychain (no access group, no App Group). Readable after the first unlock, so background
/// launches that deliver push tokens can use the secret.
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
                                    kSecAttrAccessible as String: kSecAttrAccessibleAfterFirstUnlock]
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
