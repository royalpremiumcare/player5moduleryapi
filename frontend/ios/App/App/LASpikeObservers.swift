// PHASE 0 SPIKE — throwaway. Started from AppDelegate.didFinishLaunching so observers also
// exist on BACKGROUND launches (S2: does iOS wake the app to deliver tokens after push-to-start?).
import ActivityKit
import Foundation
import UIKit

@available(iOS 16.2, *)
@MainActor
final class LASpikeObservers {
    static let shared = LASpikeObservers()

    private var started = false
    private var observed = Set<String>()
    private(set) var lastPushToStartToken: String?
    private(set) var activityTokens: [String: String] = [:]   // activity.id -> hex token

    private func log(_ message: String) {
        LASpikeLog.write("appState=\(UIApplication.shared.applicationState.rawValue) \(message)")
    }

    func start() {
        guard !started else { return }
        started = true
        let info = ActivityAuthorizationInfo()
        log("launch enabled=\(info.areActivitiesEnabled) frequent=\(info.frequentPushesEnabled) existing=\(Activity<PlannAppointmentAttributes>.activities.count)")

        Task { @MainActor in
            for await enabled in info.activityEnablementUpdates {
                self.log("enablementUpdate=\(enabled)")
            }
        }
        Task { @MainActor in
            for await frequent in info.frequentPushEnablementUpdates {
                self.log("frequentPushUpdate=\(frequent)")
            }
        }

        if #available(iOS 17.2, *) {
            if let token = Activity<PlannAppointmentAttributes>.pushToStartToken {
                lastPushToStartToken = token.laSpikeHex
                log("pushToStartToken(sync)=\(token.laSpikeHex)")
            } else {
                log("pushToStartToken(sync)=nil")
            }
            Task { @MainActor in
                for await token in Activity<PlannAppointmentAttributes>.pushToStartTokenUpdates {
                    self.lastPushToStartToken = token.laSpikeHex
                    self.log("pushToStartTokenUpdate=\(token.laSpikeHex)")
                }
            }
        }

        for activity in Activity<PlannAppointmentAttributes>.activities {
            observe(activity, origin: "existing")
        }
        Task { @MainActor in
            for await activity in Activity<PlannAppointmentAttributes>.activityUpdates {
                self.observe(activity, origin: "activityUpdates")
            }
        }
    }

    func observe(_ activity: Activity<PlannAppointmentAttributes>, origin: String) {
        guard !observed.contains(activity.id) else { return }
        observed.insert(activity.id)
        let apt = activity.attributes.appointmentId
        log("observe origin=\(origin) id=\(activity.id) apt=\(apt) state=\(activity.activityState) v=\(activity.content.state.version)")

        Task { @MainActor in
            for await token in activity.pushTokenUpdates {
                self.activityTokens[activity.id] = token.laSpikeHex
                self.log("pushTokenUpdate id=\(activity.id) apt=\(apt) token=\(token.laSpikeHex)")
            }
        }
        Task { @MainActor in
            for await state in activity.activityStateUpdates {
                self.log("stateUpdate id=\(activity.id) apt=\(apt) state=\(state)")
            }
        }
        Task { @MainActor in
            for await content in activity.contentUpdates {
                self.log("contentUpdate id=\(activity.id) apt=\(apt) phase=\(content.state.phase) v=\(content.state.version)")
            }
        }
    }
}
