// PHASE 0 SPIKE — throwaway. Extension deployment target is 16.2, so no availability guards needed.
// Visual review build: the "first white version" (owner choice 2026-11-15, after option C was too large):
// white card, 4 pt status bar on the left, name + time first, compact timer row, thin progress bar.
// Rules carried from Phase 0 findings: terminal phases render NO live timer; compact leading uses the
// PLANN "P" mark instead of a generic clock glyph.
import ActivityKit
import SwiftUI
import WidgetKit

private enum PC {
    static let ink = Color(red: 10 / 255, green: 10 / 255, blue: 11 / 255)           // #0A0A0B
    static let secondary = Color(red: 82 / 255, green: 82 / 255, blue: 91 / 255)     // #52525B
    static let muted = Color(red: 113 / 255, green: 113 / 255, blue: 122 / 255)      // #71717A
    static let amberBar = Color(red: 217 / 255, green: 119 / 255, blue: 6 / 255)     // #D97706
    static let amberText = Color(red: 180 / 255, green: 83 / 255, blue: 9 / 255)    // #B45309
    static let amberDot = Color(red: 245 / 255, green: 158 / 255, blue: 11 / 255)    // #F59E0B
    static let greenBar = Color(red: 22 / 255, green: 163 / 255, blue: 74 / 255)     // #16A34A
    static let greenText = Color(red: 21 / 255, green: 128 / 255, blue: 61 / 255)    // #15803D
    static let greenSoft = Color(red: 74 / 255, green: 222 / 255, blue: 128 / 255)   // #4ADE80 (on black)
    static let redBar = Color(red: 220 / 255, green: 38 / 255, blue: 38 / 255)       // #DC2626
    static let redText = Color(red: 185 / 255, green: 28 / 255, blue: 28 / 255)      // #B91C1C
    static let redSoft = Color(red: 248 / 255, green: 113 / 255, blue: 113 / 255)    // #F87171 (on black)
    static let track = Color(red: 237 / 255, green: 235 / 255, blue: 230 / 255)      // #EDEBE6
    static let trackDone = Color(red: 214 / 255, green: 211 / 255, blue: 206 / 255)  // #D6D3CE
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

private func barColor(_ l: Look) -> Color {
    switch l {
    case .upcoming, .starting, .processing: return PC.amberBar
    case .overdue: return PC.muted
    case .completed: return PC.greenBar
    case .cancelled: return PC.redBar
    }
}

private func titleLine(_ s: PlannAppointmentAttributes.ContentState) -> String {
    s.customerDisplay ?? s.serviceName
}

private func firstName(_ s: PlannAppointmentAttributes.ContentState) -> String {
    let t = titleLine(s)
    return t.split(separator: " ").first.map(String.init) ?? t
}

private func serviceLine(_ s: PlannAppointmentAttributes.ContentState) -> String {
    var parts: [String] = []
    if s.customerDisplay != nil { parts.append(s.serviceName) }
    if let staff = s.staffName, !staff.isEmpty { parts.append(staff) }
    return parts.joined(separator: " · ")
}

struct AppointmentLiveActivity: Widget {
    var body: some WidgetConfiguration {
        ActivityConfiguration(for: PlannAppointmentAttributes.self) { context in
            LockScreenCard(state: context.state, isStale: context.isStale)
                .padding(.leading, 14)
                .padding(.trailing, 16)
                .padding(.vertical, 12)
                .activityBackgroundTint(Color.white)
                .activitySystemActionForegroundColor(PC.ink)
                .widgetURL(URL(string: "plannapp://la-spike"))
        } dynamicIsland: { context in
            let l = lookFor(context.state, context.isStale)
            return DynamicIsland {
                DynamicIslandExpandedRegion(.leading) {
                    HStack(spacing: 10) {
                        IslandMark(look: l, size: 30)
                        Text(titleLine(context.state))
                            .font(.system(size: 17, weight: .bold))
                            .foregroundColor(.white)
                            .lineLimit(1)
                    }
                    .padding(.leading, 4)
                }
                DynamicIslandExpandedRegion(.trailing) {
                    Text("\(context.state.startLabel)–\(context.state.endLabel)")
                        .font(.system(size: 15, weight: .semibold))
                        .monospacedDigit()
                        .foregroundColor(.white)
                        .padding(.trailing, 4)
                }
                DynamicIslandExpandedRegion(.bottom) {
                    VStack(alignment: .leading, spacing: 6) {
                        Text(serviceLine(context.state))
                            .font(.system(size: 14))
                            .foregroundColor(.gray)
                            .lineLimit(1)
                        TimerRow(look: l, state: context.state, onDark: true, valueSize: 24)
                        ProgressLine(look: l, state: context.state, onDark: true)
                    }
                    .padding(.horizontal, 4)
                }
            } compactLeading: {
                HStack(spacing: 6) {
                    IslandMark(look: l, size: 21)
                    Text(firstName(context.state))
                        .font(.system(size: 14, weight: .semibold))
                        .foregroundColor(.white)
                        .lineLimit(1)
                }
            } compactTrailing: {
                CompactValue(look: l, state: context.state)
            } minimal: {
                IslandMark(look: l, size: 21)
            }
            .widgetURL(URL(string: "plannapp://la-spike"))
        }
    }
}

// MARK: - Lock Screen card

private struct LockScreenCard: View {
    let state: PlannAppointmentAttributes.ContentState
    let isStale: Bool

