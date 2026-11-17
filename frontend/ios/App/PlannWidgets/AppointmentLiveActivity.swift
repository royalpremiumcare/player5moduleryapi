// Slot Live Activity UI: Lock Screen card and Dynamic Island (design 3: ring with a state symbol, big countdown).
// The card sits on the system Lock Screen material (no background tint). One accent per state, derived only from Look.
// Terminal and stale phases render no live timer.
// The extension deploys at iOS 16.2; the only newer API (numeric content transition) is behind #available(iOS 17.0, *).
import ActivityKit
import SwiftUI
import WidgetKit

private enum Look { case upcoming, starting, processing, overdue, completed, cancelled, empty }

private func lookFor(_ s: PlannAppointmentAttributes.ContentState, _ stale: Bool) -> Look {
    switch s.phase {
    case .completed: return .completed
    case .cancelled: return .cancelled
    case .removed, .unknown: return .empty
    case .processing: return stale ? .overdue : .processing
    case .upcoming: return stale ? .starting : .upcoming
    }
}

private func leadRange(_ s: PlannAppointmentAttributes.ContentState) -> ClosedRange<Date> {
    s.startDate.addingTimeInterval(-30 * 60)...s.startDate
}

private func processingRange(_ s: PlannAppointmentAttributes.ContentState) -> ClosedRange<Date> {
    let end = max(s.endDate, s.startDate.addingTimeInterval(60))
    return s.startDate...end
}

/// Range for the countdown text. Only the upper bound sets what it shows (time left until it);
/// the lower bound sits 12 h back so an activity started earlier than the ring window still counts live.
private func countdownRange(to end: Date) -> ClosedRange<Date> {
    end.addingTimeInterval(-12 * 3600)...end
}

/// The single accent for a state. Nothing else carries colour, so no colour outlives a state change.
private func accent(_ l: Look) -> Color {
    switch l {
    case .upcoming, .starting: return Color.orange
    case .processing, .overdue, .completed: return Color.green
    case .cancelled: return Color.secondary
    case .empty: return Color.clear
    }
}

private func badgeText(_ l: Look) -> String {
    switch l {
    case .upcoming: return "Sıradaki"
    case .starting: return "Başlıyor"
    case .processing: return "İşlemde"
    case .overdue: return "Süre doldu"
    case .completed: return "Tamamlandı"
    case .cancelled: return "İptal edildi"
    case .empty: return ""
    }
}

private func symbolName(_ l: Look) -> String {
    switch l {
    case .upcoming, .starting: return "clock"
    case .processing, .overdue: return "scissors"
    case .completed: return "checkmark"
    case .cancelled, .empty: return "xmark"
    }
}

/// Small line under the hero value; nil when the hero itself already says it (stale states).
private func heroCaption(_ l: Look) -> String? {
    switch l {
    case .upcoming: return "Başlamasına kalan"
    case .processing: return "Bitmesine kalan"
    case .completed: return "Bitiş saati"
    case .cancelled: return "İptal edildi"
    case .starting, .overdue, .empty: return nil
    }
}

private func titleLine(_ s: PlannAppointmentAttributes.ContentState) -> String {
    s.customerDisplay ?? s.serviceName
}

private func serviceLine(_ s: PlannAppointmentAttributes.ContentState) -> String {
    var parts: [String] = []
    if s.customerDisplay != nil { parts.append(s.serviceName) }
    if let staff = s.staffName, !staff.isEmpty { parts.append(staff) }
    return parts.joined(separator: " · ")
}

private func rangeLine(_ s: PlannAppointmentAttributes.ContentState) -> String {
    "\(s.startLabel)–\(s.endLabel)"
}

private func deepLink(_ s: PlannAppointmentAttributes.ContentState) -> URL? {
    URL(string: s.appointmentId.isEmpty ? "plannapp://" : "plannapp://appointment/\(s.appointmentId)")
}

