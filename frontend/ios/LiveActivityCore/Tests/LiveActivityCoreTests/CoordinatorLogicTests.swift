import XCTest
import Foundation
#if canImport(FoundationNetworking)
import FoundationNetworking
#endif
@testable import LiveActivityCore

final class CoordinatorLogicTests: XCTestCase {
    // MARK: report state strings

    func testReportStatePassesKnownStatesThrough() {
        for s in ["active", "stale", "pending", "ended", "dismissed"] {
            XCTAssertEqual(reportState(described: s), s)
        }
    }

    func testReportStateTreatsUnknownAsActive() {
        XCTAssertEqual(reportState(described: "somethingNew"), "active")
        XCTAssertEqual(reportState(described: ""), "active")
    }

    // MARK: snapshots from attributes.slotId

    func testSnapshotParsesSlotIndexFromSlotId() {
        let s = ActivitySnapshot(slotId: "DEV-1:3", activityId: "A", state: "stale")
        XCTAssertEqual(s, ActivitySnapshot(slotIndex: 3, activityId: "A", state: "stale"))
    }

    func testSnapshotRejectsUnparseableSlotId() {
        XCTAssertNil(ActivitySnapshot(slotId: "DEV-1", activityId: "A", state: "active"))
        XCTAssertNil(ActivitySnapshot(slotId: "DEV-1:9", activityId: "A", state: "active"))
    }

    // MARK: complete report

    func testCompleteReportListsEverySnapshotWithItsActivityId() throws {
        let cur = [ActivitySnapshot(slotIndex: 1, activityId: "A", state: "active"),
                   ActivitySnapshot(slotIndex: 2, activityId: "B", state: "dismissed")]
        let r = completeReport(deviceId: "DEV", activitiesEnabled: false, pushToStartToken: "pts", current: cur)
        XCTAssertTrue(r.complete)
        XCTAssertEqual(r.device_id, "DEV")
        XCTAssertFalse(r.activities_enabled)
        XCTAssertEqual(r.push_to_start_token, "pts")
        XCTAssertEqual(r.slots, [ActivitySnapshotDTO(slot_index: 1, activity_id: "A", state: "active"),
                                 ActivitySnapshotDTO(slot_index: 2, activity_id: "B", state: "dismissed")])
    }

    func testCompleteReportWithoutActivitiesSendsEmptySlotsAndNullToken() throws {
        let r = completeReport(deviceId: "DEV", activitiesEnabled: true, pushToStartToken: nil, current: [])
        let json = try JSONSerialization.jsonObject(with: JSONEncoder().encode(r)) as! [String: Any]
        XCTAssertEqual(json["complete"] as? Bool, true)
        XCTAssertEqual((json["slots"] as? [Any])?.count, 0)
        XCTAssertTrue(json["push_to_start_token"] is NSNull)
    }

    // MARK: local start attributes

    func decodeStart(_ json: String) throws -> LocalStart {
        try JSONDecoder().decode(LocalStart.self, from: Data(json.utf8))
    }

    let content = #"{"phase":"upcoming","startEpoch":1,"endEpoch":2,"startLabel":"a","endLabel":"b","customerDisplay":null,"serviceName":"s","staffName":null,"version":1,"appointmentId":"x"}"#

    func testLocalStartUsesServerAttributes() throws {
        let s = try decodeStart(#"{"slot_index":2,"relevance":50,"content":\#(content),"attributes":{"slotId":"DEV:2","orgId":"ORG"}}"#)
        XCTAssertEqual(localStartAttributes(s, deviceId: "DEV"), LocalStartAttributes(slotId: "DEV:2", orgId: "ORG"))
    }

    func testLocalStartWithoutAttributesBuildsSlotIdFromDevice() throws {
        let s = try decodeStart(#"{"slot_index":4,"relevance":50,"content":\#(content)}"#)
        XCTAssertEqual(localStartAttributes(s, deviceId: "DEV"), LocalStartAttributes(slotId: "DEV:4", orgId: ""))
    }

    func testLocalStartRejectsSlotIdThatDisagreesWithSlotIndex() throws {
        let s = try decodeStart(#"{"slot_index":2,"relevance":50,"content":\#(content),"attributes":{"slotId":"DEV:3","orgId":"ORG"}}"#)
        XCTAssertNil(localStartAttributes(s, deviceId: "DEV"))
    }

    func testLocalStartRejectsOutOfRangeSlotIndex() throws {
        let s = try decodeStart(#"{"slot_index":7,"relevance":50,"content":\#(content)}"#)
        XCTAssertNil(localStartAttributes(s, deviceId: "DEV"))
    }

    // MARK: identity strings

    func testPushTokenHexIsLowercaseTwoDigitsPerByte() {
        XCTAssertEqual(pushTokenHex(Data([0x00, 0x0a, 0xff, 0x10])), "000aff10")
        XCTAssertEqual(pushTokenHex(Data()), "")
    }

    func testAppBuildStringCombinesVersionAndBuild() {
        XCTAssertEqual(appBuildString(shortVersion: "6.4.2", build: "70"), "6.4.2 (70)")
        XCTAssertEqual(appBuildString(shortVersion: nil, build: nil), "? (?)")
    }

    // MARK: token retry policy

    func testTokenErrorsRetryOnlyTransientFailures() {
        XCTAssertTrue(isRetryableTokenError(URLError(.timedOut)))
        XCTAssertTrue(isRetryableTokenError(APIError.http(503)))
        XCTAssertTrue(isRetryableTokenError(APIError.http(429)))
        XCTAssertFalse(isRetryableTokenError(APIError.http(401)))
        XCTAssertFalse(isRetryableTokenError(APIError.http(422)))
        XCTAssertFalse(isRetryableTokenError(APIError.noSecret))
        XCTAssertFalse(isRetryableTokenError(APIError.noBaseUrl))
        XCTAssertFalse(isRetryableTokenError(CancellationError()))
    }

    // MARK: plugin error codes

    func testPluginErrorCodesNameTheFailureWithoutDetails() {
        XCTAssertEqual(pluginErrorCode(APIError.http(401)), "HTTP_401")
        XCTAssertEqual(pluginErrorCode(APIError.noSecret), "NO_SECRET")
        XCTAssertEqual(pluginErrorCode(APIError.noBaseUrl), "NO_BASE_URL")
        XCTAssertEqual(pluginErrorCode(URLError(.notConnectedToInternet)), "NETWORK")
    }

    // MARK: secret presence

    func testHasSecretFollowsRegisterAndUnregister() async throws {
        let (api, t, _, _) = makeAPI()
        XCTAssertFalse(api.hasSecret)
        t.responses = [(Data(#"{"device_secret":"SEC"}"#.utf8), 200)]
        _ = try await api.register(apiBaseUrl: "https://plannapp.co", jwt: "J", osVersion: "18", appBuild: "1",
                                   fcmToken: nil, pushToStartToken: nil, activitiesEnabled: true)
        XCTAssertTrue(api.hasSecret)
        await api.unregister(jwt: "J")
        XCTAssertFalse(api.hasSecret)
    }
}
