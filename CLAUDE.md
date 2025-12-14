# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

MyCon Learn is a locally hosted web application for practicing Vietnamese reading and writing. It presents flashcards bidirectionally (English ↔ Vietnamese) with strict diacritic/tone validation.

## Tech Stack

- **Backend:** Python 3.11+ with FastAPI
- **Database:** SQLite (for spaced repetition tracking)
- **Frontend:** HTML5, Vanilla JS or Vue.js (CDN), TailwindCSS (CDN) - no npm/webpack build steps
- **Package Manager:** Poetry

## Commands

```bash
# Install dependencies
poetry install

# Seed the database with initial vocabulary
poetry run python seed_db.py

# Run the FastAPI server
poetry run uvicorn app.main:app --reload

# Run tests
poetry run pytest tests/ -v
```

## Architecture

### Project Structure
```
app/
  database.py     # SQLite/SQLAlchemy setup
  models.py       # Card model
  schemas.py      # Pydantic request/response schemas
  main.py         # FastAPI app and endpoints
  vocab_loader.py # CSV vocabulary file loader
static/
  index.html      # Vue.js frontend
vocab/            # CSV vocabulary files (one per topic)
  greetings.csv
  food.csv
  family.csv
  common_verbs.csv
tests/
  test_api.py     # API tests
seed_db.py        # Database seeding script
```

### API Endpoints
- `GET /api/card/random` - Returns random flashcard (query params: `?mode=eng_to_viet|viet_to_eng`, `?category=...`)
- `POST /api/check` - Validates user answer `{ card_id: int, user_input: string }` → `{ correct: bool, diff: string }`
- `POST /api/hint` - Get hint for current card `{ card_id: int, hint_level: 1-3 }`
- `POST /api/card` - Add new word to deck
- `GET /api/cards` - List all cards
- `GET /api/stats` - Get learning statistics
- `GET /api/topics` - List available CSV files in vocab/ folder
- `GET /api/categories` - List categories in database
- `POST /api/topics/load` - Load a CSV file `{ filename: string, clear_existing: bool }`
- `POST /api/topics/sync` - Sync all CSV files to database

### Data Model
Cards table with: id, vietnamese, english, category, difficulty_level, success_count, fail_count, last_reviewed

### Key Requirements
- **Strict diacritic validation:** Answers must match exact Vietnamese spelling including all tone marks (e.g., "ma" ≠ "má")
- **String normalization:** Trim whitespace, lowercase before comparison
- **Hint system:** Three levels (syllable count → first letters → definition/context)
- **Vietnamese input:** Users should use OS-level Telex keyboard input