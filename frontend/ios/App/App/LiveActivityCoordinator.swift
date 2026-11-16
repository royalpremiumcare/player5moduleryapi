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
    /// FIFO for register/unregister: each waits for the previous one to finish.
    private var identityTail: Task<Void, Never>?
    private var reconcileTail: Task<ReconcileOutcome, Error>?
    private var pendingReport: Task<Void, Never>?
    /// Unregister calls not yet finished. While > 0 no report, reconcile or local start runs, so
    /// nothing can recreate cards during the logout DELETE (the secret is deleted only after it).
    private var unregistersInFlight = 0
    private var unregistering: Bool { unregistersInFlight > 0 }
    /// activity id -> last token hex the server accepted; drives the post-reconcile re-post.
    private var postedTokens: [String: String] = [:]

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
                rememberPushToStartToken(pushTokenHex(token))
            }
            Task {
                for await token in PlannActivity.pushToStartTokenUpdates {
                    let hex = pushTokenHex(token)
                    guard hex != self.latestPushToStartToken else { continue }
                    self.rememberPushToStartToken(hex)
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

    private func rememberPushToStartToken(_ hex: String) {
        latestPushToStartToken = hex
        api.lastPushToStartToken = hex
    }

    /// The push-to-start token to send now (17.2+): re-read from ActivityKit, else the last one
    /// seen or persisted, so a cold-launch register never nulls the server's stored token.
    private func pushToStartTokenNow() -> String? {
        var fresh: String?
        if #available(iOS 17.2, *), let token = PlannActivity.pushToStartToken {
            fresh = pushTokenHex(token)
        }
        let token = pushToStartTokenToSend(fresh: fresh, latest: latestPushToStartToken,
                                           persisted: api.lastPushToStartToken)
        if let token = token, token != latestPushToStartToken { rememberPushToStartToken(token) }
        return token
    }

    /// Latest FCM token from Firebase (AppDelegate's MessagingDelegate). Only stored: the next
    /// register uses it (JS re-registers on resume while the server has no FCM token).
    func updateFcmToken(_ token: String?) {
        guard let token = token, !token.isEmpty else { return }
        lastFcmToken = token
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
                postedTokens[activity.id] = hex
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
        pendingReport = nil
        guard !unregistering else { return }
        pendingReport = Task {
            try? await Task.sleep(nanoseconds: Self.reportDebounceNanos)
            guard !Task.isCancelled else { return }
            self.pendingReport = nil
            guard self.api.hasSecret, !self.unregistering else { return }
            do {
                try await self.reconcile()
            } catch {
                self.log.error("reconcile failed: \(pluginErrorCode(error), privacy: .public)")
            }
        }
    }

    /// Foreground reconcile (AppDelegate.applicationDidBecomeActive), only once registered.
    func reconcileIfRegistered() {
        guard api.hasSecret, !unregistering else { return }
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
        guard !unregistering else { return ReconcileOutcome(ended: 0, startedLocally: 0) }
        let background = BackgroundTaskGuard("PlannLiveActivityReconcile")
        defer { background.end() }
        let current = snapshots()
        let report = completeReport(deviceId: api.deviceId(), activitiesEnabled: activitiesEnabled,
                                    pushToStartToken: pushToStartTokenNow(), current: current)
        let response = try await api.reconcile(report)

        let endIds = endInstructions(response: response, current: current)
        var ended = 0
        for activity in PlannActivity.activities where endIds.contains(activity.id) {
            await activity.end(nil, dismissalPolicy: .immediate)
            ended += 1
        }
        let startedLocally = startLocally(response.start_locally)
        repostTokens()
        return ReconcileOutcome(ended: ended, startedLocally: startedLocally)
    }

    /// Re-posts current per-activity tokens the server has not accepted yet (a post that failed,
    /// or one that arrived before the secret existed).
    private func repostTokens() {
        guard !unregistering else { return }
        let activities = PlannActivity.activities
        let candidates = activities.compactMap { activity -> TokenCandidate? in
            guard let slot = SlotId(activity.attributes.slotId) else { return nil }
            return TokenCandidate(slotIndex: slot.index, activityId: activity.id,
                                  token: activity.pushToken.map(pushTokenHex),
                                  state: Self.stateString(activity.activityState))
        }
        for candidate in tokensToRepost(candidates, posted: postedTokens) {
            guard let token = candidate.token,
                  let activity = activities.first(where: { $0.id == candidate.activityId }) else { continue }
            Task { await self.postToken(token, for: activity) }
        }
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
        guard !starts.isEmpty, !unregistering, UIApplication.shared.applicationState == .active else { return 0 }
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

    /// Runs `operation` after every earlier register/unregister has finished (FIFO).
    private func enqueueIdentity<T: Sendable>(_ operation: @escaping @MainActor () async throws -> T) async throws -> T {
        let previous = identityTail
        let task = Task { () async throws -> T in
            await previous?.value
            return try await operation()
        }
        identityTail = Task { _ = await task.result }
        return try await task.value
    }

    /// Serialized with unregister: one identity operation in flight, later calls wait for it
    /// before running their own. After a registration that stored a new secret, runs one
    /// complete reconcile.
    func register(apiBaseUrl: String, jwt: String, fcmToken: String?) async throws
        -> (deviceId: String, newSecret: Bool, hasFcmToken: Bool) {
        let outcome = try await enqueueIdentity {
            try await self.performRegister(apiBaseUrl: apiBaseUrl, jwt: jwt, fcmToken: fcmToken)
        }
        return (api.deviceId(), outcome.newSecret, outcome.hasFcmToken)
    }

    private struct RegisterOutcome: Sendable {
        let newSecret: Bool
        let hasFcmToken: Bool
    }

    private func performRegister(apiBaseUrl: String, jwt: String, fcmToken: String?) async throws -> RegisterOutcome {
        let background = BackgroundTaskGuard("PlannLiveActivityRegister")
        defer { background.end() }
        let given = (fcmToken?.isEmpty == false) ? fcmToken : nil
        let fcm = given ?? Messaging.messaging().fcmToken ?? lastFcmToken
        if let fcm = fcm { lastFcmToken = fcm }
        let info = Bundle.main.infoDictionary
        // registerEnsuringSecret: a secret lost in transit (server has one, Keychain none) is
        // recovered once by deleting the device with the JWT and registering again.
        let newSecret = try await api.registerEnsuringSecret(
            apiBaseUrl: apiBaseUrl, jwt: jwt,
            osVersion: UIDevice.current.systemVersion,
            appBuild: appBuildString(shortVersion: info?["CFBundleShortVersionString"] as? String,
                                     build: info?["CFBundleVersion"] as? String),
            fcmToken: fcm, pushToStartToken: pushToStartTokenNow(),
            activitiesEnabled: activitiesEnabled)
        if newSecret {
            pendingReport?.cancel()
            pendingReport = nil
            postedTokens.removeAll() // a new secret: re-post every live token after the reconcile
            do {
                try await reconcile()
            } catch {
                log.error("post-register reconcile failed: \(pluginErrorCode(error), privacy: .public)")
            }
        }
        return RegisterOutcome(newSecret: newSecret, hasFcmToken: fcm != nil)
    }

    /// Logout, serialized with register: blocks reports/reconciles/local starts at once, waits for
    /// the in-flight reconcile, ends every local activity, then the core unregister (DELETE with
    /// the JWT; always deletes the stored secret). Without a JWT the secret is deleted locally.
    @discardableResult
    func unregister(jwt: String?) async -> Int {
        unregistersInFlight += 1
        pendingReport?.cancel()
        pendingReport = nil
        let background = BackgroundTaskGuard("PlannLiveActivityUnregister")
        defer { background.end() }
        let ended = (try? await enqueueIdentity { await self.performUnregister(jwt: jwt) }) ?? 0
        return ended
    }

    /// Runs inside the identity FIFO; lifts its block before the next queued register starts.
    private func performUnregister(jwt: String?) async -> Int {
        defer { unregistersInFlight -= 1 }
        _ = await reconcileTail?.result
        let ended = await endAll()
        if let jwt = jwt, !jwt.isEmpty {
            await api.unregister(jwt: jwt)
        } else {
            api.forgetSecret()
        }
        pendingReport?.cancel() // state updates from the ended cards may have scheduled one
        pendingReport = nil
        postedTokens.removeAll()
        return ended
    }
}

/// Keeps the app running briefly when a token post or report starts during a background launch.
@MainActor
private final class BackgroundTaskGuard {
    private var id: UIBackgroundTaskIdentifier = .invalid

    init(_ name: String) {
        // The expiration handler ends the task by its own id: no call back into this
        // main-actor object from a closure whose isolation differs across SDKs.
        var taskId: UIBackgroundTaskIdentifier = .invalid
        taskId = UIApplication.shared.beginBackgroundTask(withName: name) {
            UIApplication.shared.endBackgroundTask(taskId)
        }
        id = taskId
    }

    func end() {
        guard id != .invalid else { return }
        UIApplication.shared.endBackgroundTask(id)
        id = .invalid
    }
}
