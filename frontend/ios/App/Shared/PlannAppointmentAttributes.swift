import ActivityKit
import Foundation

// Compiled into both the App and PlannWidgets targets. PlannContentState comes from
// LiveActivityCore/ContentModel.swift, which is also compiled into both targets
// (file reference, not a module: no `import LiveActivityCore`).
@available(iOS 16.2, *)
struct PlannAppointmentAttributes: ActivityAttributes {
    typealias ContentState = PlannContentState

    let slotId: String
    let orgId: String
}
