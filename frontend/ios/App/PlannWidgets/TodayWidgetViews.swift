// Today widget views per family (spec §5.4 as amended by §7A.1).
// Same language as the Live Activity card: premium white surface (near-black in dark mode),
// amber for upcoming, green for processing, zinc text, no strikethrough.
// Only iOS 17+ API used here: containerBackground(for:), guarded by #available with an iOS 16 fallback.
import SwiftUI
import WidgetKit

// MARK: - Palette (one place to restyle)

struct TodayPalette {
    let surface: Color
    let ink: Color
    let secondary: Color
    let muted: Color
    let amber: Color      // upcoming accent
    let green: Color      // processing accent
    let hairline: Color

    init(_ scheme: ColorScheme) {
        if scheme == .dark {
            surface = Color(red: 24 / 255, green: 24 / 255, blue: 27 / 255)      // #18181B
            ink = Color(red: 250 / 255, green: 250 / 255, blue: 250 / 255)       // #FAFAFA
            secondary = Color(red: 161 / 255, green: 161 / 255, blue: 170 / 255) // #A1A1AA
            muted = Color(red: 113 / 255, green: 113 / 255, blue: 122 / 255)     // #71717A
            amber = Color(red: 245 / 255, green: 158 / 255, blue: 11 / 255)      // #F59E0B
            green = Color(red: 74 / 255, green: 222 / 255, blue: 128 / 255)      // #4ADE80
            hairline = Color(red: 39 / 255, green: 39 / 255, blue: 42 / 255)     // #27272A
        } else {
            surface = Color.white
            ink = Color(red: 10 / 255, green: 10 / 255, blue: 11 / 255)          // #0A0A0B
            secondary = Color(red: 82 / 255, green: 82 / 255, blue: 91 / 255)    // #52525B
            muted = Color(red: 113 / 255, green: 113 / 255, blue: 122 / 255)     // #71717A
            amber = Color(red: 217 / 255, green: 119 / 255, blue: 6 / 255)       // #D97706
            green = Color(red: 22 / 255, green: 163 / 255, blue: 74 / 255)       // #16A34A
            hairline = Color(red: 237 / 255, green: 235 / 255, blue: 230 / 255)  // #EDEBE6
        }
    }

    func accent(_ phase: PlannPhase) -> Color { phase == .processing ? green : amber }
}

// MARK: - Background (iOS 17 containerBackground, iOS 16 fallback)

private extension View {
    /// iOS 17+ needs containerBackground (the system then adds the content margins);
    /// iOS 16 gets the same colour as a plain background plus our own padding.
    @ViewBuilder
    func todaySurface(_ color: Color, padding: CGFloat) -> some View {
        if #available(iOS 17.0, *) {
            self.containerBackground(for: .widget) { color }
        } else {
            self.padding(padding)
                .frame(maxWidth: .infinity, maxHeight: .infinity)
                .background(color)
        }
    }
}

// MARK: - Entry view

struct TodayWidgetView: View {
    let entry: TodayEntry
    @Environment(\.widgetFamily) private var family
    @Environment(\.colorScheme) private var scheme

    var body: some View {
        let p = TodayPalette(scheme)
        switch family {
        case .accessoryRectangular:
            LockRectangularView(entry: entry)
                .todaySurface(Color.clear, padding: 0)
                .widgetURL(isSignedOut(entry) ? nil : quickAddURL(.rectangular))
        case .accessoryCircular:
            LockCircularView(entry: entry)
                .todaySurface(Color.clear, padding: 0)
                .widgetURL(isSignedOut(entry) ? nil : quickAddURL(.circular))
        case .systemMedium:
            HomeView(entry: entry, kind: .medium, palette: p)
                .todaySurface(p.surface, padding: 16)
        case .systemLarge:
            HomeView(entry: entry, kind: .large, palette: p)
                .todaySurface(p.surface, padding: 16)
        default:
            HomeView(entry: entry, kind: .small, palette: p)
                .todaySurface(p.surface, padding: 16)
                .widgetURL(isSignedOut(entry) ? nil : quickAddURL(.small))
        }
    }
}

