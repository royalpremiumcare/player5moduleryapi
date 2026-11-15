// PHASE 0 SPIKE — throwaway. Target: App. Register in MyViewController.capacitorDidLoad:
//     bridge?.registerPluginInstance(LASpikePlugin())
// Drive from Safari Web Inspector console, e.g.:
//     await Capacitor.Plugins.LASpike.state()
//     await Capacitor.Plugins.LASpike.startLocal({ count: 10, startsInSeconds: 600, durationMinutes: 45 })
//     await Capacitor.Plugins.LASpike.endAll()
//     (await Capacitor.Plugins.LASpike.readLog()).log
import ActivityKit
import Capacitor
import Foundation

@objc(LASpikePlugin)
public class LASpikePlugin: CAPPlugin, CAPBridgedPlugin {
    public let identifier = "LASpikePlugin"
    public let jsName = "LASpike"
    public let pluginMethods: [CAPPluginMethod] = [
        CAPPluginMethod(name: "state", returnType: CAPPluginReturnPromise),
        CAPPluginMethod(name: "startLocal", returnType: CAPPluginReturnPromise),
        CAPPluginMethod(name: "endAll", returnType: CAPPluginReturnPromise),
        CAPPluginMethod(name: "readLog", returnType: CAPPluginReturnPromise),
        CAPPluginMethod(name: "clearLog", returnType: CAPPluginReturnPromise),
    ]

    @objc func state(_ call: CAPPluginCall) {
        guard #available(iOS 16.2, *) else { call.resolve(["supported": false]); return }
        let info = ActivityAuthorizationInfo()
        var r: [String: Any] = [
            "supported": true,
            "enabled": info.areActivitiesEnabled,
            "frequentPushesEnabled": info.frequentPushesEnabled,
            "activities": Activity<PlannAppointmentAttributes>.activities.map {
                ["id": $0.id, "appointmentId": $0.attributes.appointmentId,
                 "state": String(describing: $0.activityState), "version": $0.content.state.version,
                 "pushToken": $0.pushToken?.laSpikeHex ?? NSNull()] as [String: Any]
            },
        ]
        if #available(iOS 17.2, *) {
            r["pushToStartToken"] = Activity<PlannAppointmentAttributes>.pushToStartToken?.laSpikeHex ?? NSNull()
        }
        call.resolve(r)
    }

    /// S3: request `count` activities back-to-back and record exactly which attempt fails and how.
    @objc func startLocal(_ call: CAPPluginCall) {
        guard #available(iOS 16.2, *) else { call.reject("iOS 16.2+ required"); return }
        let count = call.getInt("count") ?? 1
        let startsIn = call.getInt("startsInSeconds") ?? 600
        let durationMin = call.getInt("durationMinutes") ?? 45
        Task { @MainActor in
            let fmt = DateFormatter()
            fmt.dateFormat = "HH:mm"
            fmt.timeZone = TimeZone(identifier: "Europe/Istanbul")
            var results: [[String: Any]] = []
            for i in 0..<count {
                let start = Date().addingTimeInterval(TimeInterval(startsIn + i * 60))
                let end = start.addingTimeInterval(TimeInterval(durationMin * 60))
                let state = PlannAppointmentAttributes.ContentState(
                    phase: "upcoming", startEpoch: start.timeIntervalSince1970, endEpoch: end.timeIntervalSince1970,
                    startLabel: fmt.string(from: start), endLabel: fmt.string(from: end),
                    customerDisplay: "Test \(i + 1)", serviceName: "Spike", staffName: nil, version: 1)
                let attrs = PlannAppointmentAttributes(
                    appointmentId: "spike-\(Int(Date().timeIntervalSince1970))-\(i)", orgId: "spike")
                do {
                    let a = try Activity.request(
                        attributes: attrs, content: .init(state: state, staleDate: start), pushType: .token)
                    results.append(["i": i, "ok": true, "activityId": a.id])
                    LASpikeLog.write("startLocal i=\(i) ok id=\(a.id)")
                } catch let e as ActivityAuthorizationError {
                    results.append(["i": i, "ok": false, "error": String(describing: e)])
                    LASpikeLog.write("startLocal i=\(i) ActivityAuthorizationError=\(e)")
                } catch {
                    results.append(["i": i, "ok": false, "error": String(describing: error)])
                    LASpikeLog.write("startLocal i=\(i) error=\(error)")
                }
            }
            call.resolve(["results": results, "activeCount": Activity<PlannAppointmentAttributes>.activities.count])
        }
    }

    @objc func endAll(_ call: CAPPluginCall) {
        guard #available(iOS 16.2, *) else { call.resolve(["ended": 0]); return }
        Task {
            let all = Activity<PlannAppointmentAttributes>.activities
            for a in all { await a.end(nil, dismissalPolicy: .immediate) }
            LASpikeLog.write("endAll ended=\(all.count)")
            call.resolve(["ended": all.count])
        }
    }

    @objc func readLog(_ call: CAPPluginCall) { call.resolve(["log": LASpikeLog.read()]) }
    @objc func clearLog(_ call: CAPPluginCall) { LASpikeLog.clear(); call.resolve() }
}
