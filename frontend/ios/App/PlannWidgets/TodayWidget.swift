// Today widget: provider and configuration (spec §5.3).
// The decisions (credential → content, entry dates, reload policy, row phases) live in the
// Linux-tested LiveActivityCore files compiled into this target; this file only does I/O.
// The extension deploys at iOS 16.2, so no availability guards are needed in this file.
import Foundation
import SwiftUI
import WidgetKit

struct TodayEntry: TimelineEntry {
    let date: Date
    let content: WidgetContent
}

struct TodayProvider: TimelineProvider {
    func placeholder(in context: Context) -> TodayEntry {
        TodayEntry(date: Date(), content: .summary(TodaySample.summary(around: Date())))
    }

    /// No network: the gallery gets sample data, a placed widget its cache (spec §5.3).
    func getSnapshot(in context: Context, completion: @escaping (TodayEntry) -> Void) {
        let now = Date()
        if context.isPreview {
            completion(TodayEntry(date: now, content: .summary(TodaySample.summary(around: now))))
            return
        }
        // Privacy: outside the gallery the snapshot shows the real state (signed out, unreachable or
        // this key's cache), never sample rows, so a signed-in salon never sees made-up customer names.
        let key = WidgetCredentialStore.read()?.key
        completion(TodayEntry(date: now, content: widgetContent(.unavailable, cache: TodayCache.read(), currentKey: key,
                                                                now: now)))
    }

    func getTimeline(in context: Context, completion: @escaping (Timeline<TodayEntry>) -> Void) {
        let now = Date()
        guard let credential = WidgetCredentialStore.read() else {
            // Signed out: never show (or keep on disk) the previous user's rows.
            // A failed Keychain read also lands here, e.g. errSecInteractionNotAllowed before the first
            // unlock after a reboot (items are AfterFirstUnlock). That is transient: the 15-min policy
            // below retries, and the app's setWidgetCredential reloads at once.
            TodayCache.remove()
            completion(Timeline(entries: [TodayEntry(date: now, content: .signedOut)],
                                policy: .after(nextReload(nil, from: now))))
            return
        }
        // Every placed widget (small, medium, lock screen...) asks for its own timeline, often in the
        // same burst: one fetch per key per minute serves them all, and the skipped ones reload once
        // that minute is over so an in-app change made meanwhile still arrives.
        if let cache = TodayCache.read(), shouldSkipFetch(cache: cache, currentKey: credential.key, now: now) {
            let content = widgetContent(.unavailable, cache: cache, currentKey: credential.key, now: now)
            completion(TodayTimeline.make(content, now: now,
                                          retryAt: cache.fetchedAt.addingTimeInterval(widgetFetchDedupInterval)))
            return
        }
        Task {
            let outcome = await TodayFetcher.fetch(baseURL: credential.baseURL, key: credential.key)
            switch outcome {
            case .fetched(let summary):
                TodayCache.write(WidgetCacheEnvelope(keyHash: sha256hex(credential.key), summary: summary,
                                                     fetchedAt: Date()))
            case .unauthorized:
                // Revoked or expired key: drop this key's rows and show signed out. The Keychain item
                // stays; the app replaces it with a fresh key the next time it is opened.
                TodayCache.remove()
            case .unavailable:
                break
            }
            let content = widgetContent(outcome, cache: outcome == .unavailable ? TodayCache.read() : nil,
                                        currentKey: credential.key, now: now)
            completion(TodayTimeline.make(content, now: now))
        }
    }
}

enum TodayTimeline {
    /// One entry now and one at every start and end, so rows roll from upcoming to processing to
    /// gone without network; reload policy from `nextReload` (next boundary or 15 min; 60 min or
    /// midnight when nothing is left today; sooner when `retryAt` asks for it).
    static func make(_ content: WidgetContent, now: Date, retryAt: Date? = nil) -> Timeline<TodayEntry> {
        guard case .summary(let summary) = content else {
            return Timeline(entries: [TodayEntry(date: now, content: content)],
                            policy: .after(nextReload(nil, from: now, retryAt: retryAt)))
        }
        let entries = entryDates(summary, from: now).map { TodayEntry(date: $0, content: content) }
        return Timeline(entries: entries, policy: .after(nextReload(summary, from: now, retryAt: retryAt)))
    }
}