    var body: some View {
        let l = lookFor(state, isStale)
        HStack(alignment: .top, spacing: 12) {
            RoundedRectangle(cornerRadius: 3)
                .fill(barColor(l))
                .frame(width: l == .processing ? 6 : 4)
            VStack(alignment: .leading, spacing: 4) {
                NameRow(look: l, state: state)
                SubRow(look: l, state: state)
                switch l {
                case .completed:
                    FinalRow(symbol: "checkmark.circle", color: PC.greenText,
                             text: "Tamamlandı · \(state.endLabel)")
                case .cancelled:
                    FinalRow(symbol: "xmark.circle", color: PC.redText, text: "Randevu iptal edildi")
                default:
                    CompactTimerRow(look: l, state: state)
                        .padding(.top, 2)
                }
            }
        }
    }
}

private struct NameRow: View {
    let look: Look
    let state: PlannAppointmentAttributes.ContentState

    var body: some View {
        let cancelled = (look == .cancelled)
        let nameColor: Color = cancelled ? PC.secondary : PC.ink
        HStack(alignment: .center, spacing: 8) {
            Text(titleLine(state))
                .font(.system(size: 17, weight: .bold))
                .strikethrough(cancelled)
                .foregroundColor(nameColor)
                .lineLimit(1)
            Spacer(minLength: 4)
            StatusLabel(look: look)
        }
    }
}

/// Second line: service · staff on the left, time range on the right.
private struct SubRow: View {
    let look: Look
    let state: PlannAppointmentAttributes.ContentState

    var body: some View {
        let cancelled = (look == .cancelled)
        HStack(alignment: .firstTextBaseline, spacing: 8) {
            Text(serviceLine(state))
                .font(.system(size: 13))
                .foregroundColor(PC.secondary)
                .lineLimit(1)
            Spacer(minLength: 4)
            Text("\(state.startLabel)–\(state.endLabel)")
                .font(.system(size: 13, weight: .semibold))
                .monospacedDigit()
                .strikethrough(cancelled)
                .foregroundColor(PC.secondary)
        }
    }
}

/// Third line: "Başlamasına 12:41" then the progress bar filling the rest of the row.
private struct CompactTimerRow: View {
    let look: Look
    let state: PlannAppointmentAttributes.ContentState

    var body: some View {
        let labelColor: Color = (look == .overdue) ? PC.secondary : PC.amberText
        HStack(alignment: .center, spacing: 8) {
            Text(label)
                .font(.system(size: 13, weight: .semibold))
                .foregroundColor(labelColor)
                .lineLimit(1)
                .fixedSize()
            value
                .font(.system(size: 20, weight: .bold))
                .monospacedDigit()
                .foregroundColor(PC.ink)
                .lineLimit(1)
                .frame(width: 74, alignment: .leading)
            ProgressLine(look: look, state: state, onDark: false)
                .frame(maxWidth: .infinity)
        }
    }

    private var label: String {
        switch look {
        case .upcoming: return "Başlamasına kalan"
        case .starting: return "Başlıyor ·"
        case .processing: return "Bitmesine kalan"
        case .overdue: return "Süre doldu ·"
        default: return ""
        }
    }

    private var value: Text {
        switch look {
        case .upcoming: return Text(state.startDate, style: .timer)
        case .processing: return Text(state.endDate, style: .timer)
        case .starting: return Text(state.startLabel)
        default: return Text(state.endLabel)
        }
    }
}

private struct StatusLabel: View {
    let look: Look

    var body: some View {
        switch look {
        case .upcoming, .starting:
            Text("Sıradaki")
                .font(.system(size: 12, weight: .semibold))
                .foregroundColor(PC.amberText)
        case .processing:
            HStack(spacing: 5) {
                Circle()
                    .fill(PC.greenSoft)
                    .frame(width: 6, height: 6)
                Text("İşlemde")
                    .font(.system(size: 12, weight: .semibold))
                    .foregroundColor(.white)
            }
            .padding(.horizontal, 9)
            .padding(.vertical, 3)
            .background(Capsule().fill(PC.ink))
        case .overdue:
            Text("Süre doldu")
                .font(.system(size: 12, weight: .semibold))
                .foregroundColor(PC.secondary)
        case .completed:
            HStack(spacing: 4) {
                Image(systemName: "checkmark")
                    .font(.system(size: 10, weight: .bold))
                Text("Tamamlandı")
                    .font(.system(size: 12, weight: .semibold))
            }
            .foregroundColor(PC.greenText)
        case .cancelled:
            Text("İptal edildi")
                .font(.system(size: 12, weight: .semibold))
                .foregroundColor(PC.redText)
        }
    }
}

private struct FinalRow: View {
    let symbol: String
    let color: Color
    let text: String