@available(iOS 16.2, *)
struct AppointmentLiveActivity: Widget {
    var body: some WidgetConfiguration {
        ActivityConfiguration(for: PlannAppointmentAttributes.self) { context in
            // Background tint left unset (nil): the system Lock Screen material stays underneath.
            LockScreenCard(state: context.state, isStale: context.isStale)
                .padding(.horizontal, 16)
                .padding(.vertical, 14)
                .widgetURL(deepLink(context.state))
        } dynamicIsland: { context in
            let l = lookFor(context.state, context.isStale)
            return DynamicIsland {
                DynamicIslandExpandedRegion(.leading) {
                    if l != .empty {
                        StatusRing(look: l, state: context.state, size: 40, lineWidth: 4, symbolSize: 17)
                            .padding(.leading, 4)
                    }
                }
                DynamicIslandExpandedRegion(.trailing) {
                    if l != .empty {
                        HeroValue(look: l, state: context.state, valueSize: 24, timerWidth: 70, alignment: .trailing)
                            .padding(.trailing, 4)
                    }
                }
                DynamicIslandExpandedRegion(.bottom) {
                    if l != .empty {
                        VStack(alignment: .leading, spacing: 3) {
                            Text(titleLine(context.state))
                                .font(.system(size: 17, weight: .semibold))
                                .foregroundColor(.primary)
                                .lineLimit(1)
                            HStack(spacing: 8) {
                                Text(serviceLine(context.state))
                                    .font(.system(size: 14))
                                    .foregroundColor(.secondary)
                                    .lineLimit(1)
                                Spacer(minLength: 4)
                                Text(rangeLine(context.state))
                                    .font(.system(size: 13, weight: .semibold))
                                    .monospacedDigit()
                                    .foregroundColor(.secondary)
                                    .lineLimit(1)
                            }
                        }
                        .padding(.horizontal, 4)
                    }
                }
            } compactLeading: {
                if l != .empty {
                    IslandIndicator(look: l, state: context.state)
                }
            } compactTrailing: {
                CompactValue(look: l, state: context.state)
            } minimal: {
                if l != .empty {
                    StatusRing(look: l, state: context.state, size: 20, lineWidth: 3, symbolSize: nil)
                }
            }
            .keylineTint(accent(l))
            .widgetURL(deepLink(context.state))
        }
    }
}

// MARK: - Lock Screen card

private struct LockScreenCard: View {
    let state: PlannAppointmentAttributes.ContentState
    let isStale: Bool

    var body: some View {
        let l = lookFor(state, isStale)
        if l == .empty {
            Color.clear
        } else {
            VStack(alignment: .leading, spacing: 9) {
                HStack(alignment: .center, spacing: 8) {
                    Text(titleLine(state))
                        .font(.system(size: 17, weight: .semibold))
                        .foregroundColor(.primary)
                        .lineLimit(1)
                    Spacer(minLength: 8)
                    StatusBadge(look: l)
                }
                HStack(alignment: .center, spacing: 12) {
                    StatusRing(look: l, state: state, size: 46, lineWidth: 4, symbolSize: 20)
                    HeroValue(look: l, state: state, valueSize: 30, timerWidth: 84, alignment: .leading)
                        .layoutPriority(1)
                    MetaBlock(state: state)
                }
            }
        }
    }
}

/// Coloured dot plus `.primary` text; colour lives only in the dot.
private struct StatusBadge: View {
    let look: Look

    var body: some View {
        HStack(spacing: 6) {
            Circle()
                .fill(accent(look))
                .frame(width: 8, height: 8)
            Text(badgeText(look))
                .font(.system(size: 13, weight: .semibold))
                .foregroundColor(.primary)
                .lineLimit(1)
        }
        .fixedSize()
    }
}

/// Service line and time range, right-aligned in secondary.
private struct MetaBlock: View {
    let state: PlannAppointmentAttributes.ContentState

    var body: some View {
        let service = serviceLine(state)
        VStack(alignment: .trailing, spacing: 3) {
            if !service.isEmpty {
                Text(service)
                    .font(.system(size: 15))
                    .foregroundColor(.secondary)
                    .multilineTextAlignment(.trailing)
                    .lineLimit(1)
            }
            Text(rangeLine(state))
                .font(.system(size: 13, weight: .semibold))
                .monospacedDigit()
                .foregroundColor(.secondary)
                .multilineTextAlignment(.trailing)
                .lineLimit(1)
        }
        .frame(maxWidth: .infinity, alignment: .trailing)
    }
}

// MARK: - Shared pieces

/// The ring. Live looks (upcoming, processing) use the system circular timer ProgressView, which
/// drains on its own; every other look draws a static full ring with no timer.
/// Kept in this one view so it can be swapped (e.g. for a linear bar) if the circular style
/// renders badly on a device.
private struct StatusRing: View {
    let look: Look
    let state: PlannAppointmentAttributes.ContentState
    let size: CGFloat
    let lineWidth: CGFloat
    /// nil draws the ring without the state symbol (minimal island).
    let symbolSize: CGFloat?

    var body: some View {
        let tint = accent(look)
        ZStack {
            switch look {
            case .upcoming:
                ProgressView(timerInterval: leadRange(state), countsDown: true) {
                    EmptyView()
                } currentValueLabel: {
                    EmptyView()
                }
                .progressViewStyle(.circular)
                .tint(tint)
            case .processing:
                ProgressView(timerInterval: processingRange(state), countsDown: true) {
                    EmptyView()
                } currentValueLabel: {
                    EmptyView()
                }
                .progressViewStyle(.circular)
                .tint(tint)
            default:
                Circle()
                    .stroke(tint, lineWidth: lineWidth)
                    .padding(lineWidth / 2)
            }
            if let symbolSize = symbolSize {
                Image(systemName: symbolName(look))
                    .font(.system(size: symbolSize, weight: .semibold))
                    .foregroundStyle(tint)
            }
        }
        .frame(width: size, height: size)
    }
}

