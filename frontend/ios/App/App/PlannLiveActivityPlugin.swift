import Foundation
import Capacitor
import UIKit
import WidgetKit

/// JS bridge for the slot Live Activities (`PlannLiveActivity`). Compiles for the iOS 15 app
/// target: every Live Activity method gates itself on iOS 16.2 on an iPhone and resolves
/// `{supported:false}` otherwise (iPad has no lock-screen Live Activities).
/// The JWT arrives only for register/unregister and is handed straight to the coordinator.
/// The Home Screen widget methods (setWidgetCredential, clearWidgetCredential, reloadWidgets,
/// widgetCredentialPresent) gate on iOS 16.2 only (the widget extension's deployment target), not on
/// iPhone: iPad has widgets.
@objc(PlannLiveActivityPlugin)
public class PlannLiveActivityPlugin: CAPPlugin, CAPBridgedPlugin {
    public let identifier = "PlannLiveActivityPlugin"
    public let jsName = "PlannLiveActivity"
    public let pluginMethods: [CAPPluginMethod] = [
        CAPPluginMethod(name: "register", returnType: CAPPluginReturnPromise),
        CAPPluginMethod(name: "reconcile", returnType: CAPPluginReturnPromise),
        CAPPluginMethod(name: "unregister", returnType: CAPPluginReturnPromise),
        CAPPluginMethod(name: "getStatus", returnType: CAPPluginReturnPromise),
        CAPPluginMethod(name: "openSettings", returnType: CAPPluginReturnPromise),
        CAPPluginMethod(name: "setWidgetCredential", returnType: CAPPluginReturnPromise),
        CAPPluginMethod(name: "clearWidgetCredential", returnType: CAPPluginReturnPromise),
        CAPPluginMethod(name: "reloadWidgets", returnType: CAPPluginReturnPromise),
        CAPPluginMethod(name: "widgetCredentialPresent", returnType: CAPPluginReturnPromise)
    ]

    /// Live Activities exist on iPhone only; iPad and Mac (iPad idiom) report unsupported.
    @MainActor private static var isPhone: Bool { UIDevice.current.userInterfaceIdiom == .phone }

    // register({apiBaseUrl, jwt, fcmToken?}) -> {deviceId, newSecret, hasFcmToken}
    @objc func register(_ call: CAPPluginCall) {
        guard #available(iOS 16.2, *) else { call.resolve(["supported": false]); return }
        Task { @MainActor in
            guard Self.isPhone else { call.resolve(["supported": false]); return }
            self.runRegister(call)
        }
    }

    // reconcile() -> {ended, startedLocally}
    @objc func reconcile(_ call: CAPPluginCall) {
        guard #available(iOS 16.2, *) else { call.resolve(["supported": false]); return }
        Task { @MainActor in
            guard Self.isPhone else { call.resolve(["supported": false]); return }
            self.runReconcile(call)
        }
    }

    // unregister({jwt?}) -> {ended}; without a jwt the secret is deleted locally
    @objc func unregister(_ call: CAPPluginCall) {
        guard #available(iOS 16.2, *) else { call.resolve(["supported": false]); return }
        Task { @MainActor in
            guard Self.isPhone else { call.resolve(["supported": false]); return }
            self.runUnregister(call)
        }
    }

