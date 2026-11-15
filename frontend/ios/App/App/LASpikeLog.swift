// PHASE 0 SPIKE — throwaway. Append-only file log so S2 can prove what ran while the app
// was NOT in the foreground. Callers on the main actor add appState themselves.
import Foundation

enum LASpikeLog {
    private static let queue = DispatchQueue(label: "co.plannapp.laspike.log")

    private static var fileURL: URL {
        FileManager.default.urls(for: .documentDirectory, in: .userDomainMask)[0]
            .appendingPathComponent("la-spike.log")
    }

    private static func timestamp() -> String {
        let f = ISO8601DateFormatter()
        f.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        return f.string(from: Date())
    }

    static func write(_ message: String) {
        let line = "\(timestamp()) \(message)\n"
        NSLog("[LASpike] %@", line)
        let url = fileURL
        queue.async {
            guard let data = line.data(using: .utf8) else { return }
            if let handle = try? FileHandle(forWritingTo: url) {
                handle.seekToEndOfFile()
                handle.write(data)
                handle.closeFile()
            } else {
                try? data.write(to: url)
            }
        }
    }

    static func read() -> String {
        queue.sync { (try? String(contentsOf: fileURL, encoding: .utf8)) ?? "" }
    }

    static func clear() {
        let url = fileURL
        queue.async { try? FileManager.default.removeItem(at: url) }
    }
}

extension Data {
    var laSpikeHex: String { map { String(format: "%02x", $0) }.joined() }
}
