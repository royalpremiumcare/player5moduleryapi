import Foundation
import Capacitor
import UIKit

/// JS bridge for the slot Live Activities (`PlannLiveActivity`). Compiles for the iOS 15 app
/// target: every method gates itself on iOS 16.2 and resolves `{supported:false}` below it.
/// The JWT arrives only for register/unregister and is handed straight to the coordinator.
@objc(PlannLiveActivityPlugin)
public class PlannLiveActivityPlugin: CAPPlugin, CAPBridgedPlugin {
    public let identifier = "PlannLiveActivityPlugin"
    public let jsName = "PlannLiveActivity"
    public let pluginMethods: [CAPPluginMethod] = [
        CAPPluginMethod(name: "register", returnType: CAPPluginReturnPromise),
        CAPPluginMethod(name: "reconcile", returnType: CAPPluginReturnPromise),
        CAPPluginMethod(name: "unregister", returnType: CAPPluginReturnPromise),
        CAPPluginMethod(name: "getStatus", returnType: CAPPluginReturnPromise),
        CAPPluginMethod(name: "openSettings", returnType: CAPPluginReturnPromise)
    ]

    // register({apiBaseUrl, jwt, fcmToken?}) -> {deviceId, newSecret}
    @objc func register(_ call: CAPPluginCall) {
        guard #available(iOS 16.2, *) else { call.resolve(["supported": false]); return }
        runRegister(call)
    }

    // reconcile() -> {ended, startedLocally}
    @objc func reconcile(_ call: CAPPluginCall) {
        guard #available(iOS 16.2, *) else { call.resolve(["supported": false]); return }
        runReconcile(call)
    }

    // unregister({jwt?}) -> {ended}; without a jwt the secret is deleted locally
    @objc func unregister(_ call: CAPPluginCall) {
        guard #available(iOS 16.2, *) else { call.resolve(["supported": false]); return }
        runUnregister(call)
    }

    // getStatus() -> {supported, enabled, iosVersion}
    @objc func getStatus(_ call: CAPPluginCall) {
        guard #available(iOS 16.2, *) else {
            Task { @MainActor in
                call.resolve(["supported": false, "iosVersion": UIDevice.current.systemVersion])
            }
            return
        }
        runGetStatus(call)
    }

    // openSettings() -> {opened}
    @objc func openSettings(_ call: CAPPluginCall) {
        guard #available(iOS 16.2, *) else { call.resolve(["supported": false]); return }
        Task { @MainActor in
            guard let url = URL(string: UIApplication.openSettingsURLString) else {
                call.reject("Settings URL unavailable", "UNAVAILABLE")
                return
            }
            UIApplication.shared.open(url, options: [:]) { opened in
                call.resolve(["supported": true, "opened": opened])
            }
        }
    }

    // MARK: iOS 16.2+

    @available(iOS 16.2, *)
    private func runRegister(_ call: CAPPluginCall) {
        guard let apiBaseUrl = call.getString("apiBaseUrl"), !apiBaseUrl.isEmpty,
              let jwt = call.getString("jwt"), !jwt.isEmpty else {
            call.reject("apiBaseUrl and jwt are required", "INVALID_ARGUMENTS")
            return
        }
        let fcmToken = call.getString("fcmToken")
        Task { @MainActor in
            do {
                let result = try await LiveActivityCoordinator.shared.register(
                    apiBaseUrl: apiBaseUrl, jwt: jwt, fcmToken: fcmToken)
                call.resolve(["supported": true, "deviceId": result.deviceId, "newSecret": result.newSecret])
            } catch {
                call.reject("Live Activity registration failed", pluginErrorCode(error))
            }
        }
    }

    @available(iOS 16.2, *)
    private func runReconcile(_ call: CAPPluginCall) {
        Task { @MainActor in
            do {
                let outcome = try await LiveActivityCoordinator.shared.reconcile()
                call.resolve(["supported": true, "ended": outcome.ended, "startedLocally": outcome.startedLocally])
            } catch {
                call.reject("Live Activity reconcile failed", pluginErrorCode(error))
            }
        }
    }

    @available(iOS 16.2, *)
    private func runUnregister(_ call: CAPPluginCall) {
        let jwt = call.getString("jwt")
        Task { @MainActor in
            let ended = await LiveActivityCoordinator.shared.unregister(jwt: jwt)
            call.resolve(["supported": true, "ended": ended])
        }
    }

    @available(iOS 16.2, *)
    private func runGetStatus(_ call: CAPPluginCall) {
        Task { @MainActor in
            call.resolve(["supported": true,
                          "enabled": LiveActivityCoordinator.shared.activitiesEnabled,
                          "iosVersion": UIDevice.current.systemVersion])
        }
    }
}
