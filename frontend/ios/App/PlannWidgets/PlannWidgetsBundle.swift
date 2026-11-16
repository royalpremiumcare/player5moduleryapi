import SwiftUI
import WidgetKit

@main
struct PlannWidgetsBundle: WidgetBundle {
    var body: some Widget {
        if #available(iOS 16.2, *) {
            AppointmentLiveActivity()
        }
    }
}
