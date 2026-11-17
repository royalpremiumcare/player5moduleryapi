import XCTest
import Foundation
#if canImport(FoundationNetworking)
import FoundationNetworking
#endif
@testable import LiveActivityCore

final class WidgetTests: XCTestCase {
    // 2026-11-17T14:00:00+03:00
    static let base: Double = 1794913200
    static var t0: Date { Date(timeIntervalSince1970: base) }

    func fixture() throws -> WidgetSummary {
        let url = try XCTUnwrap(Bundle.module.url(forResource: "widget_summary", withExtension: "json", subdirectory: "Fixtures"))
        return try JSONDecoder().decode(WidgetSummary.self, from: Data(contentsOf: url))
    }

    func item(_ id: String, _ start: Double, _ end: Double, _ phase: PlannPhase = .upcoming) -> WidgetItem {
        WidgetItem(id: id, startLabel: "s", endLabel: "e", startEpoch: start, endEpoch: end,
                   phase: phase, customerDisplay: nil, serviceName: "svc", staffName: nil)
    }

    func summary(_ items: [WidgetItem], completed: Int = 0) -> WidgetSummary {
        WidgetSummary(generatedAt: "2026-11-17T14:00:00+03:00", scope: "own", privacyMode: "full", orgName: nil,
                      counts: .init(total: completed + items.count, completed: completed, remaining: items.count),
                      items: items, tomorrowFirst: nil)
    }

    func testDecodesFixture() throws {
        let s = try fixture()
        XCTAssertEqual(s.scope, "all")
        XCTAssertEqual(s.orgName, "Salon Güzel")
        XCTAssertEqual(s.counts, WidgetSummary.Counts(total: 5, completed: 2, remaining: 3))
        XCTAssertEqual(s.items.count, 3)
        XCTAssertEqual(s.items[0].phase, .processing)
        XCTAssertEqual(s.items[0].staffName, "Mehmet")
        XCTAssertNil(s.items[2].customerDisplay)
        XCTAssertEqual(s.tomorrowFirst?.startLabel, "09:30")
        // fractional seconds + offset decode robustly
        XCTAssertEqual(s.generatedAtDate?.timeIntervalSince1970 ?? 0, Self.base + 0.123456, accuracy: 0.001)
    }

    func testGeneratedAtWithoutFractionAndZulu() {
        XCTAssertEqual(summary([]).generatedAtDate, Self.t0)
        var s = summary([]); s.generatedAt = "2026-11-17T11:00:00Z"
        XCTAssertEqual(s.generatedAtDate, Self.t0)
    }

    func testUnknownPhaseTolerated() throws {
        let json = #"{"generatedAt":"2026-11-17T14:00:00+03:00","scope":"own","privacyMode":"full","counts":{"total":1,"completed":0,"remaining":1},"items":[{"id":"x","startLabel":"a","endLabel":"b","startEpoch":1.0,"endEpoch":2.0,"phase":"zzz","customerDisplay":null,"serviceName":"s"}],"tomorrowFirst":null}"#
        let s = try JSONDecoder().decode(WidgetSummary.self, from: Data(json.utf8))
        XCTAssertEqual(s.items[0].phase, .unknown)
        XCTAssertNil(s.orgName)
        XCTAssertTrue(widgetDay(s, at: Self.t0).rows.isEmpty)
    }

    func testRollsUpcomingToProcessingAtStart() throws {
        let s = try fixture()
        let before = widgetDay(s, at: Self.t0)
        XCTAssertEqual(before.rows.map(\.id), ["apt-1", "apt-2", "apt-3"])
        XCTAssertEqual(before.rows.map(\.phase), [.processing, .upcoming, .upcoming])
        let after = widgetDay(s, at: Date(timeIntervalSince1970: Self.base + 1800))
        XCTAssertEqual(after.rows.map(\.id), ["apt-2", "apt-3"])
        XCTAssertEqual(after.rows.map(\.phase), [.processing, .upcoming])
    }

    func testDropsEndedRowAndShiftsCounts() throws {
        let s = try fixture()
        let d = widgetDay(s, at: Date(timeIntervalSince1970: Self.base + 900)) // apt-1 ends exactly
        XCTAssertEqual(d.rows.map(\.id), ["apt-2", "apt-3"])
        XCTAssertEqual(d.counts, WidgetSummary.Counts(total: 5, completed: 3, remaining: 2))
        let late = widgetDay(s, at: Date(timeIntervalSince1970: Self.base + 4000))
        XCTAssertEqual(late.counts, WidgetSummary.Counts(total: 5, completed: 4, remaining: 1))
    }

    func testProcessingSortedByEndThenUpcomingByStart() {
        let b = Self.base
        let s = summary([item("u2", b + 5000, b + 6000), item("p2", b - 100, b + 900, .processing),
                         item("u1", b + 3000, b + 4000), item("p1", b - 100, b + 300, .processing)])
        XCTAssertEqual(widgetDay(s, at: Self.t0).rows.map(\.id), ["p1", "p2", "u1", "u2"])
    }

