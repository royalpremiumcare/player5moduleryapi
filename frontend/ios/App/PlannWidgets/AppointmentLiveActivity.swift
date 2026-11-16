import ActivityKit
import SwiftUI
import WidgetKit

// Placeholder UI until the real Live Activity views land (Task 4).
@available(iOS 16.2, *)
struct AppointmentLiveActivity: Widget {
    var body: some WidgetConfiguration {
        ActivityConfiguration(for: PlannAppointmentAttributes.self) { context in
            Text(context.state.serviceName)
                .padding()
        } dynamicIsland: { context in
            DynamicIsland {
                DynamicIslandExpandedRegion(.center) {
                    Text(context.state.serviceName)
                }
            } compactLeading: {
                Text("P")
            } compactTrailing: {
                Text("")
            } minimal: {
                Text("P")
            }
        }
    }
}
