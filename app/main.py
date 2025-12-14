import unicodedata
from datetime import datetime
from enum import Enum
from typing import Annotated

from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import engine, get_db, Base
from app.models import Card
from app.schemas import (
    CardCreate,
    CardResponse,
    CardQuiz,
    CheckRequest,
    CheckResponse,
    GiveUpRequest,
    GiveUpResponse,
    HintRequest,
    HintResponse,
    TopicInfo,
    TopicLoadRequest,
    TopicLoadResponse,
)
from app.vocab_loader import get_available_topics, load_topic_into_db, sync_all_topics, VOCAB_DIR

Base.metadata.create_all(bind=engine)

app = FastAPI(title="MyCon Learn", description="Vietnamese flashcard learning app")

app.mount("/static", StaticFiles(directory="static"), name="static")


class QuizMode(str, Enum):
    ENG_TO_VIET = "eng_to_viet"
    VIET_TO_ENG = "viet_to_eng"


def normalize_vietnamese(text: str) -> str:
    """Normalize Vietnamese text for comparison.

    - Strips whitespace
    - Converts to lowercase
    - Normalizes Unicode (NFC form for consistent diacritic handling)
    """
    text = text.strip().lower()
    text = unicodedata.normalize("NFC", text)
    return text


def generate_diff(expected: str, actual: str) -> str:
    """Generate a simple diff showing character-level differences."""
    diff_parts = []
    max_len = max(len(expected), len(actual))

    for i in range(max_len):
        exp_char = expected[i] if i < len(expected) else ""
        act_char = actual[i] if i < len(actual) else ""

        if exp_char != act_char:
            if exp_char and act_char:
                diff_parts.append(f"'{act_char}'->'{exp_char}'")
            elif exp_char:
                diff_parts.append(f"missing '{exp_char}'")
            else:
                diff_parts.append(f"extra '{act_char}'")

    return ", ".join(diff_parts) if diff_parts else None


def generate_hint(card: Card, mode: QuizMode, hint_level: int) -> str:
    """Generate hints based on hint level.

    Level 1: Show syllable count with underscores
    Level 2: Show first letter of each word
    Level 3: Show the answer (give up)
    """
    answer = card.vietnamese if mode == QuizMode.ENG_TO_VIET else card.english
    words = answer.split()

    if hint_level == 1:
        return " ".join("_" * len(word) for word in words)
    elif hint_level == 2:
        return " ".join(word[0] + "_" * (len(word) - 1) for word in words)
    else:  # level 3
        return answer


@app.get("/")
async def root():
    return FileResponse("static/index.html")


@app.get("/api/card/random", response_model=CardQuiz)
async def get_random_card(
    mode: Annotated[QuizMode, Query()] = QuizMode.ENG_TO_VIET,
    category: Annotated[str | None, Query()] = None,
    db: Session = Depends(get_db),
):
    """Get a random card for quiz.

    Args:
        mode: Quiz direction (eng_to_viet or viet_to_eng)
        category: Optional category filter (e.g., "greetings", "food")
    """
    query = db.query(Card)

    if category:
        query = query.filter(Card.category == category)

    card = query.order_by(func.random()).first()

    if not card:
        raise HTTPException(status_code=404, detail="No cards available")

    prompt = card.english if mode == QuizMode.ENG_TO_VIET else card.vietnamese

    return CardQuiz(id=card.id, prompt=prompt, mode=mode.value, category=card.category)


@app.post("/api/check", response_model=CheckResponse)
async def check_answer(request: CheckRequest, db: Session = Depends(get_db)):
    """Check if the user's answer is correct.

    Performs strict comparison with normalized strings.
    Only updates stats when record_result=True (for final attempts).
    Does not reveal the answer on incorrect attempts (use /api/give_up for that).
    """
    card = db.query(Card).filter(Card.id == request.card_id).first()

    if not card:
        raise HTTPException(status_code=404, detail="Card not found")

    user_normalized = normalize_vietnamese(request.user_input)
    viet_normalized = normalize_vietnamese(card.vietnamese)
    eng_normalized = normalize_vietnamese(card.english)

    # Check against Vietnamese (eng_to_viet mode)
    correct_viet = user_normalized == viet_normalized
    # Check against English (viet_to_eng mode)
    correct_eng = user_normalized == eng_normalized

    correct = correct_viet or correct_eng

    # Only record stats on final attempt (when user gets it right or explicitly records)
    if request.record_result or correct:
        card.last_reviewed = datetime.utcnow()
        if correct:
            card.success_count += 1
        else:
            card.fail_count += 1
        db.commit()

    # Only reveal the expected answer if correct
    expected = None
    diff = None
    if correct:
        expected = card.vietnamese if correct_viet else card.english

    return CheckResponse(
        correct=correct,
        expected=expected,
        user_input=request.user_input,
        diff=diff,
    )


