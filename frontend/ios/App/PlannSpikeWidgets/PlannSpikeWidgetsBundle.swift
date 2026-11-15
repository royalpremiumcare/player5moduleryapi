// PHASE 0 SPIKE — throwaway. Widget extension entry point (Live Activity only).
import SwiftUI
import WidgetKit

@main
struct PlannSpikeWidgetsBundle: WidgetBundle {
    var body: some Widget {
        AppointmentLiveActivity()
    }
}
