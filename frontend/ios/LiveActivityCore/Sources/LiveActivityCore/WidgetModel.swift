import Foundation

public struct WidgetItem: Codable, Sendable, Equatable {
    public var id: String
    public var startLabel: String
    public var endLabel: String
    public var startEpoch: Double
    public var endEpoch: Double
    public var phase: PlannPhase
    public var customerDisplay: String?
    public var serviceName: String
    public var staffName: String?

    public init(id: String, startLabel: String, endLabel: String, startEpoch: Double, endEpoch: Double,
                phase: PlannPhase, customerDisplay: String?, serviceName: String, staffName: String?) {
        self.id = id
        self.startLabel = startLabel
        self.endLabel = endLabel
        self.startEpoch = startEpoch
        self.endEpoch = endEpoch
        self.phase = phase
        self.customerDisplay = customerDisplay
        self.serviceName = serviceName
        self.staffName = staffName
    }

    public var startDate: Date { Date(timeIntervalSince1970: startEpoch) }
    public var endDate: Date { Date(timeIntervalSince1970: endEpoch) }
}

public struct WidgetTomorrowItem: Codable, Sendable, Equatable {
    public var startLabel: String
    public var customerDisplay: String?
    public var serviceName: String

    public init(startLabel: String, customerDisplay: String?, serviceName: String) {
        self.startLabel = startLabel
        self.customerDisplay = customerDisplay
        self.serviceName = serviceName
    }
}

public struct WidgetSummary: Codable, Sendable, Equatable {
    public struct Counts: Codable, Sendable, Equatable {
        public var total: Int
        public var completed: Int
        public var remaining: Int

        public init(total: Int, completed: Int, remaining: Int) {
            self.total = total
            self.completed = completed
            self.remaining = remaining
        }
    }

    public var generatedAt: String
    public var scope: String
    public var privacyMode: String
    public var orgName: String?
    public var counts: Counts
    public var items: [WidgetItem]
    public var tomorrowFirst: WidgetTomorrowItem?

    public init(generatedAt: String, scope: String, privacyMode: String, orgName: String?, counts: Counts,
                items: [WidgetItem], tomorrowFirst: WidgetTomorrowItem?) {
        self.generatedAt = generatedAt
        self.scope = scope
        self.privacyMode = privacyMode
        self.orgName = orgName
        self.counts = counts
        self.items = items
        self.tomorrowFirst = tomorrowFirst
    }

    /// ISO-8601 with offset; fractional seconds (any digit count) optional.
    public var generatedAtDate: Date? { parseISO8601(generatedAt) }
}

func parseISO8601(_ raw: String) -> Date? {
    var base = raw
    var fraction = 0.0
    if let dot = raw.firstIndex(of: ".") {
        var end = raw.index(after: dot)
        while end < raw.endIndex, raw[end].isASCIINumber { end = raw.index(after: end) }
        let digits = raw[raw.index(after: dot)..<end]
        guard !digits.isEmpty, let f = Double("0." + digits) else { return nil }
        fraction = f
        base = String(raw[raw.startIndex..<dot]) + String(raw[end...])
    }
    let f = ISO8601DateFormatter()
    f.formatOptions = [.withInternetDateTime]
    guard let d = f.date(from: base) else { return nil }
    return d.addingTimeInterval(fraction)
}

private extension Character {
    var isASCIINumber: Bool { ("0"..."9").contains(self) }
}
