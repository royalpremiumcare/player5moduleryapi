import Foundation

/// Pure decisions behind the app-side widget bridge (`setWidgetCredential`, `clearWidgetCredential`,
/// `reloadWidgets`) and the shared Keychain item names both the app and the widget extension use.
public enum WidgetBridge {
    /// Keychain items shared with the widget extension (spec §5.1).
    public static let keychainService = "co.plannapp.app.widget"
    public static let keyAccount = "widget_key"
    public static let baseURLAccount = "api_base_url"
    /// The entitlement is `$(AppIdentifierPrefix)co.plannapp.app.shared`.
    public static let sharedGroupSuffix = "co.plannapp.app.shared"

    /// `reloadAllTimelines()` runs at most once per this many seconds.
    public static let reloadInterval: TimeInterval = 5

    /// Only `https://` origins with a host are stored for the widget.
    public static func isAcceptableBaseURL(_ string: String) -> Bool {
        guard !string.isEmpty, string.rangeOfCharacter(from: .whitespacesAndNewlines) == nil,
              string.lowercased().hasPrefix("https://"),
              let url = URL(string: string), url.scheme?.lowercased() == "https",
              let host = url.host, !host.isEmpty else { return false }
        return true
    }

    /// Leading edge of the reload debounce. A clock set backwards never blocks a reload.
    public static func shouldReload(last: Date?, now: Date) -> Bool {
        guard let last else { return true }
        let elapsed = now.timeIntervalSince(last)
        return elapsed < 0 || elapsed >= reloadInterval
    }

    /// Seconds until a suppressed reload may run (0 when it may run now).
    public static func reloadDelay(last: Date?, now: Date) -> TimeInterval {
        guard !shouldReload(last: last, now: now), let last else { return 0 }
        return reloadInterval - now.timeIntervalSince(last)
    }

    /// The concrete shared access group from the `AppIdentifierPrefix` Info.plist value (the same
    /// build setting the entitlement expands). nil when the value is missing or was not expanded.
    public static func accessGroup(appIdentifierPrefix: String?) -> String? {
        guard var prefix = appIdentifierPrefix else { return nil }
        while prefix.hasSuffix(".") { prefix.removeLast() }
        guard !prefix.isEmpty,
              prefix.unicodeScalars.allSatisfy({ $0.isASCII && CharacterSet.alphanumerics.contains($0) }) else {
            return nil
        }
        return prefix + "." + sharedGroupSuffix
    }
}
