import Foundation
import Capacitor
import FirebaseMessaging
import UIKit

@objc(FCMTokenPlugin)
public class FCMTokenPlugin: CAPPlugin, CAPBridgedPlugin {
    public let identifier = "FCMTokenPlugin"
    public let jsName = "FCMTokenPlugin"
    public let pluginMethods: [CAPPluginMethod] = [
        CAPPluginMethod(name: "getToken", returnType: CAPPluginReturnPromise),
        CAPPluginMethod(name: "registerAndGetToken", returnType: CAPPluginReturnPromise)
    ]

    @objc func getToken(_ call: CAPPluginCall) {
        getTokenWithRetry(attempts: 5, delay: 2.0) { token, error in
            if let error = error {
                call.reject("Failed to get FCM token", nil, error)
                return
            }
            call.resolve(["token": token ?? ""])
        }
    }

    @objc func registerAndGetToken(_ call: CAPPluginCall) {
        DispatchQueue.main.async {
            UIApplication.shared.registerForRemoteNotifications()
        }
        // Wait for APNs token exchange then get FCM token
        getTokenWithRetry(attempts: 8, delay: 2.0) { token, error in
            if let error = error {
                call.reject("Failed to get FCM token", nil, error)
                return
            }
            call.resolve(["token": token ?? ""])
        }
    }

    private func getTokenWithRetry(attempts: Int, delay: TimeInterval, completion: @escaping (String?, Error?) -> Void) {
        Messaging.messaging().token { token, error in
            if let token = token, !token.isEmpty {
                completion(token, nil)
            } else if attempts > 1 {
                DispatchQueue.main.asyncAfter(deadline: .now() + delay) {
                    self.getTokenWithRetry(attempts: attempts - 1, delay: delay, completion: completion)
                }
            } else {
                completion(nil, error ?? NSError(domain: "FCMTokenPlugin", code: -1, userInfo: [NSLocalizedDescriptionKey: "FCM token not available after retries"]))
            }
        }
    }
}
