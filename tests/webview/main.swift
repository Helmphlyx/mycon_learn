//
// Loads the real offline bundle in a WKWebView and drives it the way a
// learner would, then checks that progress survives losing the WebView's own
// storage. Compiled against the app's own AppContentSchemeHandler and
// ProgressStore, so it exercises the shipping code rather than a copy.
//
// Usage: harness <path to www directory>
// Prints a JSON report after a ---RESULT--- sentinel line.
//

import AppKit
import WebKit

let wwwPath = CommandLine.arguments.count > 1 ? CommandLine.arguments[1] : ""
guard !wwwPath.isEmpty else {
    FileHandle.standardError.write(Data("usage: harness <www directory>\n".utf8))
    exit(2)
}
let wwwDirectory = URL(fileURLWithPath: wwwPath, isDirectory: true)

// Progress is mirrored into a scratch directory rather than the real
// Application Support, so a run starts clean and leaves nothing behind.
let scratchDirectory = URL(
    fileURLWithPath: CommandLine.arguments.count > 2
        ? CommandLine.arguments[2]
        : NSTemporaryDirectory(),
    isDirectory: true
)
let store = ProgressStore(directory: scratchDirectory)

// Answers one card correctly, then reports what the page and its storage look
// like afterwards.
let practiceScript = """
function sleep(ms) { return new Promise(function (resolve) { setTimeout(resolve, ms); }); }

var report = {};

for (var i = 0; i < 200; i++) {
    if (document.querySelector('#app h2.text-4xl')) { break; }
    await sleep(25);
}

report.vueMounted = !!document.querySelector('#app h2.text-4xl');
report.restoreScriptInjected = typeof window.__MYCON_RESTORED__ !== 'undefined';
report.tailwindApplied = getComputedStyle(document.body).backgroundColor;

try {
    window.localStorage.setItem('__probe__', 'yes');
    report.localStorageWorks = window.localStorage.getItem('__probe__') === 'yes';
    window.localStorage.removeItem('__probe__');
} catch (error) {
    report.localStorageWorks = false;
    report.localStorageError = String(error);
}

var cards = await (await fetch('/api/cards?limit=1000')).json();
report.cardCount = cards.length;
report.categoryCount = (await (await fetch('/api/categories')).json()).length;
report.topicCount = (await (await fetch('/api/topics')).json()).length;

report.prompt = document.querySelector('#app h2.text-4xl').textContent.trim();
var card = cards.filter(function (c) { return c.english === report.prompt; })[0];
report.promptMatchesACard = !!card;
if (!card) { return report; }

var hint = await (await fetch('/api/hint?mode=eng_to_viet', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ card_id: card.id, hint_level: 1 })
})).json();
report.hintLevelOne = hint.hint;

var input = document.querySelector('#app form input[type=text]');
input.value = card.vietnamese;
input.dispatchEvent(new Event('input', { bubbles: true }));
document.querySelector('#app form').dispatchEvent(
    new Event('submit', { bubbles: true, cancelable: true })
);

await sleep(400);

var banner = document.querySelector('#app .border-l-4 p');
report.feedback = banner ? banner.textContent.trim() : null;
report.answeredVietnamese = card.vietnamese;
report.answeredEnglish = card.english;

var saved = window.localStorage.getItem('mycon.state.v1');
report.savedToLocalStorage = !!saved;
if (saved) {
    var parsed = JSON.parse(saved);
    report.masteredCount = Object.keys(parsed.progress).filter(function (key) {
        return parsed.progress[key].mastered;
    }).length;
}

return report;
"""

// Run after the WebView's own storage has been thrown away: the only place the
// mastered card can come from now is the native mirror.
let restoreScript = """
for (var i = 0; i < 200; i++) {
    if (document.querySelector('#app h2.text-4xl')) { break; }
    await sleep0(25);
}
function sleep0(ms) { return new Promise(function (resolve) { setTimeout(resolve, ms); }); }

var cards = await (await fetch('/api/cards?limit=1000')).json();
return {
    vueMounted: !!document.querySelector('#app h2.text-4xl'),
    restoredFromNative: window.__MYCON_RESTORED__ !== null,
    masteredCount: cards.filter(function (card) { return card.mastered; }).length,
    masteredWords: cards.filter(function (card) { return card.mastered; })
        .map(function (card) { return card.vietnamese; })
};
"""