/// Big value with its caption: a live countdown for upcoming/processing, otherwise a static label.
private struct HeroValue: View {
    let look: Look
    let state: PlannAppointmentAttributes.ContentState
    let valueSize: CGFloat
    /// Fixed width for the live timer, which would otherwise expand to fill the row.
    let timerWidth: CGFloat
    let alignment: HorizontalAlignment

    var body: some View {
        VStack(alignment: alignment, spacing: 4) {
            value
            if let caption = heroCaption(look) {
                Text(caption)
                    .font(.caption)
                    .foregroundColor(.secondary)
                    .lineLimit(1)
                    .fixedSize()
            }
        }
    }

    @ViewBuilder
    private var value: some View {
        switch look {
        case .upcoming:
            CountdownText(end: state.startDate, size: valueSize, width: timerWidth, alignment: alignment,
                          color: .primary)
        case .processing:
            CountdownText(end: state.endDate, size: valueSize, width: timerWidth, alignment: alignment,
                          color: .primary)
        case .starting, .overdue, .completed:
            StaticValue(text: staticText, size: valueSize, color: .primary)
        case .cancelled:
            StaticValue(text: state.startLabel, size: valueSize, color: .secondary)
        case .empty:
            EmptyView()
        }
    }

    private var staticText: String {
        switch look {
        case .starting: return "Başlıyor"
        case .overdue: return "Süre doldu"
        default: return state.endLabel
        }
    }
}

private struct CountdownText: View {
    let end: Date
    let size: CGFloat
    let width: CGFloat
    let alignment: HorizontalAlignment
    let color: Color

    var body: some View {
        Text(timerInterval: countdownRange(to: end), countsDown: true)
            .font(.system(size: size, weight: .bold, design: .rounded))
            .monospacedDigit()
            .foregroundColor(color)
            .lineLimit(1)
            .minimumScaleFactor(0.6)
            .multilineTextAlignment(alignment == .trailing ? .trailing : .leading)
            .frame(width: width, alignment: Alignment(horizontal: alignment, vertical: .center))
            .numericCountdownTransition()
    }
}

private struct StaticValue: View {
    let text: String
    let size: CGFloat
    let color: Color

    var body: some View {
        Text(text)
            .font(.system(size: size, weight: .bold, design: .rounded))
            .monospacedDigit()
            .foregroundColor(color)
            .lineLimit(1)
            .minimumScaleFactor(0.6)
    }
}

private extension View {
    /// Rolling digits where the system supports it; earlier versions just change the digits in place.
    @ViewBuilder
    func numericCountdownTransition() -> some View {
        if #available(iOS 17.0, *) {
            self.contentTransition(.numericText(countsDown: true))
        } else {
            self
        }
    }
}

// MARK: - Dynamic Island compact pieces (system black background)

/// Compact leading: the live ring for upcoming/processing, otherwise the state symbol.
private struct IslandIndicator: View {
    let look: Look
    let state: PlannAppointmentAttributes.ContentState

    var body: some View {
        switch look {
        case .upcoming, .processing:
            StatusRing(look: look, state: state, size: 20, lineWidth: 3, symbolSize: nil)
        default:
            Image(systemName: symbolName(look))
                .font(.system(size: 14, weight: .semibold))
                .foregroundStyle(accent(look))
                .frame(width: 20, height: 20)
        }
    }
}

private struct CompactValue: View {
    let look: Look
    let state: PlannAppointmentAttributes.ContentState

    var body: some View {
        let tint = accent(look)
        switch look {
        case .upcoming:
            CountdownText(end: state.startDate, size: 15, width: 48, alignment: .trailing, color: tint)
        case .processing:
            CountdownText(end: state.endDate, size: 15, width: 48, alignment: .trailing, color: tint)
        case .starting, .cancelled:
            CompactLabel(text: state.startLabel, color: tint)
        case .overdue, .completed:
            CompactLabel(text: state.endLabel, color: tint)
        case .empty:
            EmptyView()
        }
    }
}

private struct CompactLabel: View {
    let text: String
    let color: Color

    var body: some View {
        Text(text)
            .font(.system(size: 15, weight: .semibold, design: .rounded))
            .monospacedDigit()
            .foregroundColor(color)
            .lineLimit(1)
            .minimumScaleFactor(0.7)
            .frame(maxWidth: 48, alignment: .trailing)
    }
}
