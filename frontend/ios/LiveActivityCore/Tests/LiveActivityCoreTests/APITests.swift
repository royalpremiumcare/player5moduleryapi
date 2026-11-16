import XCTest
import Foundation
#if canImport(FoundationNetworking)
import FoundationNetworking
#endif
@testable import LiveActivityCore

final class FakeTransport: HTTPTransport {
    var requests: [URLRequest] = []
    var responses: [(Data, Int)] = []
    var failWith: Error?
    func send(_ request: URLRequest) async throws -> (Data, Int) {
        requests.append(request)
        if let e = failWith { throw e }
        return responses.isEmpty ? (Data(), 204) : responses.removeFirst()
    }
}

final class MemorySecrets: SecretStore {
    var values: [String: String] = [:]
    func read(_ key: String) -> String? { values[key] }
    func write(_ key: String, _ value: String) { values[key] = value }
    func delete(_ key: String) { values[key] = nil }
}

func makeAPI(_ t: FakeTransport = FakeTransport(), _ s: MemorySecrets = MemorySecrets())
    -> (LiveActivityAPI, FakeTransport, MemorySecrets, UserDefaults) {
    let d = UserDefaults(suiteName: "la.test.\(UUID().uuidString)")!
    return (LiveActivityAPI(transport: t, secrets: s, defaults: d), t, s, d)
}

func body(_ r: URLRequest) -> [String: Any] {
    (try! JSONSerialization.jsonObject(with: r.httpBody!)) as! [String: Any]
}

final class APITests: XCTestCase {
    func register(_ api: LiveActivityAPI) async throws -> Bool {
        try await api.register(apiBaseUrl: "https://plannapp.co/", jwt: "JWT", osVersion: "18.1",
                               appBuild: "42", fcmToken: nil, pushToStartToken: "pts", activitiesEnabled: true)
    }

