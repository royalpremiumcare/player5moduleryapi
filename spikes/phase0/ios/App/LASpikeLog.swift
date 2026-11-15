// PHASE 0 SPIKE — throwaway. Target: App.
// Append-only file log so S2 can prove what ran while the app was NOT in the foreground
// (timestamps + applicationState are recorded for every event).
import Foundation
import UIKit

enum LASpikeLog {
    private static let queue = DispatchQueue(label: "co.plannapp.laspike.log")
    private static var url: URL {
        FileManager.default.urls(for: .documentDirectory, in: .userDomainMask)[0]
            .appendingPathComponent("la-spike.log")
    }
    private static let iso: ISO8601DateFormatter = {
        let f = ISO8601DateFormatter()
        f.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        return f
    }()

    static func write(_ message: String) {
        let state: String
        if Thread.isMainThread {
            state = String(describing: UIApplication.shared.applicationState.rawValue) // 0 active, 1 inactive, 2 background
        } else {
            state = "?"
        }
        let line = "\(iso.string(from: Date())) appState=\(state) \(message)\n"
        NSLog("[LASpike] %@", line)
        queue.async {
            guard let data = line.data(using: .utf8) else { return }
            if let h = try? FileHandle(forWritingTo: url) {
                h.seekToEndOfFile(); h.write(data); try? h.close()
            } else {
                try? data.write(to: url)
            }
        }
    }

    static func read() -> String { (try? String(contentsOf: url, encoding: .utf8)) ?? "" }
    static func clear() { queue.async { try? FileManager.default.removeItem(at: url) } }
}

extension Data {
    var laSpikeHex: String { map { String(format: "%02x", $0) }.joined() }
}
