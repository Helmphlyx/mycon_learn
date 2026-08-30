import Foundation

/// Keeps a copy of the learner's progress outside the WebView.
///
/// The page saves to `localStorage`, which lives in the app's data container
/// and normally survives installing a new build over an existing app — which
/// is what happens when the free seven-day signing certificate is refreshed.
/// WebKit's storage can still be evicted under disk pressure, though, so every
/// save is mirrored to a file in Application Support, which is not subject to
/// that eviction and is included in device backups. `local-api.js` reads the
/// mirror back whenever it finds `localStorage` empty.
///
/// Deleting the app from the Home Screen removes the container and with it
/// both copies.
final class ProgressStore {
    static let shared = ProgressStore()

    /// The `window.webkit.messageHandlers` name that `local-api.js` posts to.
    static let messageName = "myconProgress"

    private let fileURL: URL?

    /// - Parameter directory: where the mirror is written. Defaults to
    ///   Application Support inside the app container; the test harness passes
    ///   a scratch directory so a run leaves nothing behind.
    init(directory: URL? = nil) {
        let resolved = directory ?? (try? FileManager.default.url(
            for: .applicationSupportDirectory,
            in: .userDomainMask,
            appropriateFor: nil,
            create: true
        ))
        fileURL = resolved?.appendingPathComponent("mycon-progress.json")
    }

    func save(_ json: String) {
        guard let fileURL else { return }
        try? Data(json.utf8).write(to: fileURL, options: .atomic)
    }

    func load() -> String? {
        guard let fileURL, let data = try? Data(contentsOf: fileURL) else { return nil }
        return String(data: data, encoding: .utf8)
    }

    /// JavaScript run before the page loads, defining `window.__MYCON_RESTORED__`.
    ///
    /// The payload is base64 so that quotes, newlines and diacritics in the
    /// saved JSON cannot break out of the injected source.
    func restoreScript() -> String {
        guard let json = load() else {
            return "window.__MYCON_RESTORED__ = null;"
        }

        let encoded = Data(json.utf8).base64EncodedString()
        return """
        window.__MYCON_RESTORED__ = (function () {
            try {
                var binary = atob("\(encoded)");
                var bytes = new Uint8Array(binary.length);
                for (var i = 0; i < binary.length; i++) {
                    bytes[i] = binary.charCodeAt(i);
                }
                return new TextDecoder("utf-8").decode(bytes);
            } catch (error) {
                return null;
            }
        })();
        """
    }
}
