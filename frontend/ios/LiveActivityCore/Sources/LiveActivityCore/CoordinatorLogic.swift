import Foundation

// Pure helpers for the app-side LiveActivityCoordinator: the coordinator only adapts
// ActivityKit/UIKit to these.

/// Report string for an ActivityKit `activityState` (its case name). Known states pass
/// through; an unknown future state is reported as present ("active").
public func reportState(described: String) -> String {
    switch described {
    case "active", "stale", "pending", "ended", "dismissed": return described
    default: return "active"
    }
}

extension ActivitySnapshot {
    /// Snapshot of an activity whose `attributes.slotId` is "<device_id>:<n>"; nil when it does not parse.
    public init?(slotId: String, activityId: String, state: String) {
        guard let slot = SlotId(slotId) else { return nil }
        self.init(slotIndex: slot.index, activityId: activityId, state: state)
    }
}

/// The `complete` report: every PLANN activity currently known to ActivityKit.
public func completeReport(deviceId: String, activitiesEnabled: Bool, pushToStartToken: String?,
                           current: [ActivitySnapshot]) -> ReconcileReport {
    ReconcileReport(device_id: deviceId, activities_enabled: activitiesEnabled, complete: true,
                    push_to_start_token: pushToStartToken,
                    slots: current.map { ActivitySnapshotDTO(slot_index: $0.slotIndex, activity_id: $0.activityId,
                                                             state: $0.state) })
}

public struct LocalStartAttributes: Equatable {
    public let slotId: String
    public let orgId: String

    public init(slotId: String, orgId: String) {
        self.slotId = slotId
        self.orgId = orgId
    }
}

/// Attributes for a `start_locally` entry: the server's own when given (its slotId must name
/// `slot_index`), else "<deviceId>:<slot_index>". Nil when the entry is not a valid slot.
public func localStartAttributes(_ start: LocalStart, deviceId: String) -> LocalStartAttributes? {
    guard (1...5).contains(start.slot_index) else { return nil }
    let orgId = start.attributes?["orgId"] ?? ""
    if let raw = start.attributes?["slotId"] {
        guard let slot = SlotId(raw), slot.index == start.slot_index else { return nil }
        return LocalStartAttributes(slotId: raw, orgId: orgId)
    }
    return LocalStartAttributes(slotId: "\(deviceId):\(start.slot_index)", orgId: orgId)
}

/// APNs token bytes as lowercase hex.
public func pushTokenHex(_ token: Data) -> String {
    token.map { String(format: "%02x", $0) }.joined()
}

/// Push-to-start token for a register/report: the one ActivityKit returns now, else the last one
/// its update stream delivered, else the persisted one. Empty strings count as absent, so a
/// register never nulls the server's stored token while one is known.
public func pushToStartTokenToSend(fresh: String?, latest: String?, persisted: String?) -> String? {
    [fresh, latest, persisted].lazy.compactMap { $0 }.first { !$0.isEmpty }
}

/// `CFBundleShortVersionString (CFBundleVersion)`.
public func appBuildString(shortVersion: String?, build: String?) -> String {
    "\(shortVersion ?? "?") (\(build ?? "?"))"
}

/// Whether a failed token post is worth retrying: network errors, 408/429 and 5xx. A rejected
/// secret (401), a bad request, a missing secret/base URL or a cancellation are final.
public func isRetryableTokenError(_ error: Error) -> Bool {
    if error is CancellationError { return false }
    switch error as? APIError {
    case .http(let status)?: return status == 408 || status == 429 || status >= 500
    case .noSecret?, .noBaseUrl?: return false
    case nil: return true
    }
}

/// Error code handed to JS by the plugin: names the failure, never carries request details.
public func pluginErrorCode(_ error: Error) -> String {
    switch error as? APIError {
    case .http(let status)?: return "HTTP_\(status)"
    case .noSecret?: return "NO_SECRET"
    case .noBaseUrl?: return "NO_BASE_URL"
    case nil: return "NETWORK"
    }
}

/// An activity's current per-activity push token, as seen by the coordinator.
public struct TokenCandidate: Equatable {
    public var slotIndex: Int
    public var activityId: String
    public var token: String?
    /// report state string (see `reportState(described:)`)
    public var state: String

    public init(slotIndex: Int, activityId: String, token: String?, state: String) {
        self.slotIndex = slotIndex
        self.activityId = activityId
        self.token = token
        self.state = state
    }
}

/// Tokens to post again after a reconcile: alive activities (active/stale/pending) with a token
/// that was never posted successfully or has changed since. Order is preserved.
public func tokensToRepost(_ candidates: [TokenCandidate], posted: [String: String]) -> [TokenCandidate] {
    let alive: Set<String> = ["active", "stale", "pending"]
    return candidates.filter { c in
        guard let token = c.token, !token.isEmpty, alive.contains(c.state) else { return false }
        return posted[c.activityId] != token
    }
}
