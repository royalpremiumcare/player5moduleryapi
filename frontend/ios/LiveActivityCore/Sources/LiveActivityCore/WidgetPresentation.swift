import Foundation

/// What a TodayWidget entry shows. Decided once per timeline, so the views only render.
public enum WidgetContent: Equatable, Sendable {
    case signedOut
    case unreachable
    case summary(WidgetSummary)
}

/// No credential is always signed out, whatever is cached (spec §7A.9). A fresh fetch wins; on a
/// failed fetch only the cache written for this very key is used.
public func widgetContent(fetched: WidgetSummary?, cache: WidgetCacheEnvelope?, currentKey: String?) -> WidgetContent {
    guard let currentKey else { return .signedOut }
    if let fetched { return .summary(fetched) }
    if let cached = usableCache(cache, currentKey: currentKey) { return .summary(cached) }
    return .unreachable
}

/// The widget's Turkish copy (plan Global Constraints), kept verbatim in one place.
public enum WidgetCopy {
    public static let today = "Bugün"
    public static let remainingSubtitle = "kalan randevu"
    public static let total = "Toplam"
    public static let completed = "Tamamlanan"
    public static let remaining = "Kalan"
    public static let addShort = "＋ Randevu"
    public static let addLong = "＋ Yeni randevu"
    public static let upcoming = "Sıradaki"
    public static let processing = "İşlemde"
    public static let noMoreToday = "Bugün başka randevu yok"
    public static let noneToday = "Bugün randevu yok"
    public static let signedOut = "Görmek için PLANN'a giriş yapın"
    public static let unreachable = "Bağlanılamadı"
    public static let galleryName = "PLANN · Bugün"
    public static let galleryDescription = "Bugünkü randevularınız ve hızlı randevu ekleme"
    public static let brand = "PLANN"
}

/// Rows only ever hold upcoming or processing appointments (spec §7A.1).
public func chipLabel(_ phase: PlannPhase) -> String? {
    switch phase {
    case .upcoming: return WidgetCopy.upcoming
    case .processing: return WidgetCopy.processing
    default: return nil
    }
}

public func widgetTitle(orgName: String?) -> String {
    let name = orgName?.trimmingCharacters(in: .whitespacesAndNewlines) ?? ""
    return name.isEmpty ? WidgetCopy.brand : name
}

public func emptyTitle(_ counts: WidgetSummary.Counts) -> String {
    counts.total == 0 ? WidgetCopy.noneToday : WidgetCopy.noMoreToday
}

public func tomorrowLine(_ t: WidgetTomorrowItem?) -> String? {
    guard let t else { return nil }
    return "Yarın ilk: \(t.startLabel) · \(t.customerDisplay ?? t.serviceName)"
}

/// The customer when the privacy mode shows one, otherwise the service.
public func rowTitle(_ row: WidgetRow) -> String { row.customerDisplay ?? row.serviceName }

public func rowHeadline(_ row: WidgetRow) -> String { "\(row.startLabel) · \(rowTitle(row))" }

/// The service (unless it is already the title) and, for the "all" scope, the staff member.
public func rowDetail(_ row: WidgetRow, showStaff: Bool) -> String {
    var parts: [String] = []
    if row.customerDisplay != nil { parts.append(row.serviceName) }
    if showStaff, let staff = row.staffName, !staff.isEmpty { parts.append(staff) }
    return parts.joined(separator: " · ")
}

public func showsStaff(_ s: WidgetSummary) -> Bool { s.scope == "all" }

public func quickAddURL(_ family: WidgetFamilyKind) -> URL {
    let source: String
    switch family {
    case .small: source = "widget_small"
    case .medium: source = "widget_medium"
    case .large: source = "widget_large"
    case .rectangular, .circular: source = "widget_lock"
    }
    return URL(string: "plannapp://new-appointment?source=\(source)")!
}

/// Same id rule as the app's deep-link parser: 1–64 of [A-Za-z0-9_-].
public func appointmentURL(id: String) -> URL? {
    guard (1...64).contains(id.count),
          id.unicodeScalars.allSatisfy({ $0.isASCII && (CharacterSet.alphanumerics.contains($0) || $0 == "_" || $0 == "-") })
    else { return nil }
    return URL(string: "plannapp://appointment/\(id)")
}
