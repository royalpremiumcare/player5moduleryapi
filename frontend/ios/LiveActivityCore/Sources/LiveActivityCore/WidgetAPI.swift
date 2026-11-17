import Foundation
#if canImport(FoundationNetworking)
import FoundationNetworking
#endif

public struct WidgetCacheEnvelope: Codable, Sendable {
    public var keyHash: String
    public var summary: WidgetSummary
    public var fetchedAt: Date

    public init(keyHash: String, summary: WidgetSummary, fetchedAt: Date) {
        self.keyHash = keyHash
        self.summary = summary
        self.fetchedAt = fetchedAt
    }
}

/// The cache file is written and read only through these, with plain coders (default date
/// strategy) on both sides.
public extension WidgetCacheEnvelope {
    func encoded() -> Data? { try? JSONEncoder().encode(self) }

    static func decode(_ data: Data?) -> WidgetCacheEnvelope? {
        guard let data else { return nil }
        return try? JSONDecoder().decode(WidgetCacheEnvelope.self, from: data)
    }
}

/// The salons' calendar: the summary's "today" is the Europe/Istanbul day (fixed UTC+3 since 2016,
/// which is also the fallback if the zone database is missing).
public let widgetTimeZone: TimeZone = TimeZone(identifier: "Europe/Istanbul") ?? TimeZone(secondsFromGMT: 3 * 3600)!

private var widgetCalendar: Calendar {
    var cal = Calendar(identifier: .gregorian)
    cal.timeZone = widgetTimeZone
    return cal
}

public func isSameTRDay(_ a: Date, _ b: Date) -> Bool {
    widgetCalendar.isDate(a, inSameDayAs: b)
}

/// The next Europe/Istanbul midnight after `date`.
public func nextTRMidnight(after date: Date) -> Date {
    let cal = widgetCalendar
    let start = cal.startOfDay(for: date)
    return cal.date(byAdding: .day, value: 1, to: start) ?? date.addingTimeInterval(24 * 3600)
}

/// A cached summary is only usable by the credential that fetched it, and only on the TR calendar
/// day it was generated: after midnight yesterday's counts and "Yarın ilk" line would be wrong.
public func usableCache(_ env: WidgetCacheEnvelope?, currentKey: String?, now: Date) -> WidgetSummary? {
    guard let env, let key = currentKey, sha256hex(key) == env.keyHash,
          let generated = env.summary.generatedAtDate, isSameTRDay(generated, now) else { return nil }
    return env.summary
}

/// The result of one summary request, as the widget acts on it.
public enum WidgetFetchOutcome: Equatable, Sendable {
    case fetched(WidgetSummary)
    /// 401: the key is revoked, expired or its user is inactive. The widget drops its cache and
    /// shows signed out; the app re-issues a key the next time it comes to the foreground.
    case unauthorized
    /// No data: transport error, timeout, rate limit, any other status, bad JSON, or not attempted.
    case unavailable
}

public func fetchOutcome(statusCode: Int?, data: Data?) -> WidgetFetchOutcome {
    guard let statusCode else { return .unavailable }
    if statusCode == 401 { return .unauthorized }
    guard (200..<300).contains(statusCode), let data,
          let summary = try? JSONDecoder().decode(WidgetSummary.self, from: data) else { return .unavailable }
    return .fetched(summary)
}

/// Every widget instance (small, medium, lock screen...) runs its own timeline. Within this window
/// after a fetch for the same key they reuse the cache instead of calling the server again.
public let widgetFetchDedupInterval: TimeInterval = 60

public func shouldSkipFetch(cache: WidgetCacheEnvelope?, currentKey: String?, now: Date) -> Bool {
    guard let cache, usableCache(cache, currentKey: currentKey, now: now) != nil else { return false }
    let age = now.timeIntervalSince(cache.fetchedAt)
    return age >= 0 && age < widgetFetchDedupInterval
}

public func summaryRequest(baseURL: String, key: String) -> URLRequest? {
    var base = baseURL
    while base.hasSuffix("/") { base.removeLast() }
    guard base.lowercased().hasPrefix("https://"),
          let url = URL(string: base + "/api/widget/summary"), url.host?.isEmpty == false else { return nil }
    var req = URLRequest(url: url, timeoutInterval: 10)
    req.httpMethod = "GET"
    req.setValue(key, forHTTPHeaderField: "X-Plann-Widget-Key")
    return req
}

public func sha256hex(_ string: String) -> String {
    sha256(Array(string.utf8)).map { String(format: "%02x", $0) }.joined()
}

private let k256: [UInt32] = [
    0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5,
    0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3, 0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174,
    0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc, 0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
    0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7, 0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967,
    0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13, 0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85,
    0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
    0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3,
    0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208, 0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2,
]

func sha256(_ message: [UInt8]) -> [UInt8] {
    var h: [UInt32] = [0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a,
                       0x510e527f, 0x9b05688c, 0x1f83d9ab, 0x5be0cd19]
    var data = message
    data.append(0x80)
    while data.count % 64 != 56 { data.append(0) }
    let bits = UInt64(message.count) * 8
    for i in (0..<8).reversed() { data.append(UInt8((bits >> (UInt64(i) * 8)) & 0xff)) }

    func rotr(_ x: UInt32, _ n: UInt32) -> UInt32 { (x >> n) | (x << (32 - n)) }
    for chunk in stride(from: 0, to: data.count, by: 64) {
        var w = [UInt32](repeating: 0, count: 64)
        for i in 0..<16 {
            let j = chunk + i * 4
            w[i] = UInt32(data[j]) << 24 | UInt32(data[j + 1]) << 16 | UInt32(data[j + 2]) << 8 | UInt32(data[j + 3])
        }
        for i in 16..<64 {
            let s0 = rotr(w[i - 15], 7) ^ rotr(w[i - 15], 18) ^ (w[i - 15] >> 3)
            let s1 = rotr(w[i - 2], 17) ^ rotr(w[i - 2], 19) ^ (w[i - 2] >> 10)
            w[i] = w[i - 16] &+ s0 &+ w[i - 7] &+ s1
        }
        var a = h[0], b = h[1], c = h[2], d = h[3], e = h[4], f = h[5], g = h[6], hh = h[7]
        for i in 0..<64 {
            let s1 = rotr(e, 6) ^ rotr(e, 11) ^ rotr(e, 25)
            let ch = (e & f) ^ (~e & g)
            let t1 = hh &+ s1 &+ ch &+ k256[i] &+ w[i]
            let s0 = rotr(a, 2) ^ rotr(a, 13) ^ rotr(a, 22)
            let maj = (a & b) ^ (a & c) ^ (b & c)
            let t2 = s0 &+ maj
            hh = g; g = f; f = e; e = d &+ t1; d = c; c = b; b = a; a = t1 &+ t2
        }
        h[0] = h[0] &+ a; h[1] = h[1] &+ b; h[2] = h[2] &+ c; h[3] = h[3] &+ d
        h[4] = h[4] &+ e; h[5] = h[5] &+ f; h[6] = h[6] &+ g; h[7] = h[7] &+ hh
    }
    return h.flatMap { [UInt8($0 >> 24), UInt8(($0 >> 16) & 0xff), UInt8(($0 >> 8) & 0xff), UInt8($0 & 0xff)] }
}
