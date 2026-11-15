// PHASE 0 SPIKE — throwaway. Extension deployment target is 16.2, so no availability guards needed.
// Visual review build: design option "C · Dev sayaç" on a white card (owner review 2026-11-15).
// Rules carried from Phase 0 findings: terminal phases render NO live timer; compact leading uses the
// PLANN "P" mark instead of a generic clock glyph.
import ActivityKit
import SwiftUI
import WidgetKit

private enum PC {
    static let ink = Color(red: 10 / 255, green: 10 / 255, blue: 11 / 255)           // #0A0A0B
    static let secondary = Color(red: 82 / 255, green: 82 / 255, blue: 91 / 255)     // #52525B
    static let amber = Color(red: 217 / 255, green: 119 / 255, blue: 6 / 255)        // #D97706
    static let amberText = Color(red: 180 / 255, green: 83 / 255, blue: 9 / 255)     // #B45309
    static let amberDot = Color(red: 245 / 255, green: 158 / 255, blue: 11 / 255)    // #F59E0B
    static let green = Color(red: 21 / 255, green: 128 / 255, blue: 61 / 255)        // #15803D
    static let greenSoft = Color(red: 74 / 255, green: 222 / 255, blue: 128 / 255)   // #4ADE80 (on black)
    static let greenBg = Color(red: 220 / 255, green: 252 / 255, blue: 231 / 255)    // #DCFCE7
    static let red = Color(red: 185 / 255, green: 28 / 255, blue: 28 / 255)          // #B91C1C
    static let redSoft = Color(red: 248 / 255, green: 113 / 255, blue: 113 / 255)    // #F87171 (on black)
    static let redBg = Color(red: 254 / 255, green: 226 / 255, blue: 226 / 255)      // #FEE2E2
    static let hairline = Color(red: 241 / 255, green: 238 / 255, blue: 232 / 255)   // #F1EEE8
}

private enum Look { case upcoming, starting, processing, overdue, completed, cancelled }

private func lookFor(_ s: PlannAppointmentAttributes.ContentState, _ stale: Bool) -> Look {
    switch s.phase {
    case "completed": return .completed
    case "cancelled", "removed": return .cancelled
    case "processing": return stale ? .overdue : .processing
    default: return stale ? .starting : .upcoming
    }
}

private func leadRange(_ s: PlannAppointmentAttributes.ContentState) -> ClosedRange<Date> {
    s.startDate.addingTimeInterval(-30 * 60)...s.startDate
}

private func processingRange(_ s: PlannAppointmentAttributes.ContentState) -> ClosedRange<Date> {
    let end = max(s.endDate, s.startDate.addingTimeInterval(60))
    return s.startDate...end
}

private func caption(_ l: Look, _ s: PlannAppointmentAttributes.ContentState) -> String {
    switch l {
    case .upcoming: return "Başlamasına"
    case .starting: return "Başlıyor"
    case .processing: return "İşlemde · geçen"
    case .overdue: return "Bitiş \(s.endLabel)"
    case .completed: return "Bitiş \(s.endLabel)"
    case .cancelled: return "Randevu"
    }
}

private func captionColor(_ l: Look, onDark: Bool) -> Color {
    switch l {
    case .upcoming, .starting: return onDark ? PC.amberDot : PC.amberText
    case .processing: return onDark ? .white : PC.ink
    case .overdue: return onDark ? .gray : PC.secondary
    case .completed: return onDark ? PC.greenSoft : PC.green
    case .cancelled: return onDark ? PC.redSoft : PC.red
    }
}

private func titleLine(_ s: PlannAppointmentAttributes.ContentState) -> String {
    s.customerDisplay ?? s.serviceName
}

private func detailLine(_ s: PlannAppointmentAttributes.ContentState) -> String {
    var parts: [String] = []
    if s.customerDisplay != nil { parts.append(s.serviceName) }
    if let staff = s.staffName, !staff.isEmpty { parts.append(staff) }
    return parts.isEmpty ? "" : " · " + parts.joined(separator: " · ")
}

