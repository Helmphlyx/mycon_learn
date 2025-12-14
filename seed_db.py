"""Seed the database with initial Vietnamese vocabulary."""

from app.database import SessionLocal, engine, Base
from app.models import Card

# Common Vietnamese words for beginners
SEED_DATA = [
    # Greetings
    {"vietnamese": "xin chào", "english": "hello", "category": "greetings"},
    {"vietnamese": "tạm biệt", "english": "goodbye", "category": "greetings"},
    {"vietnamese": "cảm ơn", "english": "thank you", "category": "greetings"},
    {"vietnamese": "xin lỗi", "english": "sorry", "category": "greetings"},

    # Time
    {"vietnamese": "hôm nay", "english": "today", "category": "time"},
    {"vietnamese": "ngày mai", "english": "tomorrow", "category": "time"},
    {"vietnamese": "hôm qua", "english": "yesterday", "category": "time"},
    {"vietnamese": "bây giờ", "english": "now", "category": "time"},
    {"vietnamese": "tuần", "english": "week", "category": "time"},
    {"vietnamese": "tháng", "english": "month", "category": "time"},
    {"vietnamese": "năm", "english": "year", "category": "time"},

    # Family
    {"vietnamese": "mẹ", "english": "mother", "category": "family"},
    {"vietnamese": "bố", "english": "father", "category": "family"},
    {"vietnamese": "anh", "english": "older brother", "category": "family"},
    {"vietnamese": "chị", "english": "older sister", "category": "family"},
    {"vietnamese": "em", "english": "younger sibling", "category": "family"},
    {"vietnamese": "ông", "english": "grandfather", "category": "family"},
    {"vietnamese": "bà", "english": "grandmother", "category": "family"},

    # Common words
    {"vietnamese": "nước", "english": "water", "category": "common"},
    {"vietnamese": "cơm", "english": "rice", "category": "food"},
    {"vietnamese": "nhà", "english": "house", "category": "common"},
    {"vietnamese": "người", "english": "person", "category": "common"},
    {"vietnamese": "yêu", "english": "love", "category": "common"},
    {"vietnamese": "đẹp", "english": "beautiful", "category": "common"},
    {"vietnamese": "tốt", "english": "good", "category": "common"},
    {"vietnamese": "xấu", "english": "bad", "category": "common"},

    # Verbs
    {"vietnamese": "ăn", "english": "eat", "category": "verbs"},
    {"vietnamese": "uống", "english": "drink", "category": "verbs"},
    {"vietnamese": "đi", "english": "go", "category": "verbs"},
    {"vietnamese": "đến", "english": "come", "category": "verbs"},
    {"vietnamese": "nói", "english": "speak", "category": "verbs"},
    {"vietnamese": "nghe", "english": "listen", "category": "verbs"},
    {"vietnamese": "đọc", "english": "read", "category": "verbs"},
    {"vietnamese": "viết", "english": "write", "category": "verbs"},
    {"vietnamese": "học", "english": "study", "category": "verbs"},
    {"vietnamese": "làm việc", "english": "work", "category": "verbs"},

    # Numbers
    {"vietnamese": "một", "english": "one", "category": "numbers"},
    {"vietnamese": "hai", "english": "two", "category": "numbers"},
    {"vietnamese": "ba", "english": "three", "category": "numbers"},
    {"vietnamese": "bốn", "english": "four", "category": "numbers"},
    {"vietnamese": "năm", "english": "five", "category": "numbers"},
    {"vietnamese": "sáu", "english": "six", "category": "numbers"},
    {"vietnamese": "bảy", "english": "seven", "category": "numbers"},
    {"vietnamese": "tám", "english": "eight", "category": "numbers"},
    {"vietnamese": "chín", "english": "nine", "category": "numbers"},
    {"vietnamese": "mười", "english": "ten", "category": "numbers"},
]


def seed_database():
    """Seed the database with initial vocabulary."""
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        existing_count = db.query(Card).count()
        if existing_count > 0:
            print(f"Database already has {existing_count} cards. Skipping seed.")
            return

        for item in SEED_DATA:
            card = Card(
                vietnamese=item["vietnamese"],
                english=item["english"],
                category=item.get("category"),
                difficulty_level=1,
            )
            db.add(card)

        db.commit()
        print(f"Successfully seeded {len(SEED_DATA)} cards!")

    finally:
        db.close()


if __name__ == "__main__":
    seed_database()
