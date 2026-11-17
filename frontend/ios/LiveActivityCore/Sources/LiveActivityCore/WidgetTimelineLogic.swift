import Foundation

public struct WidgetRow: Equatable, Sendable {
    public var id: String
    public var startLabel: String
    public var endLabel: String
    public var phase: PlannPhase
    public var customerDisplay: String?
    public var serviceName: String
    public var staffName: String?
}

public struct WidgetDay: Equatable, Sendable {
    public var rows: [WidgetRow]
    public var counts: WidgetSummary.Counts
}

public enum WidgetFamilyKind: Sendable { case small, medium, large, rectangular, circular }

private func isLive(_ p: PlannPhase) -> Bool { p == .upcoming || p == .processing }

/// Local evolution of the day between fetches, from the appointment epochs.
public func widgetDay(_ s: WidgetSummary, at date: Date) -> WidgetDay {
    let now = date.timeIntervalSince1970
    var rows: [(row: WidgetRow, start: Double, end: Double)] = []
    var ended = 0
    for it in s.items where isLive(it.phase) {
        if now >= it.endEpoch { ended += 1; continue }
        let phase: PlannPhase = (it.phase == .processing || now >= it.startEpoch) ? .processing : .upcoming
        rows.append((WidgetRow(id: it.id, startLabel: it.startLabel, endLabel: it.endLabel, phase: phase,
                               customerDisplay: it.customerDisplay, serviceName: it.serviceName,
                               staffName: it.staffName), it.startEpoch, it.endEpoch))
    }
    rows.sort { a, b in
        if (a.row.phase == .processing) != (b.row.phase == .processing) { return a.row.phase == .processing }
        let (ka, kb) = a.row.phase == .processing ? (a.end, b.end) : (a.start, b.start)
        return ka != kb ? ka < kb : a.row.id < b.row.id
    }
    let shifted = min(ended, s.counts.remaining)
    let counts = WidgetSummary.Counts(total: s.counts.total,
                                      completed: s.counts.completed + shifted,
                                      remaining: s.counts.remaining - shifted)
    return WidgetDay(rows: rows.map(\.row), counts: counts)
}

private func futureBoundaries(_ s: WidgetSummary, after now: Date) -> [Date] {
    let t = now.timeIntervalSince1970
    let all = s.items.filter { isLive($0.phase) }.flatMap { [$0.startEpoch, $0.endEpoch] }.filter { $0 > t }
    return Array(Set(all)).sorted().map { Date(timeIntervalSince1970: $0) }
}

public func entryDates(_ s: WidgetSummary, from now: Date) -> [Date] {
    Array(([now] + futureBoundaries(s, after: now)).prefix(60))
}

public func nextReload(_ s: WidgetSummary?, from now: Date) -> Date {
    let cap = now.addingTimeInterval(15 * 60)
    guard let s, let next = futureBoundaries(s, after: now).first else { return cap }
    return min(next, cap)
}

public func rows(for family: WidgetFamilyKind, _ day: WidgetDay) -> [WidgetRow] {
    let limit: Int
    switch family {
    case .small, .rectangular: limit = 1
    case .medium: limit = 2
    case .large: limit = 5
    case .circular: limit = 0
    }
    return Array(day.rows.prefix(limit))
}

public func staleLabel(generatedAt: Date, now: Date, tz: TimeZone) -> String? {
    guard now.timeIntervalSince(generatedAt) > 30 * 60 else { return nil }
    var cal = Calendar(identifier: .gregorian)
    cal.timeZone = tz
    let c = cal.dateComponents([.hour, .minute], from: generatedAt)
    return String(format: "Güncellendi %02d:%02d", c.hour ?? 0, c.minute ?? 0)
}
