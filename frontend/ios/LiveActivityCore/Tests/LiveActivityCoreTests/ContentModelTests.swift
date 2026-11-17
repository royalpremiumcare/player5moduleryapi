import XCTest
import Foundation
@testable import LiveActivityCore

final class ContentModelTests: XCTestCase {
    private func fixtureData() throws -> Data {
        let url = try XCTUnwrap(Bundle.module.url(forResource: "live_activity_content_state", withExtension: "json", subdirectory: "Fixtures"))
        return try Data(contentsOf: url)
    }

    func testDecodesBackendGoldenFixture() throws {
        let s = try JSONDecoder().decode(PlannContentState.self, from: fixtureData())
        XCTAssertEqual(s.phase, .upcoming)
        XCTAssertEqual(s.startEpoch, 1794828600.0)
        XCTAssertEqual(s.endEpoch, 1794831300.0)
        XCTAssertEqual(s.startLabel, "14:30")
        XCTAssertEqual(s.endLabel, "15:15")
        XCTAssertEqual(s.customerDisplay, "Ayşe Y.")
        XCTAssertEqual(s.serviceName, "Saç Boyama")
        XCTAssertEqual(s.staffName, "Mehmet")
        XCTAssertEqual(s.version, 3)
        XCTAssertFalse(s.appointmentId.isEmpty)
        XCTAssertEqual(s.startDate.timeIntervalSince1970, 1794828600.0)
        XCTAssertEqual(s.endDate.timeIntervalSince1970, 1794831300.0)
    }

    func testDecodesIconAndToleratesMissingIcon() throws {
        let withIcon = try JSONDecoder().decode(PlannContentState.self, from: fixtureData())
        XCTAssertEqual(withIcon.icon, "hair")
        let json = #"{"phase":"processing","startEpoch":1,"endEpoch":2,"startLabel":"a","endLabel":"b","customerDisplay":null,"serviceName":"s","staffName":null,"version":1,"appointmentId":"x"}"#
        let old = try JSONDecoder().decode(PlannContentState.self, from: Data(json.utf8))
        XCTAssertNil(old.icon)
        let nul = json.replacingOccurrences(of: #""version":1"#, with: #""version":1,"icon":null"#)
        XCTAssertNil(try JSONDecoder().decode(PlannContentState.self, from: Data(nul.utf8)).icon)
    }

    func testFixtureMatchesBackendCopy() throws {
        // <repo>/frontend/ios/LiveActivityCore/Tests/LiveActivityCoreTests/ContentModelTests.swift
        var url = URL(fileURLWithPath: #filePath)
        for _ in 0..<6 { url.deleteLastPathComponent() }
        let backend = url.appendingPathComponent("backend/tests/contracts/live_activity_content_state.json")
        XCTAssertTrue(FileManager.default.fileExists(atPath: backend.path), "backend fixture missing at \(backend.path)")
        let backendData = try Data(contentsOf: backend)
        XCTAssertEqual(try fixtureData(), backendData)
    }

    func testUnknownPhaseDecodesAsUnknown() throws {
        let json = #"{"phase":"teleporting","startEpoch":1,"endEpoch":2,"startLabel":"a","endLabel":"b","customerDisplay":null,"serviceName":"s","staffName":null,"version":1,"appointmentId":"x"}"#
        let s = try JSONDecoder().decode(PlannContentState.self, from: Data(json.utf8))
        XCTAssertEqual(s.phase, .unknown)
        let out = try JSONEncoder().encode(s)
        let obj = try XCTUnwrap(JSONSerialization.jsonObject(with: out) as? [String: Any])
        XCTAssertEqual(obj["phase"] as? String, "unknown")
    }

    func testRemovedStubDecodes() throws {
        let json = #"{"phase":"removed","startEpoch":0,"endEpoch":0,"startLabel":"","endLabel":"","customerDisplay":null,"serviceName":"","staffName":null,"version":7,"appointmentId":""}"#
        let s = try JSONDecoder().decode(PlannContentState.self, from: Data(json.utf8))
        XCTAssertEqual(s.phase, .removed)
        XCTAssertNil(s.customerDisplay)
        XCTAssertNil(s.staffName)
        XCTAssertEqual(s.serviceName, "")
        XCTAssertEqual(s.appointmentId, "")
        XCTAssertEqual(s.startLabel, "")
    }

    func testRoundTripKeepsBackendKeys() throws {
        let s = try JSONDecoder().decode(PlannContentState.self, from: fixtureData())
        let out = try JSONEncoder().encode(s)
        XCTAssertEqual(try JSONDecoder().decode(PlannContentState.self, from: out), s)
        let obj = try XCTUnwrap(JSONSerialization.jsonObject(with: out) as? [String: Any])
        XCTAssertEqual(Set(obj.keys), ["phase","startEpoch","endEpoch","startLabel","endLabel","customerDisplay","serviceName","staffName","version","appointmentId","icon"])
        XCTAssertEqual(obj["phase"] as? String, "upcoming")
    }

    func testTerminalPhases() {
        func st(_ p: PlannPhase) -> PlannContentState {
            PlannContentState(phase: p, startEpoch: 0, endEpoch: 0, startLabel: "", endLabel: "", customerDisplay: nil, serviceName: "", staffName: nil, version: 1, appointmentId: "a")
        }
        for p in [PlannPhase.completed, .cancelled, .removed, .unknown] { XCTAssertTrue(st(p).isTerminal, "\(p)") }
        for p in [PlannPhase.upcoming, .processing] { XCTAssertFalse(st(p).isTerminal, "\(p)") }
    }

    func testSlotIdParsing() {
        let ok = SlotId("ABC:DEF:3")
        XCTAssertEqual(ok?.deviceId, "ABC:DEF")
        XCTAssertEqual(ok?.index, 3)
        XCTAssertEqual(ok?.raw, "ABC:DEF:3")
        XCTAssertEqual(SlotId("x:1")?.index, 1)
        XCTAssertEqual(SlotId("x:5")?.index, 5)
        for bad in ["x:0", "x:6", "x", "x:a", ":3", ""] { XCTAssertNil(SlotId(bad), bad) }
    }

    func testVersionMonotonic() {
        XCTAssertTrue(shouldApply(incoming: 1, current: nil))
        XCTAssertTrue(shouldApply(incoming: 3, current: 3))
        XCTAssertTrue(shouldApply(incoming: 4, current: 3))
        XCTAssertFalse(shouldApply(incoming: 2, current: 3))
    }
}
