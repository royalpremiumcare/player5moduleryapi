// PHASE 0 SPIKE — throwaway. Native test screen, opened with the URL  plannapp://la-spike
// (type it into Safari on the device). Works without a Mac / Web Inspector and independently
// of the web bundle (Capgo OTA may replace the JS; this screen is native).
import ActivityKit
import FirebaseMessaging
import UIKit

final class LASpikeDebugViewController: UIViewController {
    private let textView = UITextView()
    private var fcmToken: String = "(loading)"

    static func present() {
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.6) {
            guard let root = UIApplication.shared.connectedScenes
                .compactMap({ $0 as? UIWindowScene })
                .flatMap({ $0.windows })
                .first(where: { $0.isKeyWindow })?.rootViewController
                ?? UIApplication.shared.windows.first?.rootViewController else {
                LASpikeLog.write("debugScreen: no root view controller")
                return
            }
            var top = root
            while let presented = top.presentedViewController { top = presented }
            if top is LASpikeDebugViewController { return }
            let vc = LASpikeDebugViewController()
            vc.modalPresentationStyle = .fullScreen
            top.present(vc, animated: true)
        }
    }

    override func viewDidLoad() {
        super.viewDidLoad()
        view.backgroundColor = .black

        textView.isEditable = false
        textView.isSelectable = true
        textView.backgroundColor = .black
        textView.textColor = .white
        textView.font = UIFont.monospacedSystemFont(ofSize: 11, weight: .regular)
        textView.translatesAutoresizingMaskIntoConstraints = false

        let buttons: [(String, Selector)] = [
            ("Yenile", #selector(refresh)),
            ("Tokenları kopyala", #selector(copyTokens)),
            ("1 LA başlat (2 dk sonra)", #selector(startOne)),
            ("12 LA başlat (S3 limit)", #selector(startTwelve)),
            ("Tüm LA'ları bitir", #selector(endAll)),
            ("Logu paylaş", #selector(shareLog)),
            ("Logu temizle", #selector(clearLog)),
            ("Kapat", #selector(close)),
        ]
        let rows = UIStackView()
        rows.axis = .vertical
        rows.spacing = 6
        rows.translatesAutoresizingMaskIntoConstraints = false
        var index = 0
        while index < buttons.count {
            let row = UIStackView()
            row.axis = .horizontal
            row.spacing = 6
            row.distribution = .fillEqually
            for (title, action) in buttons[index..<min(index + 2, buttons.count)] {
                let b = UIButton(type: .system)
                b.setTitle(title, for: .normal)
                b.titleLabel?.font = UIFont.systemFont(ofSize: 13, weight: .semibold)
                b.titleLabel?.adjustsFontSizeToFitWidth = true
                b.setTitleColor(.black, for: .normal)
                b.backgroundColor = .white
                b.layer.cornerRadius = 8
                b.heightAnchor.constraint(equalToConstant: 38).isActive = true
                b.addTarget(self, action: action, for: .touchUpInside)
                row.addArrangedSubview(b)
            }
            rows.addArrangedSubview(row)
            index += 2
        }

        view.addSubview(rows)
        view.addSubview(textView)
        let g = view.safeAreaLayoutGuide
        NSLayoutConstraint.activate([
            rows.topAnchor.constraint(equalTo: g.topAnchor, constant: 8),
            rows.leadingAnchor.constraint(equalTo: g.leadingAnchor, constant: 12),
            rows.trailingAnchor.constraint(equalTo: g.trailingAnchor, constant: -12),
            textView.topAnchor.constraint(equalTo: rows.bottomAnchor, constant: 8),
            textView.leadingAnchor.constraint(equalTo: g.leadingAnchor, constant: 8),
            textView.trailingAnchor.constraint(equalTo: g.trailingAnchor, constant: -8),
            textView.bottomAnchor.constraint(equalTo: g.bottomAnchor),
        ])

        UIApplication.shared.registerForRemoteNotifications()
        Messaging.messaging().token { [weak self] token, error in
            DispatchQueue.main.async {
                self?.fcmToken = token ?? "(error: \(error?.localizedDescription ?? "nil"))"
                self?.refresh()
            }
        }
        refresh()
    }

    // MARK: - State

    private func stateDictionary() -> [String: Any] {
        var d: [String: Any] = [
            "ios": UIDevice.current.systemVersion,
            "build": (Bundle.main.infoDictionary?["CFBundleShortVersionString"] as? String ?? "?")
                + " (" + (Bundle.main.infoDictionary?["CFBundleVersion"] as? String ?? "?") + ")",
            "fcm_token": fcmToken,
        ]
        guard #available(iOS 16.2, *) else {
            d["live_activities"] = "unsupported (< iOS 16.2)"
            return d
        }
        let info = ActivityAuthorizationInfo()
        d["activities_enabled"] = info.areActivitiesEnabled
        d["frequent_pushes_enabled"] = info.frequentPushesEnabled
        if #available(iOS 17.2, *) {
            d["push_to_start_token"] = Activity<PlannAppointmentAttributes>.pushToStartToken?.laSpikeHex
                ?? LASpikeObservers.shared.lastPushToStartToken ?? "nil"
        }
        d["activities"] = Activity<PlannAppointmentAttributes>.activities.map { a -> [String: Any] in
            [
                "activity_id": a.id,
                "appointment_id": a.attributes.appointmentId,
                "state": String(describing: a.activityState),
                "phase": a.content.state.phase,
                "version": a.content.state.version,
                "start_epoch": a.content.state.startEpoch,
                "push_token": a.pushToken?.laSpikeHex ?? LASpikeObservers.shared.activityTokens[a.id] ?? "nil",
            ]
        }
        return d
    }

    private func stateJSON() -> String {
        guard let data = try? JSONSerialization.data(withJSONObject: stateDictionary(),
                                                     options: [.prettyPrinted, .sortedKeys]),
              let s = String(data: data, encoding: .utf8) else { return "{}" }
        return s
    }

    @objc private func refresh() {
        textView.text = "PLANN Live Activity SPIKE — test amaçlı\n\n" + stateJSON()
            + "\n\n──────── LOG ────────\n" + LASpikeLog.read()
    }

    // MARK: - Actions

    @objc private func copyTokens() {
        UIPasteboard.general.string = stateJSON()
        LASpikeLog.write("copyTokens")
        flash("Kopyalandı — sohbete yapıştırın")
    }

    @objc private func startOne() { startLocal(count: 1) }
    @objc private func startTwelve() { startLocal(count: 12) }

    private func startLocal(count: Int) {
        guard #available(iOS 16.2, *) else { flash("iOS 16.2+ gerekli"); return }
        let fmt = DateFormatter()
        fmt.dateFormat = "HH:mm"
        fmt.timeZone = TimeZone(identifier: "Europe/Istanbul")
        var ok = 0
        var failures: [String] = []
        for i in 0..<count {
            let start = Date().addingTimeInterval(TimeInterval(120 + i * 60))
            let end = start.addingTimeInterval(45 * 60)
            let state = PlannAppointmentAttributes.ContentState(
                phase: "upcoming",
                startEpoch: start.timeIntervalSince1970,
                endEpoch: end.timeIntervalSince1970,
                startLabel: fmt.string(from: start),
                endLabel: fmt.string(from: end),
                customerDisplay: "Test \(i + 1)",
                serviceName: "Spike Hizmet",
                staffName: nil,
                version: 1)
            let attrs = PlannAppointmentAttributes(
                appointmentId: "local-\(Int(Date().timeIntervalSince1970))-\(i)", orgId: "spike")
            do {
                let activity = try Activity.request(
                    attributes: attrs,
                    content: ActivityContent(state: state, staleDate: start),
                    pushType: .token)
                ok += 1
                LASpikeLog.write("startLocal i=\(i) ok id=\(activity.id)")
                LASpikeObservers.shared.observe(activity, origin: "startLocal")
            } catch let e as ActivityAuthorizationError {
                failures.append("i=\(i) \(e)")
                LASpikeLog.write("startLocal i=\(i) ActivityAuthorizationError=\(e)")
            } catch {
                failures.append("i=\(i) \(error)")
                LASpikeLog.write("startLocal i=\(i) error=\(error)")
            }
        }
        LASpikeLog.write("startLocal summary requested=\(count) ok=\(ok) active=\(Activity<PlannAppointmentAttributes>.activities.count) failures=\(failures)")
        flash("Başlatılan: \(ok)/\(count)")
    }

    @objc private func endAll() {
        guard #available(iOS 16.2, *) else { return }
        let all = Activity<PlannAppointmentAttributes>.activities
        Task {
            for a in all {
                await a.end(nil, dismissalPolicy: .immediate)
            }
            LASpikeLog.write("endAll ended=\(all.count)")
            await MainActor.run { self.flash("Bitirildi: \(all.count)") }
        }
    }

    @objc private func shareLog() {
        let text = stateJSON() + "\n\n" + LASpikeLog.read()
        let vc = UIActivityViewController(activityItems: [text], applicationActivities: nil)
        vc.popoverPresentationController?.sourceView = view
        present(vc, animated: true)
    }

    @objc private func clearLog() {
        LASpikeLog.clear()
        flash("Log temizlendi")
    }

    @objc private func close() { dismiss(animated: true) }

    private func flash(_ message: String) {
        refresh()
        let alert = UIAlertController(title: nil, message: message, preferredStyle: .alert)
        present(alert, animated: true)
        DispatchQueue.main.asyncAfter(deadline: .now() + 1.2) { alert.dismiss(animated: true) }
    }
}