private func isSignedOut(_ entry: TodayEntry) -> Bool {
    if case .signedOut = entry.content { return true }
    return false
}

// MARK: - Home Screen

private struct HomeView: View {
    let entry: TodayEntry
    let kind: WidgetFamilyKind
    let palette: TodayPalette

    var body: some View {
        switch entry.content {
        case .signedOut:
            SignedOutView(palette: palette, compact: kind == .small)
        case .unreachable:
            UnreachableView(kind: kind, palette: palette)
        case .summary(let summary):
            let day = widgetDay(summary, at: entry.date)
            let stale = summary.generatedAtDate.flatMap { staleLabel(generatedAt: $0, now: entry.date, tz: .current) }
            switch kind {
            case .medium:
                MediumView(summary: summary, day: day, stale: stale, palette: palette)
            case .large:
                LargeView(summary: summary, day: day, stale: stale, palette: palette)
            default:
                SmallView(summary: summary, day: day, stale: stale, palette: palette)
            }
        }
    }
}

private struct SmallView: View {
    let summary: WidgetSummary
    let day: WidgetDay
    let stale: String?
    let palette: TodayPalette

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            HStack(alignment: .top) {
                Text(WidgetCopy.today)
                    .font(.system(size: 13, weight: .semibold))
                    .foregroundColor(palette.secondary)
                Spacer(minLength: 4)
                PlusBadge(palette: palette)
            }
            Text("\(day.counts.remaining)")
                .font(.system(size: 30, weight: .bold))
                .monospacedDigit()
                .foregroundColor(palette.ink)
                .lineLimit(1)
            Text(WidgetCopy.remainingSubtitle)
                .font(.system(size: 12))
                .foregroundColor(palette.secondary)
                .lineLimit(1)
            Spacer(minLength: 6)
            if let next = rows(for: .small, day).first {
                HStack(alignment: .center, spacing: 6) {
                    PhaseDot(phase: next.phase, palette: palette)
                    Text(rowHeadline(next))
                        .font(.system(size: 13, weight: .semibold))
                        .foregroundColor(palette.ink)
                        .lineLimit(1)
                }
                let detail = rowDetail(next, showStaff: false)
                if !detail.isEmpty {
                    Text(detail)
                        .font(.system(size: 12))
                        .foregroundColor(palette.secondary)
                        .lineLimit(1)
                        .padding(.leading, 13)
                }
            } else {
                EmptyDayView(summary: summary, counts: day.counts, palette: palette, compact: true)
            }
            if let stale {
                StaleText(text: stale, palette: palette)
            }
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .topLeading)
    }
}

private struct MediumView: View {
    let summary: WidgetSummary
    let day: WidgetDay
    let stale: String?
    let palette: TodayPalette

    var body: some View {
        HStack(alignment: .top, spacing: 14) {
            VStack(alignment: .leading, spacing: 4) {
                Text(WidgetCopy.today)
                    .font(.system(size: 13, weight: .semibold))
                    .foregroundColor(palette.secondary)
                CountLine(label: WidgetCopy.total, value: day.counts.total, palette: palette)
                CountLine(label: WidgetCopy.completed, value: day.counts.completed, palette: palette)
                CountLine(label: WidgetCopy.remaining, value: day.counts.remaining, palette: palette)
                Spacer(minLength: 0)
                Link(destination: quickAddURL(.medium)) {
                    AddPill(text: WidgetCopy.addShort, palette: palette)
                }
            }
            .frame(width: 112, alignment: .leading)
            Rectangle()
                .fill(palette.hairline)
                .frame(width: 1)
            VStack(alignment: .leading, spacing: 10) {
                let shown = rows(for: .medium, day)
                if shown.isEmpty {
                    EmptyDayView(summary: summary, counts: day.counts, palette: palette, compact: false)
                } else {
                    ForEach(shown, id: \.id) { row in
                        RowLink(row: row) {
                            AppointmentRow(row: row, showStaff: false, showChip: false, palette: palette)
                        }
                    }
                }
                Spacer(minLength: 0)
                if let stale {
                    StaleText(text: stale, palette: palette)
                }
            }
            .frame(maxWidth: .infinity, alignment: .leading)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .topLeading)
    }
}

