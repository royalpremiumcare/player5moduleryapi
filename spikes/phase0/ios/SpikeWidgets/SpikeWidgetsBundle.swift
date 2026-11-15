// PHASE 0 SPIKE — throwaway. Replace the template's @main bundle with this one.
import SwiftUI
import WidgetKit

@main
struct SpikeWidgetsBundle: WidgetBundle {
    var body: some Widget {
        if #available(iOS 16.2, *) {
            AppointmentLiveActivity()
        }
    }
}
