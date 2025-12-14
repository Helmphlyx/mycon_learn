# MyCon Learn

A locally hosted Vietnamese flashcard application for practicing reading and writing with strict diacritic validation.

## Features

- **Bidirectional Practice** - Quiz in both directions: English → Vietnamese and Vietnamese → English
- **Strict Diacritic Validation** - Enforces correct tone marks (e.g., "ma" ≠ "má")
- **3-Level Hint System** - Progressive hints from syllable count to first letters to full answer
- **Progress Tracking** - Tracks success/fail counts and overall accuracy
- **Topic-Based Learning** - Load vocabulary from CSV files and filter by topic/category
- **Add Cards via UI** - Easily expand your vocabulary through the web interface

## Requirements

- Python 3.11+
- Poetry

## Installation

```bash
# Clone the repository
git clone <repository-url>
cd mycon_learn

# Install dependencies
poetry install

# Seed the database with initial vocabulary (46 common words)
poetry run python seed_db.py
```

## Usage

```bash
# Start the server
poetry run uvicorn app.main:app --reload

# Open in browser
# http://127.0.0.1:8000
```

## Tech Stack

- **Backend:** FastAPI + SQLAlchemy + SQLite
- **Frontend:** Vue.js 3 (CDN) + TailwindCSS (CDN)
- **Testing:** pytest

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/card/random` | Get random flashcard (`?mode=...&category=...`) |
| POST | `/api/check` | Validate answer `{ card_id, user_input }` |
| POST | `/api/hint` | Get hint `{ card_id, hint_level: 1-3 }` |
| POST | `/api/card` | Add new card `{ vietnamese, english, category? }` |
| GET | `/api/cards` | List all cards |
| GET | `/api/stats` | Get learning statistics |
| GET | `/api/topics` | List CSV files in vocab/ folder |
| GET | `/api/categories` | List categories in database |
| POST | `/api/topics/load` | Load CSV file `{ filename, clear_existing? }` |
| POST | `/api/topics/sync` | Sync all CSV files to database |

## Loading Vocabulary from CSV Files

Place CSV files in the `vocab/` folder with this format:

```csv
vietnamese,english
xin chào,hello
tạm biệt,goodbye
```

Then either:
- Use the Topic Manager in the UI (click the gear icon)
- Call `POST /api/topics/sync` to load all files
- Call `POST /api/topics/load` with `{ "filename": "greetings.csv" }` to load a specific file

The filename (without extension) becomes the default category for cards in that file.

## Vietnamese Input

For typing Vietnamese diacritics, install a Vietnamese keyboard on your OS:
- **Windows:** Settings → Time & Language → Language → Add Vietnamese (Telex)
- **macOS:** System Preferences → Keyboard → Input Sources → Add Vietnamese

With Telex input, type `ngayf` to produce `ngày`.

## Running Tests

```bash
poetry run pytest tests/ -v
```

## License

MIT