final class Harness: NSObject, WKNavigationDelegate, WKScriptMessageHandler {
    private var webView: WKWebView?
    private var report: [String: Any] = [:]
    private var nativeSaveCount = 0
    private var stage = 0

    func run() {
        loadPage(script: practiceScript)
    }

    private func loadPage(script: String) {
        let controller = WKUserContentController()
        controller.add(self, name: ProgressStore.messageName)
        controller.addUserScript(
            WKUserScript(
                source: store.restoreScript(),
                injectionTime: .atDocumentStart,
                forMainFrameOnly: true
            )
        )

        let configuration = WKWebViewConfiguration()
        configuration.userContentController = controller
        // Non-persistent so each stage starts with empty web storage; stage two
        // then has nothing but the native mirror to recover from.
        configuration.websiteDataStore = .nonPersistent()
        configuration.setURLSchemeHandler(
            AppContentSchemeHandler(rootDirectory: wwwDirectory),
            forURLScheme: AppContentSchemeHandler.scheme
        )

        let webView = WKWebView(
            frame: NSRect(x: 0, y: 0, width: 390, height: 844),
            configuration: configuration
        )
        webView.navigationDelegate = self
        self.webView = webView

        pendingScript = script
        webView.load(URLRequest(url: AppContentSchemeHandler.startURL))
    }

    private var pendingScript = ""

    func webView(_ webView: WKWebView, didFinish navigation: WKNavigation!) {
        webView.callAsyncJavaScript(
            pendingScript,
            arguments: [:],
            in: nil,
            in: .page
        ) { result in
            switch result {
            case .success(let value):
                self.finishStage(with: value as? [String: Any] ?? [:])
            case .failure(let error):
                self.fail("stage \(self.stage) script failed: \(error)")
            }
        }
    }

    func webView(_ webView: WKWebView, didFail navigation: WKNavigation!, withError error: Error) {
        fail("navigation failed: \(error)")
    }

    func webView(
        _ webView: WKWebView,
        didFailProvisionalNavigation navigation: WKNavigation!,
        withError error: Error
    ) {
        fail("could not load \(AppContentSchemeHandler.startURL): \(error)")
    }

    func userContentController(
        _ userContentController: WKUserContentController,
        didReceive message: WKScriptMessage
    ) {
        guard let json = message.body as? String else { return }
        nativeSaveCount += 1
        store.save(json)
    }

    private func finishStage(with value: [String: Any]) {
        if stage == 0 {
            report["practice"] = value
            report["nativeSavesDuringPractice"] = nativeSaveCount
            report["nativeMirrorWritten"] = store.load() != nil
            stage = 1
            // Tear the old WebView down and start again with empty storage.
            webView?.configuration.userContentController
                .removeScriptMessageHandler(forName: ProgressStore.messageName)
            webView = nil
            loadPage(script: restoreScript)
        } else {
            report["restore"] = value
            emit()
        }
    }

    private func emit() {
        let data = try! JSONSerialization.data(withJSONObject: report, options: [.sortedKeys])
        print("---RESULT---")
        print(String(data: data, encoding: .utf8)!)
        exit(0)
    }

    private func fail(_ message: String) {
        FileHandle.standardError.write(Data((message + "\n").utf8))
        exit(1)
    }
}

let application = NSApplication.shared
application.setActivationPolicy(.accessory)

let harness = Harness()
harness.run()

DispatchQueue.main.asyncAfter(deadline: .now() + 60) {
    FileHandle.standardError.write(Data("timed out waiting for the web app\n".utf8))
    exit(1)
}

application.run()
