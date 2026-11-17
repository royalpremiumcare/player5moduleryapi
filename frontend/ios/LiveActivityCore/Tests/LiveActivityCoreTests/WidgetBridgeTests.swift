import XCTest
import Foundation
@testable import LiveActivityCore

final class WidgetBridgeTests: XCTestCase {
    let t0 = Date(timeIntervalSince1970: 1794913200)

    // MARK: base URL

    func testAcceptsHttpsOrigins() {
        XCTAssertTrue(WidgetBridge.isAcceptableBaseURL("https://plannapp.co"))
        XCTAssertTrue(WidgetBridge.isAcceptableBaseURL("https://plannapp.co/"))
        XCTAssertTrue(WidgetBridge.isAcceptableBaseURL("https://beta.plannapp.co:8443"))
    }

    func testRejectsNonHttpsAndMalformed() {
        XCTAssertFalse(WidgetBridge.isAcceptableBaseURL("http://plannapp.co"))
        XCTAssertFalse(WidgetBridge.isAcceptableBaseURL("ftp://plannapp.co"))
        XCTAssertFalse(WidgetBridge.isAcceptableBaseURL("plannapp.co"))
        XCTAssertFalse(WidgetBridge.isAcceptableBaseURL(""))
        XCTAssertFalse(WidgetBridge.isAcceptableBaseURL("https://"))
        XCTAssertFalse(WidgetBridge.isAcceptableBaseURL("https:///api"))
        XCTAssertFalse(WidgetBridge.isAcceptableBaseURL(" https://plannapp.co"))
    }

    /// Whatever the app stores, the widget must be able to build its request from.
    func testAcceptedURLsBuildASummaryRequest() {
        for base in ["https://plannapp.co", "https://plannapp.co/", "https://beta.plannapp.co:8443"] {
            XCTAssertTrue(WidgetBridge.isAcceptableBaseURL(base))
            XCTAssertNotNil(summaryRequest(baseURL: base, key: "k"), base)
        }
    }

    // MARK: reload debounce (one reloadAllTimelines per 5 s)

    func testFirstReloadAlwaysRuns() {
        XCTAssertTrue(WidgetBridge.shouldReload(last: nil, now: t0))
    }

    func testReloadWithinFiveSecondsIsSuppressed() {
        XCTAssertFalse(WidgetBridge.shouldReload(last: t0, now: t0))
        XCTAssertFalse(WidgetBridge.shouldReload(last: t0, now: t0.addingTimeInterval(4.999)))
    }

    func testReloadAtOrAfterFiveSecondsRuns() {
        XCTAssertTrue(WidgetBridge.shouldReload(last: t0, now: t0.addingTimeInterval(5)))
        XCTAssertTrue(WidgetBridge.shouldReload(last: t0, now: t0.addingTimeInterval(60)))
    }

    /// A clock set backwards must not block reloads until the old time comes round again.
    func testReloadRunsWhenClockWentBackwards() {
        XCTAssertTrue(WidgetBridge.shouldReload(last: t0, now: t0.addingTimeInterval(-1)))
    }

    func testTrailingDelayIsTheRestOfTheWindow() {
        XCTAssertEqual(WidgetBridge.reloadDelay(last: t0, now: t0.addingTimeInterval(1.5)), 3.5, accuracy: 0.0001)
        XCTAssertEqual(WidgetBridge.reloadDelay(last: t0, now: t0), 5, accuracy: 0.0001)
        XCTAssertEqual(WidgetBridge.reloadDelay(last: nil, now: t0), 0)
        XCTAssertEqual(WidgetBridge.reloadDelay(last: t0, now: t0.addingTimeInterval(9)), 0)
        XCTAssertEqual(WidgetBridge.reloadDelay(last: t0, now: t0.addingTimeInterval(-1)), 0)
    }

    // MARK: shared keychain

    func testKeychainNames() {
        XCTAssertEqual(WidgetBridge.keychainService, "co.plannapp.app.widget")
        XCTAssertEqual(WidgetBridge.keyAccount, "widget_key")
        XCTAssertEqual(WidgetBridge.baseURLAccount, "api_base_url")
    }

    func testAccessGroupFromExpandedPrefix() {
        XCTAssertEqual(WidgetBridge.accessGroup(appIdentifierPrefix: "ABCDE12345."), "ABCDE12345.co.plannapp.app.shared")
        // tolerate a prefix without its trailing dot
        XCTAssertEqual(WidgetBridge.accessGroup(appIdentifierPrefix: "ABCDE12345"), "ABCDE12345.co.plannapp.app.shared")
    }

    func testAccessGroupNilWhenPrefixMissingOrUnexpanded() {
        XCTAssertNil(WidgetBridge.accessGroup(appIdentifierPrefix: nil))
        XCTAssertNil(WidgetBridge.accessGroup(appIdentifierPrefix: ""))
        XCTAssertNil(WidgetBridge.accessGroup(appIdentifierPrefix: "."))
        XCTAssertNil(WidgetBridge.accessGroup(appIdentifierPrefix: "$(AppIdentifierPrefix)"))
        XCTAssertNil(WidgetBridge.accessGroup(appIdentifierPrefix: "AB CD."))
    }
}