private struct LargeView: View {
    let summary: WidgetSummary
    let day: WidgetDay
    let stale: String?
    let palette: TodayPalette

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack(alignment: .center, spacing: 8) {
                Text(widgetTitle(orgName: summary.orgName))
                    .font(.system(size: 17, weight: .bold))
                    .foregroundColor(palette.ink)
                    .lineLimit(1)
                Spacer(minLength: 4)
                Link(destination: quickAddURL(.large)) {
                    AddPill(text: WidgetCopy.addLong, palette: palette)
                }
            }
            HStack(spacing: 0) {
                CountCell(label: WidgetCopy.total, value: day.counts.total, palette: palette)
                CountCell(label: WidgetCopy.completed, value: day.counts.completed, palette: palette)
                CountCell(label: WidgetCopy.remaining, value: day.counts.remaining, palette: palette)
            }
            .padding(.vertical, 6)
            .background(RoundedRectangle(cornerRadius: 10).stroke(palette.hairline, lineWidth: 1))
            let shown = rows(for: .large, day)
            if shown.isEmpty {
                EmptyDayView(summary: summary, counts: day.counts, palette: palette, compact: false)
            } else {
                VStack(alignment: .leading, spacing: 6) {
                    ForEach(shown, id: \.id) { row in
                        RowLink(row: row) {
                            AppointmentRow(row: row, showStaff: showsStaff(summary), showChip: true, palette: palette)
                        }
                    }
                }
            }
            Spacer(minLength: 0)
            if let stale {
                StaleText(text: stale, palette: palette)
            }
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .topLeading)
    }
}

// MARK: - Home Screen pieces
// Glyph-on-fill pieces (PlusBadge, AddPill, PlannMark) accent only their background shape: in
// accented rendering (iOS 18 tinted) only opacity survives, so an accented glyph would merge into
// its equally opaque fill.

/// A row opens its appointment; an id the app would not accept renders as a plain row.
private struct RowLink<Content: View>: View {
    let row: WidgetRow
    @ViewBuilder let content: () -> Content

    var body: some View {
        if let url = appointmentURL(id: row.id) {
            Link(destination: url) { content() }
        } else {
            content()
        }
    }
}

private struct AppointmentRow: View {
    let row: WidgetRow
    let showStaff: Bool
    let showChip: Bool
    let palette: TodayPalette

    var body: some View {
        HStack(alignment: .center, spacing: 8) {
            RoundedRectangle(cornerRadius: 2)
                .fill(palette.accent(row.phase))
                .frame(width: 4, height: 26)
                .widgetAccentable()
            VStack(alignment: .leading, spacing: 1) {
                HStack(spacing: 6) {
                    Text(row.startLabel)
                        .font(.system(size: 13, weight: .semibold))
                        .monospacedDigit()
                        .foregroundColor(palette.ink)
                    Text(rowTitle(row))
                        .font(.system(size: 13, weight: .semibold))
                        .foregroundColor(palette.ink)
                        .lineLimit(1)
                }
                let detail = rowDetail(row, showStaff: showStaff)
                if !detail.isEmpty {
                    Text(detail)
                        .font(.system(size: 11))
                        .foregroundColor(palette.secondary)
                        .lineLimit(1)
                }
            }
            Spacer(minLength: 4)
            if showChip, let chip = chipLabel(row.phase) {
                Text(chip)
                    .font(.system(size: 11, weight: .semibold))
                    .foregroundColor(palette.accent(row.phase))
                    .padding(.horizontal, 8)
                    .padding(.vertical, 3)
                    .background(Capsule().stroke(palette.accent(row.phase), lineWidth: 1))
                    .widgetAccentable()
            }
        }
    }
}

