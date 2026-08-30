"""Parity tests for the offline iOS bundle.

ios/MyConLearn/www/local-api.js reimplements the FastAPI backend in JavaScript
so the iPhone app runs without a server. These tests replay one request
sequence through both implementations and require identical responses, so a
change to app/main.py that is not mirrored in the shim fails the suite.

The JS side runs under the JavaScriptCore shell that ships with macOS.
"""

import json
import subprocess
import unicodedata
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models import Card

PROJECT_ROOT = Path(__file__).resolve().parent.parent
WWW_DIR = PROJECT_ROOT / "ios" / "MyConLearn" / "www"
JS_DIR = Path(__file__).resolve().parent / "js"
JSC = Path(
    "/System/Library/Frameworks/JavaScriptCore.framework/Versions/A/Helpers/jsc"
)

pytestmark = pytest.mark.skipif(
    not JSC.exists(), reason="requires the JavaScriptCore shell (macOS only)"
)

# Fields that legitimately differ between the two runs.
VOLATILE_FIELDS = {"last_reviewed"}

engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


def load_bundled_vocab() -> dict:
    """Parse the generated vocab.js back into Python."""
    source = (WWW_DIR / "vocab.js").read_text(encoding="utf-8")
    start = source.index("window.MYCON_VOCAB = ") + len("window.MYCON_VOCAB = ")
    end = source.rindex("};") + 1
    return json.loads(source[start:end])