struct AppointmentLiveActivity: Widget {
    var body: some WidgetConfiguration {
        ActivityConfiguration(for: PlannAppointmentAttributes.self) { context in
            LockScreenView(state: context.state, isStale: context.isStale)
                .padding(16)
                .activityBackgroundTint(Color.white)
                .activitySystemActionForegroundColor(PC.ink)
                .widgetURL(URL(string: "plannapp://la-spike"))
        } dynamicIsland: { context in
            let l = lookFor(context.state, context.isStale)
            return DynamicIsland {
                DynamicIslandExpandedRegion(.leading) {
                    Badge(look: l, state: context.state, ink: .white, markSize: 16)
                        .frame(width: 52, height: 52)
                        .padding(.leading, 4)
                }
                DynamicIslandExpandedRegion(.center) {
                    VStack(alignment: .leading, spacing: 0) {
                        Text(caption(l, context.state))
                            .font(.system(size: 13, weight: .semibold))
                            .foregroundColor(captionColor(l, onDark: true))
                        BigValue(look: l, state: context.state, size: 30, ink: .white)
                    }
                    .frame(maxWidth: .infinity, alignment: .leading)
                }
                DynamicIslandExpandedRegion(.bottom) {
                    HStack(alignment: .firstTextBaseline) {
                        IslandTitle(state: context.state)
                        Spacer(minLength: 8)
                        Text("\(context.state.startLabel)–\(context.state.endLabel)")
                            .font(.system(size: 14, weight: .semibold))
                            .monospacedDigit()
                            .foregroundColor(.gray)
                    }
                    .padding(.top, 4)
                }
            } compactLeading: {
                CompactMark(look: l)
            } compactTrailing: {
                CompactValue(look: l, state: context.state)
            } minimal: {
                Badge(look: l, state: context.state, ink: .white, markSize: 9)
            }
            .widgetURL(URL(string: "plannapp://la-spike"))
        }
    }
}

private struct LockScreenView: View {
    let state: PlannAppointmentAttributes.ContentState
    let isStale: Bool

    var body: some View {
        let l = lookFor(state, isStale)
        let titleColor: Color = (l == .cancelled) ? PC.secondary : PC.ink
        let title: Text = Text(titleLine(state)).font(.system(size: 15, weight: .bold)).foregroundColor(titleColor)
        let detail: Text = Text(detailLine(state)).font(.system(size: 15, weight: .medium)).foregroundColor(PC.secondary)
        VStack(alignment: .leading, spacing: 10) {
            HStack(alignment: .center, spacing: 14) {
                Badge(look: l, state: state, ink: PC.ink, markSize: 20)
                    .frame(width: 60, height: 60)
                VStack(alignment: .leading, spacing: 0) {
                    Text(caption(l, state))
                        .font(.system(size: 14, weight: .semibold))
                        .foregroundColor(captionColor(l, onDark: false))
                    BigValue(look: l, state: state, size: 44, ink: PC.ink)
                }
                Spacer(minLength: 0)
            }
            Rectangle()
                .fill(PC.hairline)
                .frame(height: 1)
            HStack(alignment: .firstTextBaseline) {
                (title + detail)
                    .lineLimit(1)
                Spacer(minLength: 8)
                Text(l == .processing ? "–\(state.endLabel)" : state.startLabel)
                    .font(.system(size: 14, weight: .semibold))
                    .monospacedDigit()
                    .foregroundColor(PC.secondary)
            }
        }
    }
}

private struct IslandTitle: View {
    let state: PlannAppointmentAttributes.ContentState

    var body: some View {
        let title: Text = Text(titleLine(state)).font(.system(size: 15, weight: .bold)).foregroundColor(.white)
        let detail: Text = Text(detailLine(state)).font(.system(size: 15, weight: .medium)).foregroundColor(.gray)
        (title + detail)
            .lineLimit(1)
    }
}

/// The big number (or terminal word). Terminal phases never render a live timer.
private struct BigValue: View {
    let look: Look
    let state: PlannAppointmentAttributes.ContentState
    let size: CGFloat
    let ink: Color

