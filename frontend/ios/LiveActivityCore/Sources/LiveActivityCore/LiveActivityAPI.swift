import Foundation
#if canImport(FoundationNetworking)
import FoundationNetworking
#endif

public protocol HTTPTransport {
    func send(_ request: URLRequest) async throws -> (Data, Int)
}

public protocol SecretStore {
    func read(_ key: String) -> String?
    func write(_ key: String, _ value: String)
    func delete(_ key: String)
}

public enum APIError: Error {
    case noSecret, noBaseUrl, http(Int)
}

public final class LiveActivityAPI {
    static let deviceIdKey = "la.device_id"
    static let secretKey = "la.device_secret"
    static let baseUrlKey = "la.api_base_url"
    static let secretHeader = "X-Plann-Device-Secret"

    private let transport: HTTPTransport
    private let secrets: SecretStore
    private let defaults: UserDefaults

    public init(transport: HTTPTransport, secrets: SecretStore, defaults: UserDefaults) {
        self.transport = transport
        self.secrets = secrets
        self.defaults = defaults
    }

    public var apiBaseUrl: String? {
        get { defaults.string(forKey: Self.baseUrlKey) }
        set {
            if let v = newValue { defaults.set(Self.trimmed(v), forKey: Self.baseUrlKey) }
            else { defaults.removeObject(forKey: Self.baseUrlKey) }
        }
    }

    private static func trimmed(_ s: String) -> String {
        var s = s
        while s.hasSuffix("/") { s.removeLast() }
        return s
    }

    /// True once a register stored a device secret (and until unregister deletes it).
    public var hasSecret: Bool {
        guard let s = secrets.read(Self.secretKey) else { return false }
        return !s.isEmpty
    }

    public func deviceId() -> String {
        if let id = secrets.read(Self.deviceIdKey), !id.isEmpty { return id }
        let id = UUID().uuidString
        secrets.write(Self.deviceIdKey, id)
        return id
    }

    private func makeRequest(_ method: String, _ path: String, body: Data?) throws -> URLRequest {
        guard let base = apiBaseUrl, !base.isEmpty, let url = URL(string: base + "/api/live-activities" + path)
        else { throw APIError.noBaseUrl }
        var r = URLRequest(url: url)
        r.httpMethod = method
        if let body = body {
            r.httpBody = body
            r.setValue("application/json", forHTTPHeaderField: "Content-Type")
        }
        return r
    }

    private func perform(_ request: URLRequest) async throws -> Data {
        let (data, status) = try await transport.send(request)
        guard (200..<300).contains(status) else { throw APIError.http(status) }
        return data
    }

    private func secretRequest(_ method: String, _ path: String, json: Data) throws -> URLRequest {
        guard let secret = secrets.read(Self.secretKey), !secret.isEmpty else { throw APIError.noSecret }
        var r = try makeRequest(method, path, body: json)
        r.setValue(secret, forHTTPHeaderField: Self.secretHeader)
        return r
    }

    private struct RegisterBody: Encodable {
        let device_id: String, os_version: String, app_build: String
        let fcm_token: String?, push_to_start_token: String?, activities_enabled: Bool
        enum CodingKeys: String, CodingKey {
            case device_id, os_version, app_build, fcm_token, push_to_start_token, activities_enabled
        }
        func encode(to encoder: Encoder) throws {
            var c = encoder.container(keyedBy: CodingKeys.self)
            try c.encode(device_id, forKey: .device_id)
            try c.encode(os_version, forKey: .os_version)
            try c.encode(app_build, forKey: .app_build)
            try c.encode(fcm_token, forKey: .fcm_token)
            try c.encode(push_to_start_token, forKey: .push_to_start_token)
            try c.encode(activities_enabled, forKey: .activities_enabled)
        }
    }

    private struct RegisterResponse: Decodable { let device_secret: String? }

    /// Returns true when the server issued a new device secret (stored).
    @discardableResult
    public func register(apiBaseUrl: String, jwt: String, osVersion: String, appBuild: String,
                         fcmToken: String?, pushToStartToken: String?, activitiesEnabled: Bool) async throws -> Bool {
        self.apiBaseUrl = apiBaseUrl
        let payload = RegisterBody(device_id: deviceId(), os_version: osVersion, app_build: appBuild,
                                   fcm_token: fcmToken, push_to_start_token: pushToStartToken,
                                   activities_enabled: activitiesEnabled)
        var r = try makeRequest("POST", "/devices", body: try JSONEncoder().encode(payload))
        r.setValue("Bearer \(jwt)", forHTTPHeaderField: "Authorization")
        let data = try await perform(r)
        if let secret = (try? JSONDecoder().decode(RegisterResponse.self, from: data))?.device_secret {
            secrets.write(Self.secretKey, secret)
            return true
        }
        return false
    }

    private struct TokenBody: Encodable {
        let device_id: String, slot_index: Int, activity_id: String, update_token: String
    }

    public func postToken(slotIndex: Int, activityId: String, updateToken: String) async throws {
        let body = TokenBody(device_id: deviceId(), slot_index: slotIndex,
                             activity_id: activityId, update_token: updateToken)
        _ = try await perform(try secretRequest("POST", "/token", json: try JSONEncoder().encode(body)))
    }

    public func reconcile(_ report: ReconcileReport) async throws -> ReconcileResponse {
        let data = try await perform(try secretRequest("POST", "/reconcile", json: try JSONEncoder().encode(report)))
        return try JSONDecoder().decode(ReconcileResponse.self, from: data)
    }

    public func unregister(jwt: String) async {
        defer { secrets.delete(Self.secretKey) }
        guard var r = try? makeRequest("DELETE", "/devices/\(deviceId())", body: nil) else { return }
        r.setValue("Bearer \(jwt)", forHTTPHeaderField: "Authorization")
        _ = try? await perform(r)
    }
}
