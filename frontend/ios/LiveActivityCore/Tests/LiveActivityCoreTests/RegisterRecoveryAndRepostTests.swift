import XCTest
import Foundation
#if canImport(FoundationNetworking)
import FoundationNetworking
#endif
@testable import LiveActivityCore

final class RegisterRecoveryTests: XCTestCase {
    func ensure(_ api: LiveActivityAPI) async throws -> Bool {
        try await api.registerEnsuringSecret(apiBaseUrl: "https://plannapp.co", jwt: "JWT", osVersion: "17.0",
                                             appBuild: "1", fcmToken: "f", pushToStartToken: nil,
                                             activitiesEnabled: true)
    }

    func testNewSecretOnFirstAttemptSendsOneRequest() async throws {
        let (api, t, s, _) = makeAPI()
        t.responses = [(Data(#"{"device_secret":"SEC"}"#.utf8), 200)]
        let fresh = try await ensure(api)
        XCTAssertTrue(fresh)
        XCTAssertEqual(t.requests.count, 1)
        XCTAssertEqual(s.read("la.device_secret"), "SEC")
    }

    func testNullSecretWithStoredSecretKeepsIt() async throws {
        let (api, t, s, _) = makeAPI()
        s.write("la.device_secret", "OLD")
        t.responses = [(Data(#"{"device_secret":null}"#.utf8), 200)]
        let fresh = try await ensure(api)
        XCTAssertFalse(fresh)
        XCTAssertEqual(t.requests.count, 1)
        XCTAssertEqual(s.read("la.device_secret"), "OLD")
    }

    func testNullSecretWithoutStoredSecretDeletesDeviceAndRegistersAgain() async throws {
        let (api, t, s, _) = makeAPI()
        t.responses = [(Data(#"{"device_secret":null}"#.utf8), 200), (Data(), 204),
                       (Data(#"{"device_secret":"NEW"}"#.utf8), 200)]
        let fresh = try await ensure(api)
        XCTAssertTrue(fresh)
        XCTAssertEqual(t.requests.map { $0.httpMethod ?? "" }, ["POST", "DELETE", "POST"])
        XCTAssertEqual(t.requests[1].url?.path, "/api/live-activities/devices/\(api.deviceId())")
        XCTAssertEqual(t.requests[1].value(forHTTPHeaderField: "Authorization"), "Bearer JWT")
        XCTAssertEqual(s.read("la.device_secret"), "NEW")
    }

    func testRecoveryRunsOnlyOnce() async throws {
        let (api, t, _, _) = makeAPI()
        t.responses = [(Data(#"{"device_secret":null}"#.utf8), 200), (Data(), 204),
                       (Data(#"{"device_secret":null}"#.utf8), 200)]
        let fresh = try await ensure(api)
        XCTAssertFalse(fresh)
        XCTAssertEqual(t.requests.count, 3)
        XCTAssertFalse(api.hasSecret)
    }

    func testForgetSecretDeletesLocallyWithoutNetwork() {
        let (api, t, s, _) = makeAPI()
        s.write("la.device_secret", "SEC")
        api.forgetSecret()
        XCTAssertFalse(api.hasSecret)
        XCTAssertTrue(t.requests.isEmpty)
    }
}

final class TokenRepostTests: XCTestCase {
    func c(_ id: String, _ token: String?, _ state: String = "active", slot: Int = 1) -> TokenCandidate {
        TokenCandidate(slotIndex: slot, activityId: id, token: token, state: state)
    }

    func testRepostsAliveTokensNotYetPostedOrChanged() {
        let out = tokensToRepost([c("A", "t1"), c("B", "t2", "stale", slot: 2), c("C", "t3")],
                                 posted: ["A": "t1", "B": "old"])
        XCTAssertEqual(out, [c("B", "t2", "stale", slot: 2), c("C", "t3")])
    }

    func testSkipsMissingTokensAndEndedOrDismissedActivities() {
        let out = tokensToRepost([c("A", nil), c("B", ""), c("C", "t", "ended"), c("D", "t", "dismissed")],
                                 posted: [:])
        XCTAssertEqual(out, [])
    }
}
