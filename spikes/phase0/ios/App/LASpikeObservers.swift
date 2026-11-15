// PHASE 0 SPIKE — throwaway. Target: App.
// Started from AppDelegate.didFinishLaunching so observers exist on BACKGROUND launches
// (the S2 question: does iOS wake the app to deliver tokens after push-to-start?).
import ActivityKit
import Foundation

@available(iOS 16.2, *)
@MainActor
final class LASpikeObservers {
    static let shared = LASpikeObservers()
    private var started = false
    private var observed = Set<String>()

    func start() {
        guard !started else { return }
        started = true
        let info = ActivityAuthorizationInfo()
        LASpikeLog.write("launch enabled=\(info.areActivitiesEnabled) frequent=\(info.frequentPushesEnabled) existing=\(Activity<PlannAppointmentAttributes>.activities.count)")

        Task { for await enabled in info.activityEnablementUpdates { LASpikeLog.write("enablementUpdate=\(enabled)") } }
        Task { for await f in info.frequentPushEnablementUpdates { LASpikeLog.write("frequentPushUpdate=\(f)") } }

        if #available(iOS 17.2, *) {
            if let t = Activity<PlannAppointmentAttributes>.pushToStartToken {
                LASpikeLog.write("pushToStartToken(sync)=\(t.laSpikeHex)")
            } else {
                LASpikeLog.write("pushToStartToken(sync)=nil")
            }
            Task {
                for await t in Activity<PlannAppointmentAttributes>.pushToStartTokenUpdates {
                    LASpikeLog.write("pushToStartTokenUpdate=\(t.laSpikeHex)")
                }
            }
        }

        for a in Activity<PlannAppointmentAttributes>.activities { observe(a, origin: "existing") }
        Task {
            for await a in Activity<PlannAppointmentAttributes>.activityUpdates {
                self.observe(a, origin: "activityUpdates")
            }
        }
    }

    private func observe(_ a: Activity<PlannAppointmentAttributes>, origin: String) {
        guard !observed.contains(a.id) else { return }
        observed.insert(a.id)
        LASpikeLog.write("observe origin=\(origin) id=\(a.id) apt=\(a.attributes.appointmentId) state=\(a.activityState) v=\(a.content.state.version)")
        Task {
            for await t in a.pushTokenUpdates {
                LASpikeLog.write("pushTokenUpdate id=\(a.id) apt=\(a.attributes.appointmentId) token=\(t.laSpikeHex)")
            }
        }
        Task {
            for await s in a.activityStateUpdates {
                LASpikeLog.write("stateUpdate id=\(a.id) apt=\(a.attributes.appointmentId) state=\(s)")
            }
        }
        Task {
            for await c in a.contentUpdates {
                LASpikeLog.write("contentUpdate id=\(a.id) apt=\(a.attributes.appointmentId) phase=\(c.state.phase) v=\(c.state.version)")
            }
        }
    }
}
