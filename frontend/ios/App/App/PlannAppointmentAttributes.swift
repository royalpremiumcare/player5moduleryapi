// PHASE 0 SPIKE — throwaway (branch spike/phase0-live-activities). Not for release.
// Target membership: App AND PlannSpikeWidgets (ActivityKit requires the identical type in both).
import ActivityKit
import Foundation

@available(iOS 16.2, *)
struct PlannAppointmentAttributes: ActivityAttributes {
    public struct ContentState: Codable, Hashable {
        var phase: String              // upcoming | processing | completed | cancelled | removed
        var startEpoch: Double         // seconds since 1970 (not Date: default decoder uses reference date)
        var endEpoch: Double
        var startLabel: String         // stored wall-clock string, e.g. "14:30"
        var endLabel: String
        var customerDisplay: String?
        var serviceName: String
        var staffName: String?
        var version: Int

        var startDate: Date { Date(timeIntervalSince1970: startEpoch) }
        var endDate: Date { Date(timeIntervalSince1970: endEpoch) }
    }

    var appointmentId: String
    var orgId: String
}
