import XCTest
import Foundation
@testable import LiveActivityCore

final class PushToStartTokenTests: XCTestCase {
    func testFreshTokenWins() {
        XCTAssertEqual(pushToStartTokenToSend(fresh: "new", latest: "old", persisted: "older"), "new")
    }

    func testFallsBackToLatestThenPersisted() {
        XCTAssertEqual(pushToStartTokenToSend(fresh: nil, latest: "seen", persisted: "stored"), "seen")
        XCTAssertEqual(pushToStartTokenToSend(fresh: nil, latest: nil, persisted: "stored"), "stored")
    }

    func testEmptyValuesAreIgnored() {
        XCTAssertEqual(pushToStartTokenToSend(fresh: "", latest: "", persisted: "stored"), "stored")
        XCTAssertNil(pushToStartTokenToSend(fresh: "", latest: nil, persisted: ""))
    }

    func testNoTokenEverKnownSendsNil() {
        XCTAssertNil(pushToStartTokenToSend(fresh: nil, latest: nil, persisted: nil))
    }

    func testLastPushToStartTokenPersistsAcrossInstances() {
        let (api, _, s, d) = makeAPI()
        XCTAssertNil(api.lastPushToStartToken)
        api.lastPushToStartToken = "abc"
        let reopened = LiveActivityAPI(transport: FakeTransport(), secrets: s, defaults: d)
        XCTAssertEqual(reopened.lastPushToStartToken, "abc")
    }

    func testUnregisterKeepsLastPushToStartToken() async {
        // The push-to-start token belongs to the app install, not the user: the next login's
        // register must still send it.
        let (api, t, s, _) = makeAPI()
        api.apiBaseUrl = "https://plannapp.co"
        s.write("la.device_secret", "SEC")
        api.lastPushToStartToken = "abc"
        t.responses = [(Data(), 204)]
        await api.unregister(jwt: "JWT")
        XCTAssertEqual(api.lastPushToStartToken, "abc")
    }
}

private func requireSendable<T: Sendable>(_: T.Type) {}

final class SendableHedgeTests: XCTestCase {
    func testContentTypesAreSendable() {
        requireSendable(PlannPhase.self)
        requireSendable(PlannContentState.self)
        requireSendable(SlotId.self)
    }
}
