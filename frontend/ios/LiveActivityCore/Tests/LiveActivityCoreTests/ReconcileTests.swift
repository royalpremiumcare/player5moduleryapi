import XCTest
@testable import LiveActivityCore

final class ReconcileTests: XCTestCase {
    func testEndInstructionsEmptyResponseEndsNothing() throws {
        let cur = [ActivitySnapshot(slotIndex: 1, activityId: "A", state: "active")]
        let resp = try JSONDecoder().decode(ReconcileResponse.self, from: Data("{}".utf8))
        XCTAssertTrue(endInstructions(response: resp, current: cur).isEmpty)
    }
}
