# MyCon Learn

A locally hosted Vietnamese flashcard application for practicing reading and writing with strict diacritic validation.

## Features

- **Bidirectional Practice** - Quiz in both directions: English → Vietnamese and Vietnamese → English
- **Strict Diacritic Validation** - Enforces correct tone marks (e.g., "ma" ≠ "má") with Unicode NFC normalization
- **Unlimited Tries** - Keep trying until you get it right or give up
- **3-Level Hint System** - Progressive hints: word shapes → first letters → full answer
- **Mastery Tracking** - Mark cards as mastered and reset mastery per category
- **Progress Tracking** - Tracks success/fail counts and overall accuracy per card
- **Topic-Based Learning** - 12 built-in vocabulary topics, filterable by category
- **Password Protection** - Optional cookie-based session authentication for hosted deployments
- **Add Cards via UI** - Expand your vocabulary through the web interface
- **One-Click Launch** - `run.py` starts the server and opens your browser automatically

## Requirements

- Python 3.11+
- Poetry

## Getting Started

```bash
# Clone the repository
git clone <repository-url>
cd mycon_learn

# Install dependencies
poetry install

# Seed the database with initial vocabulary
poetry run python seed_db.py

# Launch the app (starts server + opens browser)
poetry run python run.py
```

The app will be available at http://127.0.0.1:8000.

### Alternative: Development Mode

```bash
# Start with hot-reload for development
poetry run uvicorn app.main:app --reload
```

## Configuration

Copy `.env.example` to `.env` and customize:

| Variable | Default | Description |
|---|---|---|
| `DATABASE_URL` | `sqlite:///./mycon_learn.db` | SQLAlchemy connection string |
| `APP_PASSWORD` | *(empty)* | Set to enable password-protected login |
| `HOST` | `0.0.0.0` | Server bind host |
| `PORT` | `8000` | Server bind port |
| `DEBUG` | `false` | Enables `/docs` and `/redoc` when true |
| `CORS_ORIGINS` | `*` | Comma-separated allowed origins |

Authentication is disabled when `APP_PASSWORD` is empty. Sessions are in-memory and reset on restart.

## Tech Stack

- **Backend:** FastAPI + SQLAlchemy 2.0 + Pydantic v2
- **Database:** SQLite (default), PostgreSQL supported via `DATABASE_URL`
- **Frontend:** Vue.js 3 (CDN) + TailwindCSS (CDN) — single-file, no build step
- **Testing:** pytest

## Vocabulary Topics

12 built-in CSV topics are included in the `vocab/` directory:

greetings, food, common verbs, family, times, texting phrases, feelings, questions, responses, numbers, places, daily life

### CSV Format

```csv
vietnamese,english[,category][,difficulty_level]
xin chào,hello,greetings,1
tạm biệt,goodbye,greetings,1
```

If `category` is omitted, the filename stem is used (e.g., `common_verbs.csv` → `"common verbs"`). Duplicate rows (same vietnamese + english) are skipped on load.

### Loading Vocabulary

- Use the Topic Manager in the UI (click the gear icon)
- Call `POST /api/topics/sync` to load all CSV files at once
- Call `POST /api/topics/load` with `{ "filename": "greetings.csv" }` to load a specific file

## API Endpoints

All `/api/*` endpoints require authentication when `APP_PASSWORD` is set.

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Health check (no auth required) |
| GET | `/api/card/random` | Get random flashcard (`?mode=eng_to_viet\|viet_to_eng&category=...`) |
| POST | `/api/check` | Validate answer `{ card_id, user_input, record_result?, mark_mastered? }` |
| POST | `/api/give_up` | Reveal answer and record failure `{ card_id }` |
| POST | `/api/hint` | Get hint `{ card_id, hint_level: 1-3 }` + `?mode=...` |
| POST | `/api/card` | Add new card `{ vietnamese, english, category?, difficulty_level? }` |
| GET | `/api/cards` | List cards (`?category=&skip=&limit=`) |
| DELETE | `/api/cards` | Delete all cards |
| GET | `/api/stats` | Get learning statistics |
| POST | `/api/mastery/reset` | Reset mastery status `{ category? }` |
| GET | `/api/topics` | List available CSV files in `vocab/` |
| GET | `/api/categories` | List categories in database |
| POST | `/api/topics/load` | Load a CSV file `{ filename, clear_existing? }` |
| POST | `/api/topics/sync` | Sync all CSV files to database |

## Vietnamese Input

For typing Vietnamese diacritics, install a Vietnamese keyboard on your OS:
- **Windows:** Settings → Time & Language → Language → Add Vietnamese (Telex)
- **macOS:** System Preferences → Keyboard → Input Sources → Add Vietnamese

With Telex input, type `ngayf` to produce `ngày`.

## Running Tests

```bash
poetry run pytest tests/ -v
```

## Deployment

### Local Network

```bash
# Accessible from other devices on your network
poetry run uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Access from phone/tablet at `http://YOUR_PC_IP:8000`.

### Railway

1. Push to GitHub
2. Connect repo at [railway.app](https://railway.app)
3. Set `APP_PASSWORD` environment variable
4. Deploy

### Render

1. Push to GitHub
2. Create Web Service at [render.com](https://render.com)
3. Set build command: `pip install poetry && poetry install`
4. Set start command: `poetry run uvicorn app.main:app --host 0.0.0.0 --port $PORT`
5. Set `APP_PASSWORD` environment variable

## License

MIT
