import Foundation

public enum PlannPhase: String, Codable, Sendable {
    case upcoming, processing, completed, cancelled, removed, unknown

    public init(from decoder: Decoder) throws {
        let raw = try decoder.singleValueContainer().decode(String.self)
        self = PlannPhase(rawValue: raw) ?? .unknown
    }
}

public struct PlannContentState: Codable, Hashable, Sendable {
    public var phase: PlannPhase
    public var startEpoch: Double
    public var endEpoch: Double
    public var startLabel: String
    public var endLabel: String
    public var customerDisplay: String?
    public var serviceName: String
    public var staffName: String?
    public var version: Int
    public var appointmentId: String
    /// Sector token (hair, beauty, ...); nil from older servers.
    public var icon: String?

    public init(phase: PlannPhase, startEpoch: Double, endEpoch: Double,
                startLabel: String, endLabel: String, customerDisplay: String?,
                serviceName: String, staffName: String?, version: Int, appointmentId: String, icon: String? = nil) {
        self.phase = phase
        self.startEpoch = startEpoch
        self.endEpoch = endEpoch
        self.startLabel = startLabel
        self.endLabel = endLabel
        self.customerDisplay = customerDisplay
        self.serviceName = serviceName
        self.staffName = staffName
        self.version = version
        self.appointmentId = appointmentId
        self.icon = icon
    }

    public var startDate: Date { Date(timeIntervalSince1970: startEpoch) }
    public var endDate: Date { Date(timeIntervalSince1970: endEpoch) }

    public var isTerminal: Bool {
        switch phase {
        case .completed, .cancelled, .removed, .unknown: return true
        case .upcoming, .processing: return false
        }
    }
}

public struct SlotId: Hashable, Sendable {
    public let deviceId: String
    public let index: Int

    public init?(_ raw: String) {
        guard let colon = raw.lastIndex(of: ":") else { return nil }
        let device = String(raw[raw.startIndex..<colon])
        guard !device.isEmpty,
              let n = Int(raw[raw.index(after: colon)...]),
              (1...5).contains(n) else { return nil }
        self.deviceId = device
        self.index = n
    }

    public var raw: String { "\(deviceId):\(index)" }
}

public func shouldApply(incoming: Int, current: Int?) -> Bool {
    guard let current = current else { return true }
    return incoming >= current
}
