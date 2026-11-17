import XCTest
@testable import LiveActivityCore

final class SectorIconTests: XCTestCase {
    func testMapsEverySectorTokenToItsSymbol() {
        XCTAssertEqual(symbolForIcon("hair"), "scissors")
        XCTAssertEqual(symbolForIcon("beauty"), "paintbrush.pointed")
        XCTAssertEqual(symbolForIcon("spa"), "leaf")
        XCTAssertEqual(symbolForIcon("diet"), "fork.knife")
        XCTAssertEqual(symbolForIcon("therapy"), "bubble.left.and.bubble.right")
        XCTAssertEqual(symbolForIcon("dental"), "stethoscope")
        XCTAssertEqual(symbolForIcon("generic"), "hourglass")
    }

    func testMissingOrUnknownTokenFallsBackToHourglass() {
        XCTAssertEqual(symbolForIcon(nil), "hourglass")
        XCTAssertEqual(symbolForIcon(""), "hourglass")
        XCTAssertEqual(symbolForIcon("rocket"), "hourglass")
        XCTAssertEqual(symbolForIcon("HAIR"), "hourglass")
    }
}
