// PHASE 0 SPIKE — throwaway. Extension deployment target is 16.2, so no availability guards needed.
// Minimal UI to observe: countdown → count-up at start with no push, stale rendering,
// which activity the system shows in the Dynamic Island, and which update version landed.
import ActivityKit
import SwiftUI
import WidgetKit

struct AppointmentLiveActivity: Widget {
    var body: some WidgetConfiguration {
        ActivityConfiguration(for: PlannAppointmentAttributes.self) { context in
            LockScreenView(state: context.state, isStale: context.isStale)
                .padding(16)
                .activityBackgroundTint(Color.black)
                .activitySystemActionForegroundColor(Color.white)
                .widgetURL(URL(string: "plannapp://la-spike"))
        } dynamicIsland: { context in
            DynamicIsland {
                DynamicIslandExpandedRegion(.leading) {
                    Text(context.state.customerDisplay ?? context.state.serviceName)
                        .font(.headline)
                        .lineLimit(1)
                }
                DynamicIslandExpandedRegion(.trailing) {
                    Text(context.state.startLabel)
                        .font(.headline)
                        .monospacedDigit()
                }
                DynamicIslandExpandedRegion(.bottom) {
                    HStack {
                        Text(phaseLabel(context.state.phase, isStale: context.isStale))
                        Spacer()
                        Text(context.state.startDate, style: .timer)
                            .monospacedDigit()
                    }
                    .font(.subheadline)
                }
            } compactLeading: {
                Image(systemName: context.state.phase == "processing" ? "scissors" : "clock")
            } compactTrailing: {
                Text(context.state.startDate, style: .timer)
                    .monospacedDigit()
                    .frame(maxWidth: 56)
            } minimal: {
                Image(systemName: context.state.phase == "processing" ? "scissors" : "clock")
            }
            .widgetURL(URL(string: "plannapp://la-spike"))
        }
    }
}

private struct LockScreenView: View {
    let state: PlannAppointmentAttributes.ContentState
    let isStale: Bool

    var body: some View {
        HStack(alignment: .top, spacing: 12) {
            RoundedRectangle(cornerRadius: 2)
                .fill(barColor)
                .frame(width: 4)
            VStack(alignment: .leading, spacing: 4) {
                HStack {
                    Text(state.customerDisplay ?? state.serviceName)
                        .font(.headline)
                    Spacer()
                    Text("\(state.startLabel)–\(state.endLabel)")
                        .font(.subheadline)
                        .monospacedDigit()
                }
                Text(state.serviceName)
                    .font(.subheadline)
                    .foregroundColor(.gray)
                HStack {
                    Text(phaseLabel(state.phase, isStale: isStale))
                        .font(.caption)
                        .bold()
                    Spacer()
                    Text(state.startDate, style: .timer)
                        .font(.caption)
                        .monospacedDigit()
                }
                if state.phase == "processing" && state.endDate > state.startDate {
                    ProgressView(timerInterval: state.startDate...state.endDate, countsDown: false) {
                        EmptyView()
                    } currentValueLabel: {
                        EmptyView()
                    }
                    .tint(.white)
                }
                Text("v\(state.version)")
                    .font(.caption2)
                    .foregroundColor(.gray)
            }
        }
        .foregroundColor(.white)
    }

    private var barColor: Color {
        switch state.phase {
        case "completed": return .green
        case "cancelled": return .red
        default: return .orange
        }
    }
}

private func phaseLabel(_ phase: String, isStale: Bool) -> String {
    if isStale && phase == "upcoming" { return "Başlıyor" }
    if isStale && phase == "processing" { return "Süre doldu" }
    switch phase {
    case "upcoming": return "Başlamasına"
    case "processing": return "İşlemde"
    case "completed": return "Tamamlandı"
    case "cancelled": return "İptal edildi"
    default: return phase
    }
}