private struct PhaseDot: View {
    let phase: PlannPhase
    let palette: TodayPalette

    var body: some View {
        Circle()
            .fill(palette.accent(phase))
            .frame(width: 7, height: 7)
            .widgetAccentable()
    }
}

private struct PlusBadge: View {
    let palette: TodayPalette

    var body: some View {
        Image(systemName: "plus")
            .font(.system(size: 12, weight: .bold))
            .foregroundColor(.white)
            .frame(width: 22, height: 22)
            .background(Circle().fill(palette.amber).widgetAccentable())
    }
}

private struct AddPill: View {
    let text: String
    let palette: TodayPalette

    var body: some View {
        Text(text)
            .font(.system(size: 12, weight: .semibold))
            .foregroundColor(.white)
            .lineLimit(1)
            .padding(.horizontal, 10)
            .padding(.vertical, 6)
            .background(Capsule().fill(palette.amber).widgetAccentable())
    }
}

private struct CountLine: View {
    let label: String
    let value: Int
    let palette: TodayPalette

    var body: some View {
        HStack(alignment: .firstTextBaseline) {
            Text(label)
                .font(.system(size: 12))
                .foregroundColor(palette.secondary)
                .lineLimit(1)
            Spacer(minLength: 4)
            Text("\(value)")
                .font(.system(size: 15, weight: .bold))
                .monospacedDigit()
                .foregroundColor(palette.ink)
        }
    }
}

private struct CountCell: View {
    let label: String
    let value: Int
    let palette: TodayPalette

    var body: some View {
        VStack(spacing: 2) {
            Text("\(value)")
                .font(.system(size: 18, weight: .bold))
                .monospacedDigit()
                .foregroundColor(palette.ink)
            Text(label)
                .font(.system(size: 11))
                .foregroundColor(palette.secondary)
                .lineLimit(1)
        }
        .frame(maxWidth: .infinity)
    }
}

/// "Bugün başka randevu yok" (or "Bugün randevu yok") and tomorrow's first appointment.
private struct EmptyDayView: View {
    let summary: WidgetSummary
    let counts: WidgetSummary.Counts
    let palette: TodayPalette
    let compact: Bool

    var body: some View {
        VStack(alignment: .leading, spacing: 3) {
            Text(emptyTitle(counts))
                .font(.system(size: 13, weight: .semibold))
                .foregroundColor(palette.ink)
                .lineLimit(compact ? 2 : 1)
            if let tomorrow = tomorrowLine(summary.tomorrowFirst) {
                Text(tomorrow)
                    .font(.system(size: 12))
                    .foregroundColor(palette.secondary)
                    .lineLimit(compact ? 2 : 1)
            }
        }
    }
}

private struct StaleText: View {
    let text: String
    let palette: TodayPalette

    var body: some View {
        Text(text)
            .font(.system(size: 10))
            .foregroundColor(palette.muted)
            .lineLimit(1)
            .padding(.top, 2)
    }
}

private struct PlannMark: View {
    let palette: TodayPalette
    let size: CGFloat

    var body: some View {
        Text("P")
            .font(.system(size: size * 0.55, weight: .heavy))
            .foregroundColor(.white)
            .frame(width: size, height: size)
            .background(RoundedRectangle(cornerRadius: size * 0.28).fill(palette.amber).widgetAccentable())
    }
}

