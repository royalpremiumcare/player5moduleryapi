import UIKit
import Capacitor
import WebKit

class MyViewController: CAPBridgeViewController {
    override open func capacitorDidLoad() {
        bridge?.registerPluginInstance(FCMTokenPlugin())
        bridge?.registerPluginInstance(ContactPickerPlugin())
    }

    // iOS native sağa-kaydırma (swipe-back) ve sola-kaydırma (forward) gesture'ları.
    // WKWebView, history stack'ı (window.history) üzerinden çalışır; React Router
    // pushState ile gezindiği için kullanıcı parmağıyla geri/ileri gidebilir.
    override open func viewDidLoad() {
        super.viewDidLoad()
        if let webView = self.webView as? WKWebView {
            webView.allowsBackForwardNavigationGestures = true
        }
    }
}