    var body: some View {
        HStack(spacing: 6) {
            Image(systemName: symbol)
                .font(.system(size: 16, weight: .semibold))
                .foregroundColor(color)
            Text(text)
                .font(.system(size: 15, weight: .semibold))
                .foregroundColor(PC.ink)
                .lineLimit(1)
        }
        .padding(.top, 2)
    }
}

/// Label on the left, value on the right. Only upcoming/processing render a live timer.
private struct TimerRow: View {
    let look: Look
    let state: PlannAppointmentAttributes.ContentState
    let onDark: Bool
    let valueSize: CGFloat

    var body: some View {
        let labelColor: Color = (look == .overdue) ? (onDark ? .gray : PC.secondary) : (onDark ? PC.amberDot : PC.amberText)
        let valueColor: Color = onDark ? .white : PC.ink
        HStack(alignment: .firstTextBaseline) {
            Text(label)
                .font(.system(size: 13, weight: .semibold))
                .foregroundColor(labelColor)
            Spacer(minLength: 8)
            value
                .font(.system(size: valueSize, weight: .bold))
                .monospacedDigit()
                .foregroundColor(valueColor)
                .multilineTextAlignment(.trailing)
                .lineLimit(1)
        }
    }

    private var label: String {
        switch look {
        case .upcoming: return "Başlamasına kalan"
        case .starting: return "Başlıyor ·"
        case .processing: return "Bitmesine kalan"
        case .overdue: return "Süre doldu ·"
        case .completed: return "Tamamlandı"
        case .cancelled: return "İptal edildi"
        }
    }

    private var value: Text {
        switch look {
        case .upcoming: return Text(state.startDate, style: .timer)
        case .processing: return Text(state.endDate, style: .timer)
        case .starting: return Text(state.startLabel)
        case .overdue, .completed: return Text(state.endLabel)
        case .cancelled: return Text("")
        }
    }
}

private struct ProgressLine: View {
    let look: Look
    let state: PlannAppointmentAttributes.ContentState
    let onDark: Bool

    var body: some View {
        switch look {
        case .upcoming:
            ProgressView(timerInterval: leadRange(state), countsDown: false) {
                EmptyView()
            } currentValueLabel: {
                EmptyView()
            }
            .tint(onDark ? PC.amberDot : PC.amberBar)
        case .processing:
            ProgressView(timerInterval: processingRange(state), countsDown: false) {
                EmptyView()
            } currentValueLabel: {
                EmptyView()
            }
            .tint(onDark ? PC.greenSoft : PC.greenBar)
        case .starting:
            Capsule()
                .fill(onDark ? PC.amberDot : PC.amberBar)
                .frame(height: 4)
        default:
            Capsule()
                .fill(onDark ? Color.gray.opacity(0.5) : PC.trackDone)
                .frame(height: 4)
        }
    }
}

// MARK: - Dynamic Island pieces (always on black)

private struct IslandMark: View {
    let look: Look
    let size: CGFloat

    var body: some View {
        ZStack {
            switch look {
            case .completed:
                Image(systemName: "checkmark.circle.fill")
                    .font(.system(size: size * 0.9))
                    .foregroundColor(PC.greenSoft)
            case .cancelled:
                Image(systemName: "xmark.circle.fill")
                    .font(.system(size: size * 0.9))
                    .foregroundColor(PC.redSoft)
            case .processing:
                Circle()
                    .fill(PC.amberDot)
                Text("P")
                    .font(.system(size: size * 0.5, weight: .heavy))
                    .foregroundColor(.black)
            case .overdue:
                Circle()
                    .stroke(Color.gray, lineWidth: 2)
                Text("P")
                    .font(.system(size: size * 0.5, weight: .heavy))
                    .foregroundColor(.gray)
            default:
                Circle()
                    .stroke(PC.amberDot, lineWidth: 2)
                Text("P")
                    .font(.system(size: size * 0.5, weight: .heavy))
                    .foregroundColor(.white)
            }
        }
        .frame(width: size, height: size)
    }
}

private struct CompactValue: View {
    let look: Look
    let state: PlannAppointmentAttributes.ContentState

    var body: some View {
        Group {
            switch look {
            case .upcoming:
                Text(state.startDate, style: .timer)
                    .monospacedDigit()
                    .foregroundColor(PC.amberDot)
            case .processing:
                Text(state.endDate, style: .timer)
                    .monospacedDigit()
                    .foregroundColor(PC.greenSoft)
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