private struct SignedOutView: View {
    let palette: TodayPalette
    let compact: Bool

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack(spacing: 8) {
                PlannMark(palette: palette, size: 28)
                Text(WidgetCopy.brand)
                    .font(.system(size: 15, weight: .bold))
                    .foregroundColor(palette.ink)
            }
            Spacer(minLength: 0)
            Text(WidgetCopy.signedOut)
                .font(.system(size: compact ? 13 : 14, weight: .semibold))
                .foregroundColor(palette.secondary)
                .lineLimit(3)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .topLeading)
    }
}

private struct UnreachableView: View {
    let kind: WidgetFamilyKind
    let palette: TodayPalette

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack(alignment: .top) {
                Text(WidgetCopy.today)
                    .font(.system(size: 13, weight: .semibold))
                    .foregroundColor(palette.secondary)
                Spacer(minLength: 4)
                if kind == .small {
                    PlusBadge(palette: palette)
                } else {
                    Link(destination: quickAddURL(kind)) {
                        AddPill(text: kind == .large ? WidgetCopy.addLong : WidgetCopy.addShort, palette: palette)
                    }
                }
            }
            Spacer(minLength: 0)
            HStack(spacing: 6) {
                Image(systemName: "wifi.exclamationmark")
                    .font(.system(size: 13, weight: .semibold))
                    .foregroundColor(palette.muted)
                Text(WidgetCopy.unreachable)
                    .font(.system(size: 14, weight: .semibold))
                    .foregroundColor(palette.ink)
                    .lineLimit(1)
            }
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .topLeading)
    }
}

// MARK: - Lock Screen

private struct LockRectangularView: View {
    let entry: TodayEntry

    var body: some View {
        VStack(alignment: .leading, spacing: 1) {
            switch entry.content {
            case .signedOut:
                Text(WidgetCopy.brand)
                    .font(.system(size: 13, weight: .bold))
                    .widgetAccentable()
                Text(WidgetCopy.signedOut)
                    .font(.system(size: 13))
                    .lineLimit(2)
            case .unreachable:
                Text(WidgetCopy.today)
                    .font(.system(size: 13, weight: .bold))
                    .widgetAccentable()
                Text(WidgetCopy.unreachable)
                    .font(.system(size: 13))
                    .lineLimit(1)
            case .summary(let summary):
                let day = widgetDay(summary, at: entry.date)
                if let next = rows(for: .rectangular, day).first {
                    HStack(spacing: 4) {
                        Text(next.startLabel)
                            .font(.system(size: 15, weight: .bold))
                            .monospacedDigit()
                            .widgetAccentable()
                        Text(rowTitle(next))
                            .font(.system(size: 15, weight: .semibold))
                            .lineLimit(1)
                    }
                    let detail = rowDetail(next, showStaff: false)
                    if !detail.isEmpty {
                        Text(detail)
                            .font(.system(size: 13))
                            .lineLimit(1)
                    }
                } else {
                    Text(emptyTitle(day.counts))
                        .font(.system(size: 13, weight: .semibold))
                        .lineLimit(2)
                    if let tomorrow = tomorrowLine(summary.tomorrowFirst) {
                        Text(tomorrow)
                            .font(.system(size: 12))
                            .lineLimit(1)
                    }
                }
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }
}

private struct LockCircularView: View {
    let entry: TodayEntry

    var body: some View {
        switch entry.content {
        case .summary(let summary):
            let counts = widgetDay(summary, at: entry.date).counts
            Gauge(value: Double(counts.completed), in: 0...Double(max(counts.total, 1))) {
                Text(WidgetCopy.remaining)
            } currentValueLabel: {
                Text("\(counts.remaining)")
                    .monospacedDigit()
            }
            .gaugeStyle(.accessoryCircularCapacity)
            .widgetAccentable()
        default:
            ZStack {
                AccessoryWidgetBackground()
                Text(WidgetCopy.brand.prefix(1))
                    .font(.system(size: 20, weight: .heavy))
                    .widgetAccentable()
            }
        }
    }
}
