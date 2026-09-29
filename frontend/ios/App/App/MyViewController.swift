import UIKit
import Capacitor
import WebKit

class MyViewController: CAPBridgeViewController {
    // LaunchScreen.storyboard kök view'ının tag'i; splash eklentisi bu storyboard'u açılış ekranı olarak kullanır.
    private static let launchSplashTag = 7001
    private static let bootSpinnerSize: CGFloat = 30

    private var bootSpinner: UIView?
    private var bootSpinnerTimer: Timer?
    private var bootSpinnerTicks = 0
    private var bootSplashSeen = false

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
            // Sayfa ilk boyanana kadar (ör. ilk kurulumda Capgo paketi uygulayıp yeniden yüklerken)
            // WKWebView beyaz görünmesin. html/body zeminini tema veriyor, uygulama içi etkilenmez.
            webView.isOpaque = false
            webView.backgroundColor = .black
        }
        showBootSpinner()
    }

    override open func viewDidLayoutSubviews() {
        super.viewDidLayoutSubviews()
        layoutBootSpinner()
    }

    // public/index.html'deki #boot-splash halkasıyla aynı boyut, renk, konum ve hız:
    // native splash web ekranına devrettiğinde halka aynı yerde dönmeye devam eder.
    private func showBootSpinner() {
        let size: CGFloat = Self.bootSpinnerSize
        let lineWidth: CGFloat = 2.8
        let ring = UIView(frame: CGRect(x: 0, y: 0, width: size, height: size))
        ring.isUserInteractionEnabled = false

        let center = CGPoint(x: size / 2, y: size / 2)
        let radius = (size - lineWidth) / 2

        let track = CAShapeLayer()
        track.path = UIBezierPath(arcCenter: center, radius: radius, startAngle: 0, endAngle: 2 * .pi, clockwise: true).cgPath
        track.fillColor = nil
        track.strokeColor = UIColor(white: 1, alpha: 0.18).cgColor
        track.lineWidth = lineWidth
        ring.layer.addSublayer(track)

        let arc = CAShapeLayer()
        arc.path = UIBezierPath(arcCenter: center, radius: radius, startAngle: 1.25 * .pi, endAngle: 1.75 * .pi, clockwise: true).cgPath
        arc.fillColor = nil
        arc.strokeColor = UIColor.white.cgColor
        arc.lineWidth = lineWidth
        ring.layer.addSublayer(arc)

        let spin = CABasicAnimation(keyPath: "transform.rotation.z")
        spin.fromValue = 0
        spin.toValue = 2 * Double.pi
        spin.duration = 0.8
        spin.repeatCount = .infinity
        spin.isRemovedOnCompletion = false
        ring.layer.add(spin, forKey: "spin")

        view.addSubview(ring)
        bootSpinner = ring
        layoutBootSpinner()
        // Splash eklentisi açılış ekranını loadView'da main.async ile ekliyor; o işten sonra öne al.
        DispatchQueue.main.async { [weak self] in self?.layoutBootSpinner() }

        bootSpinnerTimer = Timer.scheduledTimer(withTimeInterval: 0.1, repeats: true) { [weak self] _ in
            self?.tickBootSpinner()
        }
    }

    private func layoutBootSpinner() {
        guard let ring = bootSpinner else { return }
        let bounds = view.bounds
        let top = bounds.midY + min(bounds.width * 0.16, 72)
        let size = Self.bootSpinnerSize
        ring.frame = CGRect(x: bounds.midX - size / 2, y: top, width: size, height: size)
        view.bringSubviewToFront(ring)
    }

    private func tickBootSpinner() {
        bootSpinnerTicks += 1
        if let splash = view.viewWithTag(Self.launchSplashTag), splash.superview != nil, splash.alpha > 0.01 {
            bootSplashSeen = true
            layoutBootSpinner()
            if bootSpinnerTicks < 200 { return }
        } else if !bootSplashSeen && bootSpinnerTicks < 20 {
            return
        }
        hideBootSpinner()
    }

    private func hideBootSpinner() {
        bootSpinnerTimer?.invalidate()
        bootSpinnerTimer = nil
        bootSpinner?.layer.removeAllAnimations()
        bootSpinner?.removeFromSuperview()
        bootSpinner = nil
    }
}
