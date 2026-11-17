import XCTest
import Foundation
@testable import LiveActivityCore

final class WidgetPresentationTests: XCTestCase {
    func summary(orgName: String? = nil, items: [WidgetItem] = [], total: Int = 0,
                 tomorrow: WidgetTomorrowItem? = nil) -> WidgetSummary {
        WidgetSummary(generatedAt: "2026-11-17T14:00:00+03:00", scope: "own", privacyMode: "full", orgName: orgName,
                      counts: .init(total: total, completed: total - items.count, remaining: items.count),
                      items: items, tomorrowFirst: tomorrow)
    }

    func row(customer: String?, service: String = "Fön", staff: String? = "Elif",
             phase: PlannPhase = .upcoming) -> WidgetRow {
        let it = WidgetItem(id: "apt-1", startLabel: "14:30", endLabel: "15:00", startEpoch: 100, endEpoch: 200,
                            phase: phase, customerDisplay: customer, serviceName: service, staffName: staff)
        return widgetDay(summary(items: [it], total: 1), at: Date(timeIntervalSince1970: 0)).rows[0]
    }

    // MARK: content resolution (Review Focus 1 and 5)

    func testNoCredentialIsSignedOutEvenWithACache() {
        let s = summary()
        let env = WidgetCacheEnvelope(keyHash: sha256hex("k"), summary: s, fetchedAt: Date())
        XCTAssertEqual(widgetContent(fetched: nil, cache: env, currentKey: nil), .signedOut)
        XCTAssertEqual(widgetContent(fetched: s, cache: env, currentKey: nil), .signedOut)
    }

    func testFreshFetchWins() {
        let fresh = summary(orgName: "Yeni")
        let env = WidgetCacheEnvelope(keyHash: sha256hex("k"), summary: summary(orgName: "Eski"), fetchedAt: Date())
        XCTAssertEqual(widgetContent(fetched: fresh, cache: env, currentKey: "k"), .summary(fresh))
    }

    func testFailedFetchFallsBackToMatchingCacheOnly() {
        let cached = summary(orgName: "Eski")
        let env = WidgetCacheEnvelope(keyHash: sha256hex("k"), summary: cached, fetchedAt: Date())
        XCTAssertEqual(widgetContent(fetched: nil, cache: env, currentKey: "k"), .summary(cached))
        XCTAssertEqual(widgetContent(fetched: nil, cache: env, currentKey: "other"), .unreachable)
        XCTAssertEqual(widgetContent(fetched: nil, cache: nil, currentKey: "k"), .unreachable)
    }

    // MARK: copy

    func testCopyStringsVerbatim() {
        XCTAssertEqual(WidgetCopy.today, "Bugün")
        XCTAssertEqual(WidgetCopy.remainingSubtitle, "kalan randevu")
        XCTAssertEqual(WidgetCopy.total, "Toplam")
        XCTAssertEqual(WidgetCopy.completed, "Tamamlanan")
        XCTAssertEqual(WidgetCopy.remaining, "Kalan")
        XCTAssertEqual(WidgetCopy.addShort, "＋ Randevu")
        XCTAssertEqual(WidgetCopy.addLong, "＋ Yeni randevu")
        XCTAssertEqual(WidgetCopy.signedOut, "Görmek için PLANN'a giriş yapın")
        XCTAssertEqual(WidgetCopy.unreachable, "Bağlanılamadı")
        XCTAssertEqual(WidgetCopy.galleryName, "PLANN · Bugün")
        XCTAssertEqual(WidgetCopy.galleryDescription, "Bugünkü randevularınız ve hızlı randevu ekleme")
    }

    func testChipOnlyUpcomingAndProcessing() {
        XCTAssertEqual(chipLabel(.upcoming), "Sıradaki")
        XCTAssertEqual(chipLabel(.processing), "İşlemde")
        XCTAssertNil(chipLabel(.completed))
        XCTAssertNil(chipLabel(.cancelled))
    }

    func testTitleFallsBackToPlann() {
        XCTAssertEqual(widgetTitle(orgName: "Salon Güzel"), "Salon Güzel")
        XCTAssertEqual(widgetTitle(orgName: ""), "PLANN")
        XCTAssertEqual(widgetTitle(orgName: "   "), "PLANN")
        XCTAssertEqual(widgetTitle(orgName: nil), "PLANN")
    }

    func testEmptyTitleDependsOnWhetherTheDayHadAppointments() {
        XCTAssertEqual(emptyTitle(.init(total: 0, completed: 0, remaining: 0)), "Bugün randevu yok")
        XCTAssertEqual(emptyTitle(.init(total: 3, completed: 3, remaining: 0)), "Bugün başka randevu yok")
    }

    func testTomorrowLine() {
        XCTAssertEqual(tomorrowLine(.init(startLabel: "09:30", customerDisplay: "Ayşe Kaya", serviceName: "Kesim")),
                       "Yarın ilk: 09:30 · Ayşe Kaya")
        XCTAssertEqual(tomorrowLine(.init(startLabel: "09:30", customerDisplay: nil, serviceName: "Kesim")),
                       "Yarın ilk: 09:30 · Kesim")
        XCTAssertNil(tomorrowLine(nil))
    }

    func testRowTextWithAndWithoutCustomer() {
        let named = row(customer: "Ayşe Kaya")
        XCTAssertEqual(rowTitle(named), "Ayşe Kaya")
        XCTAssertEqual(rowHeadline(named), "14:30 · Ayşe Kaya")
        XCTAssertEqual(rowDetail(named, showStaff: false), "Fön")
        XCTAssertEqual(rowDetail(named, showStaff: true), "Fön · Elif")
        let hidden = row(customer: nil)
        XCTAssertEqual(rowTitle(hidden), "Fön")
        XCTAssertEqual(rowDetail(hidden, showStaff: false), "")
        XCTAssertEqual(rowDetail(hidden, showStaff: true), "Elif")
        XCTAssertEqual(rowDetail(row(customer: "A", staff: ""), showStaff: true), "Fön")
    }

    func testStaffShownOnlyForAllScope() {
        var s = summary()
        XCTAssertFalse(showsStaff(s))
        s.scope = "all"
        XCTAssertTrue(showsStaff(s))
    }

    // MARK: deep links

    func testQuickAddURLPerFamily() {
        XCTAssertEqual(quickAddURL(.small).absoluteString, "plannapp://new-appointment?source=widget_small")
        XCTAssertEqual(quickAddURL(.medium).absoluteString, "plannapp://new-appointment?source=widget_medium")
        XCTAssertEqual(quickAddURL(.large).absoluteString, "plannapp://new-appointment?source=widget_large")
        XCTAssertEqual(quickAddURL(.rectangular).absoluteString, "plannapp://new-appointment?source=widget_lock")
        XCTAssertEqual(quickAddURL(.circular).absoluteString, "plannapp://new-appointment?source=widget_lock")
    }

    func testAppointmentURLOnlyForSafeIds() {
        XCTAssertEqual(appointmentURL(id: "apt-1_A9")?.absoluteString, "plannapp://appointment/apt-1_A9")
        XCTAssertNil(appointmentURL(id: ""))
        XCTAssertNil(appointmentURL(id: "a/b"))
        XCTAssertNil(appointmentURL(id: "a?x=1"))
        XCTAssertNil(appointmentURL(id: String(repeating: "a", count: 65)))
        XCTAssertNotNil(appointmentURL(id: String(repeating: "a", count: 64)))
    }
}