    func testRegisterSendsBearerOnceAndStoresSecret() async throws {
        let (api, t, s, _) = makeAPI()
        t.responses = [(Data(#"{"device_secret":"SEC"}"#.utf8), 200)]
        let stored = try await register(api)
        XCTAssertTrue(stored)
        XCTAssertEqual(s.read("la.device_secret"), "SEC")
        let r = t.requests[0]
        XCTAssertEqual(r.url?.absoluteString, "https://plannapp.co/api/live-activities/devices")
        XCTAssertEqual(r.httpMethod, "POST")
        XCTAssertEqual(r.value(forHTTPHeaderField: "Authorization"), "Bearer JWT")
        XCTAssertEqual(r.value(forHTTPHeaderField: "Content-Type"), "application/json")
        let b = body(r)
        XCTAssertEqual(Set(b.keys), ["device_id", "os_version", "app_build", "fcm_token", "push_to_start_token", "activities_enabled"])
        XCTAssertEqual(b["device_id"] as? String, api.deviceId())
        XCTAssertEqual(b["activities_enabled"] as? Bool, true)
        XCTAssertTrue(b["fcm_token"] is NSNull)
        XCTAssertEqual(api.apiBaseUrl, "https://plannapp.co")
    }

    func testRegisterWithNullSecretKeepsExisting() async throws {
        let (api, t, s, _) = makeAPI()
        s.write("la.device_secret", "OLD")
        t.responses = [(Data(#"{"device_secret":null}"#.utf8), 200)]
        let stored = try await register(api)
        XCTAssertFalse(stored)
        XCTAssertEqual(s.read("la.device_secret"), "OLD")
    }

    func testRegisterNon2xxThrowsHttp() async {
        let (api, t, _, _) = makeAPI()
        t.responses = [(Data(), 401)]
        do { _ = try await register(api); XCTFail() } catch APIError.http(let c) { XCTAssertEqual(c, 401) } catch { XCTFail("\(error)") }
    }

    func testTokenPostUsesPersistedBaseUrlAndSecretOnly() async throws {
        let (api, t, s, d) = makeAPI()
        d.set("https://plannapp.co", forKey: "la.api_base_url")
        s.write("la.device_secret", "SEC")
        try await api.postToken(slotIndex: 2, activityId: "act", updateToken: "tok")
        let r = t.requests[0]
        XCTAssertEqual(r.url?.absoluteString, "https://plannapp.co/api/live-activities/token")
        XCTAssertNil(r.value(forHTTPHeaderField: "Authorization"))
        XCTAssertEqual(r.value(forHTTPHeaderField: "X-Plann-Device-Secret"), "SEC")
        let b = body(r)
        XCTAssertEqual(Set(b.keys), ["device_id", "slot_index", "activity_id", "update_token"])
        XCTAssertEqual(b["slot_index"] as? Int, 2)
    }

    func testTokenPostWithoutSecretThrowsNoSecret() async {
        let (api, t, _, d) = makeAPI()
        d.set("https://plannapp.co", forKey: "la.api_base_url")
        do { try await api.postToken(slotIndex: 1, activityId: "a", updateToken: "t"); XCTFail() }
        catch APIError.noSecret {} catch { XCTFail("\(error)") }
        XCTAssertTrue(t.requests.isEmpty)
    }

    func testMissingBaseUrlThrowsNoBaseUrl() async {
        let (api, _, s, _) = makeAPI()
        s.write("la.device_secret", "SEC")
        do { try await api.postToken(slotIndex: 1, activityId: "a", updateToken: "t"); XCTFail() }
        catch APIError.noBaseUrl {} catch { XCTFail("\(error)") }
    }

    func reportFixture(enabled: Bool = true) -> ReconcileReport {
        ReconcileReport(device_id: "dev", activities_enabled: enabled, complete: true, push_to_start_token: nil,
                        slots: [ActivitySnapshotDTO(slot_index: 1, activity_id: "A1", state: "active")])
    }

    func testReconcileRequestHasSecretHeaderAndNoAuthorization() async throws {
        let (api, t, s, d) = makeAPI()
        d.set("https://plannapp.co", forKey: "la.api_base_url")
        s.write("la.device_secret", "SEC")
        t.responses = [(Data(#"{"end":[2],"end_activities":["X"],"start_locally":[]}"#.utf8), 200)]
        let resp = try await api.reconcile(reportFixture())
        XCTAssertEqual(resp.end, [2])
        let r = t.requests[0]
        XCTAssertEqual(r.url?.absoluteString, "https://plannapp.co/api/live-activities/reconcile")
        XCTAssertNil(r.value(forHTTPHeaderField: "Authorization"))
        XCTAssertEqual(r.value(forHTTPHeaderField: "X-Plann-Device-Secret"), "SEC")
        let b = body(r)
        XCTAssertEqual(Set(b.keys), ["device_id", "activities_enabled", "complete", "push_to_start_token", "slots"])
        let slot = (b["slots"] as! [[String: Any]])[0]
        XCTAssertEqual(Set(slot.keys), ["slot_index", "activity_id", "state"])
    }

    func testReportCarriesActivitiesEnabledFlag() throws {
        let data = try JSONEncoder().encode(reportFixture(enabled: false))
        let j = try JSONSerialization.jsonObject(with: data) as! [String: Any]
        XCTAssertEqual(j["activities_enabled"] as? Bool, false)
    }

    func testResponseMissingKeysDecodeEmpty() throws {
        let r = try JSONDecoder().decode(ReconcileResponse.self, from: Data("{}".utf8))
        XCTAssertEqual(r.end, [])
        XCTAssertEqual(r.end_activities, [])
        XCTAssertTrue(r.start_locally.isEmpty)
    }

    func testStartLocallyDecodes() throws {
        let json = #"{"start_locally":[{"slot_index":1,"content":{"phase":"upcoming","startEpoch":1.0,"endEpoch":2.0,"startLabel":"a","endLabel":"b","customerDisplay":null,"serviceName":"s","staffName":null,"version":1,"appointmentId":"x"},"attributes":{"slotId":"d:1","orgId":"o"},"stale_epoch":null,"relevance":50}]}"#
        let r = try JSONDecoder().decode(ReconcileResponse.self, from: Data(json.utf8))
        XCTAssertEqual(r.start_locally[0].attributes?["slotId"], "d:1")
        XCTAssertNil(r.start_locally[0].stale_epoch)
        XCTAssertEqual(r.start_locally[0].relevance, 50)
    }

    func testEndInstructionsBySlotAndById() throws {
        let cur = [ActivitySnapshot(slotIndex: 1, activityId: "A1", state: "active"),
                   ActivitySnapshot(slotIndex: 1, activityId: "OLD", state: "active"),
                   ActivitySnapshot(slotIndex: 2, activityId: "B", state: "active")]
        let resp = try JSONDecoder().decode(ReconcileResponse.self, from: Data(#"{"end":[2],"end_activities":["OLD"]}"#.utf8))
        XCTAssertEqual(endInstructions(response: resp, current: cur), ["B", "OLD"])
    }

    func testUnregisterClearsSecretEvenIfServerFails() async {
        let (api, t, s, d) = makeAPI()
        d.set("https://plannapp.co", forKey: "la.api_base_url")
        s.write("la.device_secret", "SEC")
        t.failWith = URLError(.notConnectedToInternet)
        await api.unregister(jwt: "JWT")
        XCTAssertNil(s.read("la.device_secret"))
        XCTAssertEqual(t.requests[0].httpMethod, "DELETE")
        XCTAssertEqual(t.requests[0].value(forHTTPHeaderField: "Authorization"), "Bearer JWT")
        XCTAssertEqual(t.requests[0].url?.path, "/api/live-activities/devices/\(api.deviceId())")
    }

    func testDeviceIdStableAcrossCalls() {
        let (api, t, s, d) = makeAPI()
        let a = api.deviceId()
        XCTAssertEqual(a, api.deviceId())
        XCTAssertEqual(s.read("la.device_id"), a)
        XCTAssertEqual(LiveActivityAPI(transport: t, secrets: s, defaults: d).deviceId(), a)
    }
}
