import ActivityKit
import FirebaseMessaging
import Foundation
import UIKit
import os

/// App-side ActivityKit adapter for the slot Live Activities.
///
/// Started from `AppDelegate.didFinishLaunching`, so its observers also run when iOS launches the
/// app in the background (no WebView) to deliver a push token. Tokens and reports go through the
/// LiveActivityCore API over URLSession with the Keychain device secret. Every decision comes
/// from LiveActivityCore; this class only adapts ActivityKit and UIKit to it.
@available(iOS 16.2, *)
@MainActor
final class LiveActivityCoordinator {
    static let shared = LiveActivityCoordinator()

    struct ReconcileOutcome: Sendable {
        let ended: Int
        let startedLocally: Int
    }

    private typealias PlannActivity = Activity<PlannAppointmentAttributes>

    private static let reportDebounceNanos: UInt64 = 2_000_000_000
    private static let tokenRetryDelaysSec: [UInt64] = [0, 2, 5]

    private let api = LiveActivityAPI(transport: URLSessionTransport(), secrets: KeychainSecretStore(),
                                      defaults: .standard)
    private let log = os.Logger(subsystem: "co.plannapp.app", category: "LiveActivity")

    private var started = false
    private var observed = Set<String>()
    private(set) var latestPushToStartToken: String?
    private var lastFcmToken: String?
    private var registerTail: Task<Bool, Error>?
    private var reconcileTail: Task<ReconcileOutcome, Error>?
    private var pendingReport: Task<Void, Never>?

    private init() {}

    var activitiesEnabled: Bool { ActivityAuthorizationInfo().areActivitiesEnabled }

    // MARK: observers

    func start() {
        guard !started else { return }
        started = true

        let info = ActivityAuthorizationInfo()
        Task {
            for await _ in info.activityEnablementUpdates {
                self.scheduleReport()
            }
        }

        if #available(iOS 17.2, *) {
            if let token = PlannActivity.pushToStartToken {
                latestPushToStartToken = pushTokenHex(token)
            }
            Task {
                for await token in PlannActivity.pushToStartTokenUpdates {
                    let hex = pushTokenHex(token)
                    guard hex != self.latestPushToStartToken else { continue }
                    self.latestPushToStartToken = hex
                    self.scheduleReport()
                }
            }
        }

        for activity in PlannActivity.activities {
            observe(activity)
        }
        Task {
            for await activity in PlannActivity.activityUpdates {
                self.observe(activity)
                self.scheduleReport()
            }
        }

