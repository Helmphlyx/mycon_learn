"""End-to-end checks against a real WKWebView.

Builds a small macOS harness from the app's own AppContentSchemeHandler and
ProgressStore, loads the shipping bundle in a WebView, answers a card, then
throws the WebView's storage away and confirms the progress comes back from the
native mirror — the guarantee that matters when the free signing certificate is
refreshed every seven days.

Needs the Swift toolchain from the Command Line Tools; skipped when absent.
"""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
WWW_DIR = PROJECT_ROOT / "ios" / "MyConLearn" / "www"
APP_DIR = PROJECT_ROOT / "ios" / "MyConLearn"
HARNESS_SOURCE = Path(__file__).resolve().parent / "webview" / "main.swift"

pytestmark = pytest.mark.skipif(
    shutil.which("xcrun") is None or shutil.which("swiftc") is None,
    reason="requires the Swift toolchain (macOS Command Line Tools)",
)


@pytest.fixture(scope="module")
def webview_report(tmp_path_factory) -> dict:
    workspace = tmp_path_factory.mktemp("webview")
    harness = workspace / "harness"

    build = subprocess.run(
        [
            "xcrun",
            "swiftc",
            "-o",
            str(harness),
            str(HARNESS_SOURCE),
            str(APP_DIR / "AppContentSchemeHandler.swift"),
            str(APP_DIR / "ProgressStore.swift"),
            "-framework",
            "WebKit",
            "-framework",
            "AppKit",
        ],
        capture_output=True,
        text=True,
        timeout=300,
    )
    if build.returncode != 0:
        pytest.fail(f"harness failed to compile:\n{build.stdout}\n{build.stderr}")

    # The harness keeps its saved progress here and deletes its defaults suite
    # on the way out, so a run starts clean and leaves nothing behind.
    scratch = workspace / "storage"
    scratch.mkdir()

    run = subprocess.run(
        [str(harness), str(WWW_DIR), str(scratch)],
        capture_output=True,
        text=True,
        timeout=180,
    )
    if run.returncode != 0 or "---RESULT---" not in run.stdout:
        pytest.fail(f"harness failed:\n{run.stdout}\n{run.stderr}")

    return json.loads(run.stdout.split("---RESULT---", 1)[1])


class TestPageLoads:
    def test_vue_app_mounts(self, webview_report):
        assert webview_report["practice"]["vueMounted"]

    def test_bundled_stylesheet_applies(self, webview_report):
        """Tailwind is vendored, so the background must resolve without a CDN."""
        assert webview_report["practice"]["tailwindApplied"] == "rgb(243, 244, 246)"

    def test_all_vocabulary_is_reachable(self, webview_report):
        """Every bundled card must be reachable from inside the app."""
        vocab = json.loads(
            (WWW_DIR / "vocab.js").read_text(encoding="utf-8").split("= ", 1)[1].rsplit(";", 2)[0]
        )
        practice = webview_report["practice"]
        assert practice["cardCount"] == len(vocab["cards"])
        assert practice["topicCount"] == len(vocab["topics"])
        assert practice["categoryCount"] == len({c["c"] for c in vocab["cards"]})

    def test_custom_scheme_grants_local_storage(self, webview_report):
        """The reason the page is not served from file://."""
        assert webview_report["practice"]["localStorageWorks"], webview_report["practice"].get(
            "localStorageError"
        )


class TestPractising:
    def test_prompt_comes_from_the_deck(self, webview_report):
        assert webview_report["practice"]["promptMatchesACard"]

    def test_hints_render(self, webview_report):
        hint = webview_report["practice"]["hintLevelOne"]
        assert hint and set(hint) <= set("_()0123456789 ")

    def test_correct_answer_is_accepted_and_recorded(self, webview_report):
        practice = webview_report["practice"]
        assert practice["feedback"] == "Correct! Word mastered."
        assert practice["savedToLocalStorage"]
        assert practice["masteredCount"] == 1


class TestProgressSurvives:
    def test_progress_reaches_native_storage(self, webview_report):
        assert webview_report["nativeSavesDuringPractice"] > 0
        assert webview_report["nativeMirrorWritten"]

    def test_progress_returns_after_web_storage_is_lost(self, webview_report):
        """A reinstall or a WebKit purge must not cost the learner anything."""
        restore = webview_report["restore"]
        assert restore["vueMounted"]
        assert restore["restoredFromNative"]
        assert restore["masteredCount"] == 1
        # The harness practises whichever card the app happened to deal.
        assert restore["masteredWords"] == [webview_report["practice"]["answeredVietnamese"]]