@app.post("/api/give_up", response_model=GiveUpResponse)
async def give_up(request: GiveUpRequest, db: Session = Depends(get_db)):
    """Give up on a card and reveal the answer. Records a failure."""
    card = db.query(Card).filter(Card.id == request.card_id).first()

    if not card:
        raise HTTPException(status_code=404, detail="Card not found")

    # Record the failure
    card.last_reviewed = datetime.utcnow()
    card.fail_count += 1
    db.commit()

    return GiveUpResponse(
        answer=card.vietnamese,  # Primary answer (most common use case)
        vietnamese=card.vietnamese,
        english=card.english,
    )


@app.post("/api/hint", response_model=HintResponse)
async def get_hint(
    request: HintRequest,
    mode: Annotated[QuizMode, Query()] = QuizMode.ENG_TO_VIET,
    db: Session = Depends(get_db),
):
    """Get a hint for the current card."""
    card = db.query(Card).filter(Card.id == request.card_id).first()

    if not card:
        raise HTTPException(status_code=404, detail="Card not found")

    hint_level = max(1, min(3, request.hint_level))
    hint = generate_hint(card, mode, hint_level)

    return HintResponse(hint=hint, hint_level=hint_level)


@app.post("/api/card", response_model=CardResponse)
async def create_card(card: CardCreate, db: Session = Depends(get_db)):
    """Add a new card to the deck."""
    db_card = Card(
        vietnamese=card.vietnamese,
        english=card.english,
        category=card.category,
        difficulty_level=card.difficulty_level,
    )
    db.add(db_card)
    db.commit()
    db.refresh(db_card)
    return db_card


@app.get("/api/cards", response_model=list[CardResponse])
async def list_cards(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
):
    """List all cards in the deck."""
    cards = db.query(Card).offset(skip).limit(limit).all()
    return cards


@app.get("/api/stats")
async def get_stats(db: Session = Depends(get_db)):
    """Get overall learning statistics."""
    total_cards = db.query(Card).count()
    total_success = db.query(func.sum(Card.success_count)).scalar() or 0
    total_fail = db.query(func.sum(Card.fail_count)).scalar() or 0
    total_attempts = total_success + total_fail

    return {
        "total_cards": total_cards,
        "total_attempts": total_attempts,
        "total_success": total_success,
        "total_fail": total_fail,
        "accuracy": round(total_success / total_attempts * 100, 1) if total_attempts > 0 else 0,
    }


# ============================================================================
# Topic/Vocabulary File Management
# ============================================================================


@app.get("/api/topics", response_model=list[TopicInfo])
async def list_topics():
    """List all available vocabulary topics from CSV files in vocab/ directory."""
    topics = get_available_topics()
    return [TopicInfo(name=t["name"], filename=t["filename"]) for t in topics]


@app.get("/api/categories")
async def list_categories(db: Session = Depends(get_db)):
    """List all categories currently in the database."""
    categories = db.query(Card.category).distinct().filter(Card.category.isnot(None)).all()
    return [c[0] for c in categories]


@app.post("/api/topics/load", response_model=TopicLoadResponse)
async def load_topic(request: TopicLoadRequest, db: Session = Depends(get_db)):
    """Load vocabulary from a CSV file into the database.

    Args:
        filename: Name of the CSV file in vocab/ directory
        clear_existing: If True, removes all existing cards first
    """
    try:
        count = load_topic_into_db(request.filename, db, request.clear_existing)
        action = "Replaced all cards with" if request.clear_existing else "Added"
        return TopicLoadResponse(
            filename=request.filename,
            cards_loaded=count,
            message=f"{action} {count} cards from {request.filename}",
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.post("/api/topics/sync")
async def sync_topics(db: Session = Depends(get_db)):
    """Sync all CSV files from vocab/ directory to database.

    Adds new cards without removing existing ones.
    """
    if not VOCAB_DIR.exists():
        VOCAB_DIR.mkdir(parents=True)
        return {"message": "Created vocab/ directory. Add CSV files and sync again.", "loaded": {}}

    results = sync_all_topics(db)
    total = sum(results.values())
    return {
        "message": f"Synced {total} new cards from {len(results)} files",
        "loaded": results,
    }


@app.delete("/api/cards")
async def clear_all_cards(db: Session = Depends(get_db)):
    """Delete all cards from the database."""
    count = db.query(Card).count()
    db.query(Card).delete()
    db.commit()
    return {"message": f"Deleted {count} cards"}