        scheduleReport() // launch report, including background launches
    }

    private func observe(_ activity: PlannActivity) {
        guard observed.insert(activity.id).inserted else { return }
        Task {
            for await token in activity.pushTokenUpdates {
                await self.postToken(pushTokenHex(token), for: activity)
            }
        }
        Task {
            for await _ in activity.activityStateUpdates {
                self.scheduleReport()
            }
        }
    }

    private func postToken(_ hex: String, for activity: PlannActivity) async {
        guard let slot = SlotId(activity.attributes.slotId) else {
            log.error("push token for an activity without a valid slotId")
            return
        }
        let background = BackgroundTaskGuard("PlannLiveActivityToken")
        defer { background.end() }
        let delays = Self.tokenRetryDelaysSec
        for (attempt, delay) in delays.enumerated() {
            if delay > 0 { try? await Task.sleep(nanoseconds: delay * 1_000_000_000) }
            do {
                try await api.postToken(slotIndex: slot.index, activityId: activity.id, updateToken: hex)
                return
            } catch {
                if !isRetryableTokenError(error) || attempt == delays.count - 1 {
                    log.error("token post failed: \(pluginErrorCode(error), privacy: .public)")
                    return
                }
            }
        }
    }

    // MARK: reports

    /// Debounced (2 s) complete report after an ActivityKit change. No-op without a secret.
    func scheduleReport() {
        pendingReport?.cancel()
        pendingReport = Task {
            try? await Task.sleep(nanoseconds: Self.reportDebounceNanos)
            guard !Task.isCancelled else { return }
            self.pendingReport = nil
            guard self.api.hasSecret else { return }
            do {
                try await self.reconcile()
            } catch {
                self.log.error("reconcile failed: \(pluginErrorCode(error), privacy: .public)")
            }
        }
    }

    /// Foreground reconcile (AppDelegate.applicationDidBecomeActive), only once registered.
    func reconcileIfRegistered() {
        guard api.hasSecret else { return }
        pendingReport?.cancel()
        pendingReport = nil
        Task {
            do {
                try await self.reconcile()
            } catch {
                self.log.error("reconcile failed: \(pluginErrorCode(error), privacy: .public)")
            }
        }
    }

    /// One complete reconcile; calls are serialized.
    @discardableResult
    func reconcile() async throws -> ReconcileOutcome {
        let previous = reconcileTail
        let task = Task { () async throws -> ReconcileOutcome in
            _ = await previous?.result
            return try await self.performReconcile()
        }
        reconcileTail = task
        return try await task.value
    }

    private func performReconcile() async throws -> ReconcileOutcome {
        let background = BackgroundTaskGuard("PlannLiveActivityReconcile")
        defer { background.end() }
        let current = snapshots()
        let report = completeReport(deviceId: api.deviceId(), activitiesEnabled: activitiesEnabled,
                                    pushToStartToken: latestPushToStartToken, current: current)
        let response = try await api.reconcile(report)

        let endIds = endInstructions(response: response, current: current)
        var ended = 0
        for activity in PlannActivity.activities where endIds.contains(activity.id) {
            await activity.end(nil, dismissalPolicy: .immediate)
            ended += 1
        }
        let startedLocally = startLocally(response.start_locally)
        return ReconcileOutcome(ended: ended, startedLocally: startedLocally)
    }

    private func snapshots() -> [ActivitySnapshot] {
        PlannActivity.activities.compactMap { activity in
            ActivitySnapshot(slotId: activity.attributes.slotId, activityId: activity.id,
                             state: Self.stateString(activity.activityState))
        }
    }

    private static func stateString(_ state: ActivityState) -> String {
        switch state {
        case .active: return "active"
        case .stale: return "stale"
        case .ended: return "ended"
        case .dismissed: return "dismissed"
        default: return reportState(described: String(describing: state)) // .pending on newer SDKs
        }
    }

    /// Server-planned starts for devices without push-to-start: only in the foreground and only
    /// below iOS 17.2 (a background local start throws `.visibility`).
    private func startLocally(_ starts: [LocalStart]) -> Int {
        guard !starts.isEmpty, UIApplication.shared.applicationState == .active else { return 0 }
        guard #unavailable(iOS 17.2) else { return 0 }
        let deviceId = api.deviceId()
        var count = 0
        for start in starts {
            guard let attrs = localStartAttributes(start, deviceId: deviceId) else { continue }
            let content = ActivityContent(state: start.content,
                                          staleDate: start.stale_epoch.map { Date(timeIntervalSince1970: $0) },
                                          relevanceScore: start.relevance)
            do {
                let activity = try PlannActivity.request(
                    attributes: PlannAppointmentAttributes(slotId: attrs.slotId, orgId: attrs.orgId),
                    content: content, pushType: .token)
                observe(activity)
                count += 1
            } catch {
                log.error("local start failed: \(String(describing: type(of: error)), privacy: .public)")
            }
        }
        return count
    }

    /// Ends every PLANN Live Activity on this device immediately.
    @discardableResult
    func endAll() async -> Int {
        pendingReport?.cancel()
        pendingReport = nil
        var count = 0
        for activity in PlannActivity.activities {
            await activity.end(nil, dismissalPolicy: .immediate)
            count += 1
        }
        return count
    }

    // MARK: registration (JWT only passes through; never stored)

    /// Serialized: one registration in flight, later calls wait for it before running their own.
    /// After a registration that stored a new secret, runs one complete reconcile.
    func register(apiBaseUrl: String, jwt: String, fcmToken: String?) async throws -> (deviceId: String, newSecret: Bool) {
        let previous = registerTail
        let task = Task { () async throws -> Bool in
            _ = await previous?.result
            return try await self.performRegister(apiBaseUrl: apiBaseUrl, jwt: jwt, fcmToken: fcmToken)
        }
        registerTail = task
        let newSecret = try await task.value
        return (api.deviceId(), newSecret)
    }

    private func performRegister(apiBaseUrl: String, jwt: String, fcmToken: String?) async throws -> Bool {
        let background = BackgroundTaskGuard("PlannLiveActivityRegister")
        defer { background.end() }
        let given = (fcmToken?.isEmpty == false) ? fcmToken : nil
        let fcm = given ?? Messaging.messaging().fcmToken ?? lastFcmToken
        if let fcm = fcm { lastFcmToken = fcm }
        let info = Bundle.main.infoDictionary
        let newSecret = try await api.register(
            apiBaseUrl: apiBaseUrl, jwt: jwt,
            osVersion: UIDevice.current.systemVersion,
            appBuild: appBuildString(shortVersion: info?["CFBundleShortVersionString"] as? String,
                                     build: info?["CFBundleVersion"] as? String),
            fcmToken: fcm, pushToStartToken: latestPushToStartToken,
            activitiesEnabled: activitiesEnabled)
        if newSecret {
            pendingReport?.cancel()
            pendingReport = nil
            do {
                try await reconcile()
            } catch {
                log.error("post-register reconcile failed: \(pluginErrorCode(error), privacy: .public)")
            }
        }
        return newSecret
    }

    /// Logout: waits for in-flight register/reconcile, ends every local activity, then the core
    /// unregister (DELETE with the JWT; always deletes the stored secret).
    @discardableResult
    func unregister(jwt: String) async -> Int {
        let background = BackgroundTaskGuard("PlannLiveActivityUnregister")
        defer { background.end() }
        _ = await registerTail?.result
        _ = await reconcileTail?.result
        let ended = await endAll()
        await api.unregister(jwt: jwt)
        return ended
    }
}

/// Keeps the app running briefly when a token post or report starts during a background launch.
@MainActor
private final class BackgroundTaskGuard {
    private var id: UIBackgroundTaskIdentifier = .invalid

    init(_ name: String) {
        id = UIApplication.shared.beginBackgroundTask(withName: name) { [weak self] in
            self?.end()
        }
    }

    func end() {
        guard id != .invalid else { return }
        UIApplication.shared.endBackgroundTask(id)
        id = .invalid
    }
}