    func testEntryDatesBoundariesDedupedCapped() throws {
        let s = try fixture()
        let d = entryDates(s, from: Self.t0)
        XCTAssertEqual(d.map(\.timeIntervalSince1970),
                       [Self.base, Self.base + 900, Self.base + 1800, Self.base + 3600, Self.base + 7200, Self.base + 9900])
        let b = Self.base
        let dup = summary([item("a", b + 60, b + 120), item("b", b + 60, b + 120)])
        XCTAssertEqual(entryDates(dup, from: Self.t0).count, 3)
        let many = summary((0..<50).map { item("i\($0)", b + Double($0 * 100 + 10), b + Double($0 * 100 + 60)) })
        XCTAssertEqual(entryDates(many, from: Self.t0).count, 60)
        XCTAssertEqual(entryDates(many, from: Self.t0).first, Self.t0)
    }

    func testNextReloadMinOfBoundaryAnd15Min() throws {
        let s = try fixture()
        XCTAssertEqual(nextReload(s, from: Self.t0), Self.t0.addingTimeInterval(900))
        let soon = summary([item("a", Self.base + 120, Self.base + 5000)])
        XCTAssertEqual(nextReload(soon, from: Self.t0), Self.t0.addingTimeInterval(120))
        let far = summary([item("a", Self.base + 5000, Self.base + 6000)])
        XCTAssertEqual(nextReload(far, from: Self.t0), Self.t0.addingTimeInterval(900))
        XCTAssertEqual(nextReload(nil, from: Self.t0), Self.t0.addingTimeInterval(900))
    }

    func testRowsPerFamily() throws {
        let b = Self.base
        let day = widgetDay(summary((0..<7).map { item("i\($0)", b + Double($0 * 100 + 10), b + Double($0 * 100 + 60)) }), at: Self.t0)
        XCTAssertEqual(rows(for: .small, day).count, 1)
        XCTAssertEqual(rows(for: .medium, day).count, 2)
        XCTAssertEqual(rows(for: .large, day).count, 5)
        XCTAssertEqual(rows(for: .rectangular, day).count, 1)
        XCTAssertEqual(rows(for: .circular, day).count, 0)
        XCTAssertEqual(rows(for: .small, day).first?.id, "i0")
    }

    func testStaleLabelAfter30Min() throws {
        let tz = try XCTUnwrap(TimeZone(identifier: "Europe/Istanbul"))
        let gen = Self.t0
        XCTAssertNil(staleLabel(generatedAt: gen, now: gen.addingTimeInterval(30 * 60), tz: tz))
        XCTAssertEqual(staleLabel(generatedAt: gen, now: gen.addingTimeInterval(30 * 60 + 1), tz: tz), "Güncellendi 14:00")
    }

    func testSha256KnownVectors() {
        XCTAssertEqual(sha256hex(""), "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855")
        XCTAssertEqual(sha256hex("abc"), "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad")
        XCTAssertEqual(sha256hex("abcdbcdecdefdefgefghfghighijhijkijkljklmklmnlmnomnopnopq"),
                       "248d6a61d20638b8e5c026930c3e6039a33ce45964ff2167f6ecedd419db06c1")
    }

    func testCacheUsableOnlyWithMatchingKey() throws {
        let s = summary([])
        let env = WidgetCacheEnvelope(keyHash: sha256hex("key-1"), summary: s, fetchedAt: Self.t0)
        XCTAssertEqual(usableCache(env, currentKey: "key-1"), s)
        XCTAssertNil(usableCache(env, currentKey: "key-2"))
    }

    func testCacheNilWithoutKey() {
        let env = WidgetCacheEnvelope(keyHash: sha256hex(""), summary: summary([]), fetchedAt: Self.t0)
        XCTAssertNil(usableCache(env, currentKey: nil))
        XCTAssertNil(usableCache(nil, currentKey: "k"))
    }

    func testRequestRejectsHttp() {
        XCTAssertNil(summaryRequest(baseURL: "http://plannapp.co", key: "k"))
        XCTAssertNil(summaryRequest(baseURL: "not a url", key: "k"))
    }

    func testRequestHasHeaderAndTimeout() throws {
        let r = try XCTUnwrap(summaryRequest(baseURL: "https://plannapp.co/", key: "abc"))
        XCTAssertEqual(r.url?.absoluteString, "https://plannapp.co/api/widget/summary")
        XCTAssertEqual(r.httpMethod, "GET")
        XCTAssertEqual(r.value(forHTTPHeaderField: "X-Plann-Widget-Key"), "abc")
        XCTAssertEqual(r.timeoutInterval, 10)
    }
}
