import Foundation
import WebKit

/// Serves the bundled `www/` directory over a custom URL scheme.
///
/// Loading the page straight from `file://` would leave it on an opaque
/// origin, where WebKit refuses `localStorage`. Giving the app a scheme of its
/// own means the page gets a normal, stable origin, so the progress it saves
/// is ordinary web storage that persists across launches.
///
/// Every response is produced synchronously inside `start`, so a task can
/// never be stopped part-way through being answered.
final class AppContentSchemeHandler: NSObject, WKURLSchemeHandler {
    static let scheme = "myconlearn"
    static let host = "app"

    /// The origin the page runs on. Stable for the life of the app, which is
    /// what keeps localStorage attached to the same bucket across updates.
    static var startURL: URL {
        URL(string: "\(scheme)://\(host)/index.html")!
    }

    private enum ContentError: Error {
        case notFound
    }

    private let rootDirectory: URL

    init(rootDirectory: URL) {
        self.rootDirectory = rootDirectory.standardizedFileURL
    }

    func webView(_ webView: WKWebView, start task: WKURLSchemeTask) {
        guard let url = task.request.url, let data = contents(for: url) else {
            task.didFailWithError(ContentError.notFound)
            return
        }

        let response = HTTPURLResponse(
            url: url,
            statusCode: 200,
            httpVersion: "HTTP/1.1",
            headerFields: [
                "Content-Type": Self.mimeType(for: url),
                "Content-Length": String(data.count),
                "Cache-Control": "no-cache",
            ]
        )!

        task.didReceive(response)
        task.didReceive(data)
        task.didFinish()
    }

    func webView(_ webView: WKWebView, stop task: WKURLSchemeTask) {}

    private func contents(for url: URL) -> Data? {
        var path = url.path
        if path.isEmpty || path == "/" {
            path = "/index.html"
        }

        let resolved = rootDirectory.appendingPathComponent(path).standardizedFileURL
        // Refuse anything that climbs out of the bundled directory.
        guard resolved.path.hasPrefix(rootDirectory.path) else { return nil }

        return try? Data(contentsOf: resolved)
    }

    private static func mimeType(for url: URL) -> String {
        switch url.pathExtension.lowercased() {
        case "html": return "text/html; charset=utf-8"
        case "js": return "text/javascript; charset=utf-8"
        case "css": return "text/css; charset=utf-8"
        case "json": return "application/json; charset=utf-8"
        case "png": return "image/png"
        case "svg": return "image/svg+xml"
        default: return "application/octet-stream"
        }
    }
}
