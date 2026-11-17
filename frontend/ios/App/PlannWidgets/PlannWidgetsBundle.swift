import SwiftUI
import WidgetKit

@main
struct PlannWidgetsBundle: WidgetBundle {
    var body: some Widget {
        TodayWidget()
        AppointmentLiveActivity() // the extension's deployment target is iOS 16.2
    }
}
