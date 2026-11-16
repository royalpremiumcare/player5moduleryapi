import Foundation

/// Native HTTP for the Live Activity API (never the WebView or axios). Ephemeral session:
/// no cookies, no cache, so nothing from the web app's session rides along.
final class URLSessionTransport: HTTPTransport {
    static let timeout: TimeInterval = 15

    private let session: URLSession

    init() {
        let config = URLSessionConfiguration.ephemeral
        config.timeoutIntervalForRequest = Self.timeout
        config.timeoutIntervalForResource = Self.timeout
        config.httpShouldSetCookies = false
        config.httpCookieAcceptPolicy = .never
        config.urlCache = nil
        session = URLSession(configuration: config)
    }

    func send(_ request: URLRequest) async throws -> (Data, Int) {
        var r = request
        r.timeoutInterval = Self.timeout
        let (data, response) = try await session.data(for: r)
        guard let http = response as? HTTPURLResponse else { throw URLError(.badServerResponse) }
        return (data, http.statusCode)
    }
}
