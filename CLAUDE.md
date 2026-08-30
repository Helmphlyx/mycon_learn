pythonrun.py# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

MyCon Learn is a locally hosted web application for practicing Vietnamese reading and writing. It presents flashcards bidirectionally (English ↔ Vietnamese) with strict diacritic/tone validation.

## Tech Stack

- **Backend:** Python 3.11+ with FastAPI, SQLAlchemy 2.0, Pydantic v2
- **Database:** SQLite (default); `DATABASE_URL` env var can point to PostgreSQL
- **Frontend:** Single-file Vue.js app at `static/index.html` (CDN, no build step)
- **Package Manager:** Poetry

## Commands

```bash
# Install dependencies
poetry install

# Run the FastAPI server (development)
poetry run uvicorn app.main:app --reload

# Run the app locally and auto-open browser
poetry run python run.py

# Seed the database with initial vocabulary
poetry run python seed_db.py

# Run all tests
poetry run pytest tests/ -v

# Run a single test
poetry run pytest tests/test_api.py::TestCheckAnswer::test_wrong_diacritics_is_incorrect -v

# Rebuild the offline bundle the iOS app ships (after editing static/index.html or vocab/)
poetry run python scripts/build_ios_www.py

# Redraw the iOS app icon
poetry run python scripts/generate_app_icon.py
```

## Configuration

Settings are loaded from a `.env` file (see `.env.example`) via `app/config.py` using `pydantic-settings`:

| Variable | Default | Description |
|---|---|---|
| `DATABASE_URL` | `sqlite:///./mycon_learn.db` | SQLAlchemy connection string |
| `APP_PASSWORD` | `` (empty) | Set to enable password-protected login |
| `HOST` | `0.0.0.0` | Server bind host |
| `PORT` | `8000` | Server bind port |
| `DEBUG` | `false` | Enables `/docs` and `/redoc` when true |
| `CORS_ORIGINS` | `*` | Comma-separated allowed origins |

Authentication is disabled when `APP_PASSWORD` is empty. Sessions are in-memory (reset on restart).

## Architecture

### Key Files

```
app/
  main.py         # FastAPI app, all endpoints, answer normalization logic
  config.py       # Settings via pydantic-settings (lru_cache singleton)
  auth.py         # Cookie-based session auth, login page HTML
  database.py     # SQLAlchemy engine and get_db dependency
  models.py       # Card ORM model
  schemas.py      # Pydantic request/response schemas
  vocab_loader.py # CSV loading logic; VOCAB_DIR = project_root/vocab/
static/
  index.html      # Entire Vue.js frontend
vocab/            # CSV vocabulary files (one per topic/category)
ios/
  MyConLearn.xcodeproj/
  MyConLearn/
    MyConLearnApp.swift          # SwiftUI entry point
    WebAppView.swift             # WKWebView host
    AppContentSchemeHandler.swift # Serves www/ over myconlearn://
    ProgressStore.swift          # Mirrors progress outside the web view
    www/                         # Offline bundle; index.html + vocab.js are generated
      local-api.js               # JS port of the backend (see below)
  README.md                      # Xcode setup and the weekly reinstall
scripts/
  build_ios_www.py  # static/index.html + vocab/*.csv -> ios/MyConLearn/www/
  generate_app_icon.py
tests/
  test_api.py                # Uses in-memory SQLite; no auth (APP_PASSWORD unset)
  test_offline_parity.py     # Backend vs. the JS port, via JavaScriptCore
  test_ios_project.py        # Bundle freshness and Xcode project integrity
  test_webview_integration.py # Drives the real bundle in a WKWebView
```

### API Endpoints

All `/api/*` endpoints require authentication when `APP_PASSWORD` is set.

- `GET /health` — Health check (no auth required)
- `GET /api/card/random` — Random flashcard (`?mode=eng_to_viet|viet_to_eng`, `?category=...`)
- `POST /api/check` — Validate answer `{ card_id, user_input, record_result? }` → `{ correct, expected, diff }`
- `POST /api/give_up` — Reveal answer and record failure `{ card_id }`
- `POST /api/hint` — Get hint `{ card_id, hint_level: 1-3 }` + `?mode=...`
- `POST /api/card` — Add a card
- `GET /api/cards` — List cards (`?category=`, `?skip=`, `?limit=`)
- `DELETE /api/cards` — Delete all cards
- `GET /api/stats` — Aggregate success/fail counts and accuracy
- `GET /api/topics` — List CSV files in `vocab/`
- `GET /api/categories` — List distinct categories from DB
- `POST /api/topics/load` — Load a CSV `{ filename, clear_existing }`
- `POST /api/topics/sync` — Upsert all CSVs into DB

### Answer Validation Logic (`main.py`)

- `normalize_vietnamese`: strips whitespace, lowercases, applies Unicode NFC normalization
- `/api/check` accepts either the Vietnamese **or** English answer as correct
- Incorrect answers are **not** recorded in stats by default; pass `"record_result": true` to force recording
- `/api/give_up` always records a failure

### The iOS App Shares This Logic

The iPhone app has no server: `ios/MyConLearn/www/local-api.js` reimplements
`main.py`'s endpoints in JavaScript and answers the page's `fetch` calls from
vocabulary compiled into `www/vocab.js`.

**Changing answer validation, hints, or any `/api/*` response means changing
both.** `tests/test_offline_parity.py` replays thousands of requests through
the FastAPI app and the JavaScript port and fails on any difference.

`static/index.html` is shared verbatim — the build script rewrites a handful of
exact strings in it (the CDN tags and the viewport meta) and aborts if it
cannot find them, so editing those lines means updating `SUBSTITUTIONS` in
`scripts/build_ios_www.py`.

### Hint Levels

1. Word shapes (`___ ____`)
2. First letters (`x__ c___`)
3. Full answer revealed

### Vocabulary CSV Format

```csv
vietnamese,english[,category][,difficulty_level]
xin chào,hello,greetings,1
```

If `category` is omitted, the filename stem is used (e.g., `common_verbs.csv` → `"common verbs"`). Duplicate rows (same vietnamese + english) are skipped on load.