    // getStatus() -> {supported, enabled, iosVersion}
    @objc func getStatus(_ call: CAPPluginCall) {
        guard #available(iOS 16.2, *) else {
            Task { @MainActor in
                call.resolve(["supported": false, "iosVersion": UIDevice.current.systemVersion])
            }
            return
        }
        Task { @MainActor in
            guard Self.isPhone else {
                call.resolve(["supported": false, "iosVersion": UIDevice.current.systemVersion])
                return
            }
            self.runGetStatus(call)
        }
    }

    // openSettings() -> {opened}
    @objc func openSettings(_ call: CAPPluginCall) {
        guard #available(iOS 16.2, *) else { call.resolve(["supported": false]); return }
        Task { @MainActor in
            guard Self.isPhone else { call.resolve(["supported": false]); return }
            guard let url = URL(string: UIApplication.openSettingsURLString) else {
                call.reject("Settings URL unavailable", "UNAVAILABLE")
                return
            }
            UIApplication.shared.open(url, options: [:]) { opened in
                call.resolve(["supported": true, "opened": opened])
            }
        }
    }

    // MARK: Home Screen widgets (iPhone and iPad, iOS 16.2+)

    // setWidgetCredential({key, baseUrl}) -> {previousKey?}; previousKey is the key it replaced (the
    // app revokes it). Rejects INVALID_URL unless baseUrl is https.
    @objc func setWidgetCredential(_ call: CAPPluginCall) {
        guard #available(iOS 16.2, *) else { call.resolve(["supported": false]); return }
        guard let key = call.getString("key"), !key.isEmpty else {
            call.reject("key is required", "INVALID_ARGUMENTS")
            return
        }
        let baseUrl = call.getString("baseUrl") ?? ""
        guard WidgetBridge.isAcceptableBaseURL(baseUrl) else {
            call.reject("baseUrl must be an https URL", "INVALID_URL")
            return
        }
        let previousKey: String?
        do {
            previousKey = try WidgetCredentialStore.write(key: key, baseURL: baseUrl)
        } catch {
            call.reject("Widget credential could not be saved", "KEYCHAIN_ERROR")
            return
        }
        let result: [String: Any] = previousKey.map { ["previousKey": $0] } ?? [:]
        Task { @MainActor in
            Self.reloadWidgetTimelinesNow()
            call.resolve(result)
        }
    }

    // clearWidgetCredential() -> {key?}; key is the deleted key (logout revokes exactly that one).
    // The widget then shows the signed-out state.
    @objc func clearWidgetCredential(_ call: CAPPluginCall) {
        guard #available(iOS 16.2, *) else { call.resolve(["supported": false]); return }
        let result: [String: Any] = WidgetCredentialStore.clear().map { ["key": $0] } ?? [:]
        Task { @MainActor in
            Self.reloadWidgetTimelinesNow()
            call.resolve(result)
        }
    }

    // widgetCredentialPresent() -> {present}; false when the widget has no credential (never stored,
    // a failed write, or removed), so the app issues a new key without waiting for its 24 h stamp.
    @objc func widgetCredentialPresent(_ call: CAPPluginCall) {
        guard #available(iOS 16.2, *) else { call.resolve(["present": false, "supported": false]); return }
        call.resolve(["present": WidgetCredentialStore.read() != nil])
    }

    // reloadWidgets() -> {}; at most one reload per 5 s
    @objc func reloadWidgets(_ call: CAPPluginCall) {
        guard #available(iOS 16.2, *) else { call.resolve(["supported": false]); return }
        Task { @MainActor in
            Self.requestWidgetReload()
            call.resolve([:])
        }
    }

    @MainActor private static var lastWidgetReload: Date?
    @MainActor private static var trailingWidgetReload: Task<Void, Never>?

    /// Reloads at once (a credential change must show immediately) and restarts the 5 s window.
    @MainActor private static func reloadWidgetTimelinesNow() {
        trailingWidgetReload?.cancel()
        trailingWidgetReload = nil
        lastWidgetReload = Date()
        WidgetCenter.shared.reloadAllTimelines()
    }

    /// Debounced reload: the first call reloads; calls inside the 5 s window collapse into one
    /// reload at the end of the window, so the last data change still reaches the widget.
    @MainActor private static func requestWidgetReload() {
        let now = Date()
        if WidgetBridge.shouldReload(last: lastWidgetReload, now: now) {
            reloadWidgetTimelinesNow()
        } else if trailingWidgetReload == nil {
            let delay = WidgetBridge.reloadDelay(last: lastWidgetReload, now: now)
            trailingWidgetReload = Task { @MainActor in
                try? await Task.sleep(nanoseconds: UInt64(delay * 1_000_000_000))
                guard !Task.isCancelled else { return }
                Self.trailingWidgetReload = nil
                Self.reloadWidgetTimelinesNow()
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
                call.resolve(["supported": true, "deviceId": result.deviceId, "newSecret": result.newSecret,
                              "hasFcmToken": result.hasFcmToken])
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
