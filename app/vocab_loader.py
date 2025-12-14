"""Load vocabulary from CSV files in the vocab/ directory."""

import csv
from pathlib import Path
from sqlalchemy.orm import Session

from app.models import Card

VOCAB_DIR = Path(__file__).parent.parent / "vocab"


def get_available_topics() -> list[dict]:
    """List all available vocabulary topics from CSV files.

    Returns list of dicts with 'name' (display name) and 'filename'.
    """
    if not VOCAB_DIR.exists():
        return []

    topics = []
    for csv_file in sorted(VOCAB_DIR.glob("*.csv")):
        # Convert filename to display name: "common_words.csv" -> "Common Words"
        display_name = csv_file.stem.replace("_", " ").replace("-", " ").title()
        topics.append({
            "name": display_name,
            "filename": csv_file.name,
            "path": str(csv_file),
        })

    return topics


def load_csv_file(filepath: Path) -> list[dict]:
    """Load vocabulary from a CSV file.

    Expected CSV format:
    vietnamese,english
    xin chào,hello
    tạm biệt,goodbye

    Optional columns: category, difficulty_level
    """
    cards = []

    with open(filepath, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)

        # Normalize column names (lowercase, strip whitespace)
        if reader.fieldnames:
            reader.fieldnames = [name.lower().strip() for name in reader.fieldnames]

        for row in reader:
            # Skip empty rows
            vietnamese = row.get("vietnamese", "").strip()
            english = row.get("english", "").strip()

            if not vietnamese or not english:
                continue

            cards.append({
                "vietnamese": vietnamese,
                "english": english,
                "category": row.get("category", "").strip() or None,
                "difficulty_level": int(row.get("difficulty_level", 1) or 1),
            })

    return cards


def load_topic_into_db(filename: str, db: Session, clear_existing: bool = False) -> int:
    """Load a vocabulary CSV file into the database.

    Args:
        filename: Name of the CSV file in vocab/ directory
        db: Database session
        clear_existing: If True, removes all existing cards first

    Returns:
        Number of cards loaded
    """
    filepath = VOCAB_DIR / filename

    if not filepath.exists():
        raise FileNotFoundError(f"Vocabulary file not found: {filename}")

    if clear_existing:
        db.query(Card).delete()
        db.commit()

    # Use filename (without extension) as category if not specified in CSV
    default_category = filepath.stem.replace("_", " ").replace("-", " ")

    cards_data = load_csv_file(filepath)
    count = 0

    for data in cards_data:
        # Check if card already exists (same vietnamese + english)
        existing = db.query(Card).filter(
            Card.vietnamese == data["vietnamese"],
            Card.english == data["english"],
        ).first()

        if existing:
            continue

        card = Card(
            vietnamese=data["vietnamese"],
            english=data["english"],
            category=data["category"] or default_category,
            difficulty_level=data["difficulty_level"],
        )
        db.add(card)
        count += 1

    db.commit()
    return count


def sync_all_topics(db: Session) -> dict:
    """Sync all CSV files from vocab/ directory to database.

    Returns dict with counts per topic.
    """
    results = {}

    for topic in get_available_topics():
        count = load_topic_into_db(topic["filename"], db)
        results[topic["name"]] = count

    return results