    var body: some View {
        Group {
            switch look {
            case .upcoming, .processing:
                Text(state.startDate, style: .timer)
                    .font(.system(size: size, weight: .heavy))
                    .monospacedDigit()
            case .starting:
                Text(state.startLabel)
                    .font(.system(size: size, weight: .heavy))
                    .monospacedDigit()
            case .overdue:
                Text("Süre doldu")
                    .font(.system(size: size * 0.7, weight: .heavy))
            case .completed:
                Text("Tamamlandı")
                    .font(.system(size: size * 0.75, weight: .heavy))
            case .cancelled:
                Text("İptal edildi")
                    .font(.system(size: size * 0.75, weight: .heavy))
            }
        }
        .foregroundColor(ink)
        .lineLimit(1)
        .minimumScaleFactor(0.6)
        .multilineTextAlignment(.leading)
    }
}

/// Left badge: live ring for upcoming/processing, static symbol for the rest.
private struct Badge: View {
    let look: Look
    let state: PlannAppointmentAttributes.ContentState
    let ink: Color
    let markSize: CGFloat

    var body: some View {
        ZStack {
            switch look {
            case .upcoming:
                ProgressView(timerInterval: leadRange(state), countsDown: false) {
                    EmptyView()
                } currentValueLabel: {
                    EmptyView()
                }
                .progressViewStyle(.circular)
                .tint(PC.amber)
                Text("P")
                    .font(.system(size: markSize, weight: .heavy))
                    .foregroundColor(ink)
            case .processing:
                ProgressView(timerInterval: processingRange(state), countsDown: false) {
                    EmptyView()
                } currentValueLabel: {
                    EmptyView()
                }
                .progressViewStyle(.circular)
                .tint(ink)
                Circle()
                    .fill(PC.amberDot)
                    .frame(width: markSize * 0.7, height: markSize * 0.7)
            case .starting:
                Circle()
                    .stroke(PC.amber, lineWidth: max(2, markSize * 0.25))
                Text("P")
                    .font(.system(size: markSize, weight: .heavy))
                    .foregroundColor(ink)
            case .overdue:
                Circle()
                    .stroke(Color.gray.opacity(0.4), lineWidth: max(2, markSize * 0.25))
                Image(systemName: "hourglass")
                    .font(.system(size: markSize, weight: .semibold))
                    .foregroundColor(.gray)
            case .completed:
                Circle()
                    .fill(PC.greenBg)
                Image(systemName: "checkmark")
                    .font(.system(size: markSize + 4, weight: .bold))
                    .foregroundColor(PC.green)
            case .cancelled:
                Circle()
                    .fill(PC.redBg)
                Image(systemName: "xmark")
                    .font(.system(size: markSize + 2, weight: .bold))
                    .foregroundColor(PC.red)
            }
        }
    }
}

private struct CompactMark: View {
    let look: Look

    var body: some View {
        ZStack {
            switch look {
            case .completed:
                Image(systemName: "checkmark.circle.fill")
                    .foregroundColor(PC.greenSoft)
            case .cancelled:
                Image(systemName: "xmark.circle.fill")
                    .foregroundColor(PC.redSoft)
            case .processing:
                Circle()
                    .fill(PC.amberDot)
                    .frame(width: 22, height: 22)
                Text("P")
                    .font(.system(size: 12, weight: .heavy))
                    .foregroundColor(.black)
            default:
                Circle()
                    .stroke(PC.amberDot, lineWidth: 2)
                    .frame(width: 21, height: 21)
                Text("P")
                    .font(.system(size: 12, weight: .heavy))
                    .foregroundColor(.white)
            }
        }
    }
}

private struct CompactValue: View {
    let look: Look
    let state: PlannAppointmentAttributes.ContentState

    var body: some View {
        Group {
            switch look {
            case .upcoming, .processing:
                Text(state.startDate, style: .timer)
                    .monospacedDigit()
                    .foregroundColor(PC.amberDot)
            case .starting:
                Text(state.startLabel)
                    .monospacedDigit()
                    .foregroundColor(PC.amberDot)
            case .overdue:
                Text(state.endLabel)
                    .monospacedDigit()
                    .foregroundColor(.gray)
            case .completed:
                Text("Bitti")
                    .foregroundColor(PC.greenSoft)
            case .cancelled:
                Text("İptal")
                    .foregroundColor(PC.redSoft)
            }
        }
        .font(.system(size: 15, weight: .semibold))
        .multilineTextAlignment(.trailing)
        .frame(maxWidth: 56)
    }
}