def strip_diacritics(text: str) -> str:
    decomposed = unicodedata.normalize("NFD", text)
    return unicodedata.normalize(
        "NFC", "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    )


def build_request_sequence(cards: list[dict]) -> list[dict]:
    """One ordered script of API calls, replayed identically by both sides.

    Order matters: later assertions depend on the state earlier calls leave
    behind, so both implementations must be driven through the same sequence.
    """
    specs: list[dict] = []

    def add(name, method, url, body=None):
        specs.append({"name": name, "method": method, "url": url, "body": body})

    add("topics", "GET", "/api/topics")
    add("categories", "GET", "/api/categories")
    add("cards:initial", "GET", "/api/cards?limit=1000")

    # Exhaustive hint coverage: every card, both directions, all three levels.
    for index, card in enumerate(cards, start=1):
        for mode in ("eng_to_viet", "viet_to_eng"):
            for level in (1, 2, 3):
                add(
                    f"hint:{index}:{mode}:{level}",
                    "POST",
                    f"/api/hint?mode={mode}",
                    {"card_id": index, "hint_level": level},
                )

    # Answer checking: exact matches, tolerated formatting, and the wrong
    # answers that exercise the word-by-word partial credit path.
    for index, card in enumerate(cards, start=1):
        vietnamese, english = card["v"], card["e"]
        variants = [
            ("viet", vietnamese),
            ("eng", english),
            ("loud", f"  {vietnamese.upper()}  "),
            ("nodiacritics", strip_diacritics(vietnamese)),
            ("firstword", vietnamese.split()[0] if vietnamese.split() else ""),
            ("nonsense", "zzz qqq"),
        ]
        for label, user_input in variants:
            add(
                f"check:{index}:{label}",
                "POST",
                "/api/check",
                {"card_id": index, "user_input": user_input, "record_result": False},
            )

    # Hint clamping outside the documented 1-3 range.
    add("hint:clamp:low", "POST", "/api/hint?mode=eng_to_viet", {"card_id": 1, "hint_level": 0})
    add("hint:clamp:high", "POST", "/api/hint?mode=eng_to_viet", {"card_id": 1, "hint_level": 9})

    # Unknown card ids must 404 on both sides.
    add("hint:missing", "POST", "/api/hint?mode=eng_to_viet", {"card_id": 99999, "hint_level": 1})
    add("check:missing", "POST", "/api/check", {"card_id": 99999, "user_input": "x"})
    add("giveup:missing", "POST", "/api/give_up", {"card_id": 99999})

    # Record results the way the UI does, then confirm the persisted counters
    # and mastery flags agree.
    for index in range(1, 11):
        add(
            f"record:{index}",
            "POST",
            "/api/check",
            {
                "card_id": index,
                "user_input": cards[index - 1]["v"],
                "record_result": True,
                "mark_mastered": True,
            },
        )
    for index in range(11, 16):
        add(f"giveup:{index}", "POST", "/api/give_up", {"card_id": index})
    for index in range(16, 21):
        add(
            f"wrong:{index}",
            "POST",
            "/api/check",
            {"card_id": index, "user_input": "definitely wrong", "record_result": True},
        )

    add("cards:after-progress", "GET", "/api/cards?limit=1000")
    add("cards:by-category", "GET", "/api/cards?limit=1000&category=family")
    add("cards:paged", "GET", "/api/cards?skip=5&limit=7")
    add("stats", "GET", "/api/stats")

    add("reset:category", "POST", "/api/mastery/reset", {"category": "greetings"})
    add("cards:after-category-reset", "GET", "/api/cards?limit=1000")
    add("reset:all", "POST", "/api/mastery/reset", {"category": None})
    add("cards:after-full-reset", "GET", "/api/cards?limit=1000")

    add(
        "card:create",
        "POST",
        "/api/card",
        {"vietnamese": "cảm ơn nhiều", "english": "thanks a lot", "category": "greetings", "difficulty_level": 2},
    )
    add("categories:after-create", "GET", "/api/categories")
    add("cards:after-create", "GET", "/api/cards?limit=1000")

    return specs


def run_javascript(specs: list[dict], tmp_path: Path) -> list[dict]:
    """Replay the sequence through local-api.js under JavaScriptCore."""
    requests_js = tmp_path / "requests.js"
    requests_js.write_text(
        "var REQUESTS = " + json.dumps(specs, ensure_ascii=True) + ";\n",
        encoding="utf-8",
    )

    completed = subprocess.run(
        [
            str(JSC),
            str(JS_DIR / "harness.js"),
            str(WWW_DIR / "vocab.js"),
            str(WWW_DIR / "local-api.js"),
            str(requests_js),
            str(JS_DIR / "driver.js"),
        ],
        capture_output=True,
        text=True,
        timeout=300,
    )

    if completed.returncode != 0:
        raise AssertionError(
            f"jsc exited {completed.returncode}\nstdout:\n{completed.stdout}\nstderr:\n{completed.stderr}"
        )
    if "---RESULT---" not in completed.stdout:
        raise AssertionError(f"driver produced no results:\n{completed.stdout}\n{completed.stderr}")

    return json.loads(completed.stdout.split("---RESULT---", 1)[1])


def run_python(specs: list[dict], client: TestClient) -> list[dict]:
    results = []
    for spec in specs:
        if spec["method"] == "GET":
            response = client.get(spec["url"])
        else:
            response = client.post(spec["url"], json=spec["body"] or {})
        results.append({"name": spec["name"], "status": response.status_code, "data": response.json()})
    return results


def scrub(value):
    """Drop timestamps, which are wall-clock and never equal across runs."""
    if isinstance(value, dict):
        return {k: scrub(v) for k, v in value.items() if k not in VOLATILE_FIELDS}
    if isinstance(value, list):
        return [scrub(item) for item in value]
    return value


@pytest.fixture(scope="module")
def parity_results():
    """Run the whole sequence once through each implementation."""
    import tempfile

    vocab = load_bundled_vocab()
    cards = vocab["cards"]
    specs = build_request_sequence(cards)

    app.dependency_overrides[get_db] = override_get_db
    Base.metadata.create_all(bind=engine)
    try:
        db = TestingSessionLocal()
        db.add_all(
            Card(
                vietnamese=card["v"],
                english=card["e"],
                category=card["c"],
                difficulty_level=card["d"],
            )
            for card in cards
        )
        db.commit()
        db.close()

        with TestClient(app) as client:
            python_results = run_python(specs, client)

        with tempfile.TemporaryDirectory() as tmp:
            js_results = run_javascript(specs, Path(tmp))
    finally:
        Base.metadata.drop_all(bind=engine)
        app.dependency_overrides.pop(get_db, None)

    return specs, python_results, js_results


def test_bundle_covers_every_csv_row(parity_results):
    """Every card the loader would import is present in the bundle."""
    vocab = load_bundled_vocab()
    assert len(vocab["cards"]) == sum(topic["count"] for topic in vocab["topics"])
    assert len(vocab["topics"]) == len(list((PROJECT_ROOT / "vocab").glob("*.csv")))


def test_sequences_line_up(parity_results):
    specs, python_results, js_results = parity_results
    assert len(js_results) == len(specs)
    assert [r["name"] for r in js_results] == [r["name"] for r in python_results]


def test_offline_shim_matches_backend(parity_results):
    specs, python_results, js_results = parity_results

    mismatches = []
    for expected, actual in zip(python_results, js_results):
        name = expected["name"]

        expected_data = scrub(expected["data"])
        actual_data = scrub(actual["data"])

        # DISTINCT ordering is up to SQLite; only the set of categories is
        # part of the contract.
        if name.startswith("categories"):
            expected_data = sorted(expected_data)
            actual_data = sorted(actual_data)

        if expected["status"] != actual["status"] or expected_data != actual_data:
            mismatches.append(
                f"{name}\n"
                f"  python  {expected['status']} {json.dumps(expected_data, ensure_ascii=False)}\n"
                f"  javascript {actual['status']} {json.dumps(actual_data, ensure_ascii=False)}"
            )

    assert not mismatches, f"{len(mismatches)} of {len(specs)} responses differ:\n" + "\n".join(
        mismatches[:20]
    )