enum TodayFetcher {
    /// The summary, `.unauthorized` on 401, otherwise `.unavailable` (no request, transport error,
    /// other status, bad JSON, or 10 s). The status mapping is `fetchOutcome` in LiveActivityCore.
    static func fetch(baseURL: String, key: String) async -> WidgetFetchOutcome {
        guard let request = summaryRequest(baseURL: baseURL, key: key) else { return .unavailable }
        return await withTaskGroup(of: WidgetFetchOutcome.self, returning: WidgetFetchOutcome.self) { group in
            group.addTask {
                guard let result = try? await URLSession.shared.data(for: request) else { return .unavailable }
                let (data, response) = result
                return fetchOutcome(statusCode: (response as? HTTPURLResponse)?.statusCode, data: data)
            }
            group.addTask {
                try? await Task.sleep(nanoseconds: 10_000_000_000)
                return .unavailable
            }
            let first = (await group.next()) ?? .unavailable
            group.cancelAll()
            return first
        }
    }
}

/// `today-summary.json` in the extension's own caches directory, holding a WidgetCacheEnvelope.
enum TodayCache {
    private static var fileURL: URL? {
        FileManager.default.urls(for: .cachesDirectory, in: .userDomainMask).first?
            .appendingPathComponent("today-summary.json")
    }

    static func read() -> WidgetCacheEnvelope? {
        guard let url = fileURL else { return nil }
        return WidgetCacheEnvelope.decode(try? Data(contentsOf: url))
    }

    static func write(_ envelope: WidgetCacheEnvelope) {
        guard let url = fileURL, let data = envelope.encoded() else { return }
        try? data.write(to: url, options: .atomic)
    }

    static func remove() {
        guard let url = fileURL else { return }
        try? FileManager.default.removeItem(at: url)
    }
}

/// Gallery and placeholder data only; never shown for a signed-in user's real widget.
enum TodaySample {
    static func summary(around now: Date) -> WidgetSummary {
        let t = now.timeIntervalSince1970
        func item(_ id: String, _ start: String, _ end: String, _ from: Double, _ to: Double,
                  _ phase: PlannPhase, _ customer: String, _ service: String) -> WidgetItem {
            WidgetItem(id: id, startLabel: start, endLabel: end, startEpoch: t + from, endEpoch: t + to,
                       phase: phase, customerDisplay: customer, serviceName: service, staffName: "Elif")
        }
        return WidgetSummary(
            generatedAt: "", scope: "own", privacyMode: "full", orgName: "",
            counts: .init(total: 7, completed: 2, remaining: 5),
            items: [item("sample-1", "13:30", "14:15", -900, 1800, .processing, "Ayşe Kaya", "Saç Boyama"),
                    item("sample-2", "14:30", "15:00", 2700, 4500, .upcoming, "Zeynep Demir", "Fön"),
                    item("sample-3", "15:30", "16:15", 6300, 9000, .upcoming, "Elif Şahin", "Kesim"),
                    item("sample-4", "16:30", "17:00", 9900, 11700, .upcoming, "Merve Aydın", "Manikür"),
                    item("sample-5", "17:30", "18:30", 13500, 17100, .upcoming, "Selin Yıldız", "Keratin")],
            tomorrowFirst: nil)
    }
}

struct TodayWidget: Widget {
    let kind = "TodayWidget"

    var body: some WidgetConfiguration {
        StaticConfiguration(kind: kind, provider: TodayProvider()) { entry in
            TodayWidgetView(entry: entry)
        }
        .configurationDisplayName(WidgetCopy.galleryName)
        .description(WidgetCopy.galleryDescription)
        .supportedFamilies([.systemSmall, .systemMedium, .systemLarge, .accessoryRectangular, .accessoryCircular])
    }
}
