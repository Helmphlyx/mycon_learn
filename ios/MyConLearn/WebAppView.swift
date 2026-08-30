import SwiftUI
import WebKit

/// Hosts the offline web app bundled in `www/`.
///
/// There is no server: `www/local-api.js` answers the `/api/*` calls the page
/// makes, out of the vocabulary compiled into `www/vocab.js`.
struct WebAppView: UIViewRepresentable {

    /// Matches --mycon-bg in mobile.css, so there is no flash of white before
    /// the page paints and no mismatched strip behind the keyboard.
    private static let backgroundColor = UIColor(
        red: 0.953, green: 0.957, blue: 0.965, alpha: 1
    )

    func makeCoordinator() -> Coordinator {
        Coordinator()
    }

    func makeUIView(context: Context) -> WKWebView {
        let controller = WKUserContentController()
        controller.add(context.coordinator, name: ProgressStore.messageName)
        // Hand the last saved progress to the page before any of its own
        // scripts run, so local-api.js can recover if the WebView's storage
        // was cleared out from under it.
        controller.addUserScript(
            WKUserScript(
                source: ProgressStore.shared.restoreScript(),
                injectionTime: .atDocumentStart,
                forMainFrameOnly: true
            )
        )

        let configuration = WKWebViewConfiguration()
        configuration.userContentController = controller
        // The default (non-ephemeral) store is what makes localStorage outlive
        // a relaunch.
        configuration.websiteDataStore = .default()

        guard let wwwDirectory = Bundle.main.url(forResource: "www", withExtension: nil) else {
            assertionFailure(
                "www/ is missing from the bundle — run scripts/build_ios_www.py"
            )
            return WKWebView(frame: .zero, configuration: configuration)
        }

        configuration.setURLSchemeHandler(
            AppContentSchemeHandler(rootDirectory: wwwDirectory),
            forURLScheme: AppContentSchemeHandler.scheme
        )

        let webView = WKWebView(frame: .zero, configuration: configuration)
        webView.navigationDelegate = context.coordinator
        webView.isOpaque = true
        webView.backgroundColor = Self.backgroundColor
        webView.scrollView.backgroundColor = Self.backgroundColor
        // The page handles insets itself; letting UIKit add its own would
        // double up the safe-area padding.
        webView.scrollView.contentInsetAdjustmentBehavior = .never
        webView.scrollView.keyboardDismissMode = .interactive
        // Single page, no history to swipe back to.
        webView.allowsBackForwardNavigationGestures = false

        webView.load(URLRequest(url: AppContentSchemeHandler.startURL))
        return webView
    }

    func updateUIView(_ webView: WKWebView, context: Context) {}

    static func dismantleUIView(_ webView: WKWebView, coordinator: Coordinator) {
        webView.configuration.userContentController
            .removeScriptMessageHandler(forName: ProgressStore.messageName)
    }

    final class Coordinator: NSObject, WKScriptMessageHandler, WKNavigationDelegate {
        func userContentController(
            _ userContentController: WKUserContentController,
            didReceive message: WKScriptMessage
        ) {
            guard
                message.name == ProgressStore.messageName,
                let json = message.body as? String
            else { return }

            ProgressStore.shared.save(json)
        }
    }
}
