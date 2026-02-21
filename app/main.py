import logging
import unicodedata
from datetime import datetime
from enum import Enum
from typing import Annotated

from fastapi import FastAPI, Depends, HTTPException, Query, Request, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, RedirectResponse
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import get_settings
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
from app.auth import (
    require_auth,
    verify_password,
    generate_session_token,
    authenticated_sessions,
    is_authenticated,
    get_login_page,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

settings = get_settings()

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="MyCon Learn",
    description="Vietnamese flashcard learning app",
    docs_url="/docs" if settings.debug else None,  # Disable docs in production
    redoc_url="/redoc" if settings.debug else None,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="static"), name="static")


class QuizMode(str, Enum):
    ENG_TO_VIET = "eng_to_viet"
    VIET_TO_ENG = "viet_to_eng"


def normalize_vietnamese(text: str) -> str:
    """Normalize Vietnamese text for comparison."""
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
    """Generate hints based on hint level."""
    answer = card.vietnamese if mode == QuizMode.ENG_TO_VIET else card.english
    words = answer.split()

    if hint_level == 1:
        return " ".join("_" * len(word) for word in words)
    elif hint_level == 2:
        return " ".join(word[0] + "_" * (len(word) - 1) for word in words)
    else:
        return answer


# ============================================================================
# Health Check & Authentication
# ============================================================================


@app.get("/health")
async def health_check():
    """Health check endpoint for deployment platforms."""
    return {"status": "healthy", "version": "1.0.0"}


@app.get("/login")
async def login_page(request: Request):
    """Show login page."""
    if not settings.auth_enabled:
        return RedirectResponse(url="/", status_code=302)
    if is_authenticated(request):
        return RedirectResponse(url="/", status_code=302)
    return get_login_page()


@app.post("/login")
async def login(request: Request, password: str = Form(...)):
    """Process login."""
    if not settings.auth_enabled:
        return RedirectResponse(url="/", status_code=302)

    if verify_password(password):
        token = generate_session_token()
        authenticated_sessions.add(token)
        logger.info("User logged in successfully")
        response = RedirectResponse(url="/", status_code=302)
        response.set_cookie(
            key="session_token",
            value=token,
            httponly=True,
            secure=not settings.debug,  # Secure in production
            samesite="lax",
            max_age=86400 * 7,  # 7 days
        )
        return response
    else:
        logger.warning("Failed login attempt")
        return get_login_page(error="Invalid password")


@app.get("/logout")
async def logout(request: Request):
    """Log out and clear session."""
    token = request.cookies.get("session_token")
    if token and token in authenticated_sessions:
        authenticated_sessions.discard(token)
    response = RedirectResponse(url="/login", status_code=302)
    response.delete_cookie("session_token")
    return response


# ============================================================================
# Main App Routes (Protected)
# ============================================================================


@app.get("/")
async def root(request: Request):
    """Serve the main app (requires auth if enabled)."""
    if settings.auth_enabled and not is_authenticated(request):
        return RedirectResponse(url="/login", status_code=302)
    return FileResponse("static/index.html")


@app.get("/api/card/random", response_model=CardQuiz)
async def get_random_card(
    request: Request,
    mode: Annotated[QuizMode, Query()] = QuizMode.ENG_TO_VIET,
    category: Annotated[str | None, Query()] = None,
    db: Session = Depends(get_db),
    _: None = Depends(require_auth),
):
    """Get a random card for quiz."""
    query = db.query(Card)

    if category:
        query = query.filter(Card.category == category)

    card = query.order_by(func.random()).first()

    if not card:
        raise HTTPException(status_code=404, detail="No cards available")

    prompt = card.english if mode == QuizMode.ENG_TO_VIET else card.vietnamese

    return CardQuiz(id=card.id, prompt=prompt, mode=mode.value, category=card.category)


@app.post("/api/check", response_model=CheckResponse)
async def check_answer(
    request: Request,
    check_request: CheckRequest,
    db: Session = Depends(get_db),
    _: None = Depends(require_auth),
):
    """Check if the user's answer is correct."""
    card = db.query(Card).filter(Card.id == check_request.card_id).first()

    if not card:
        raise HTTPException(status_code=404, detail="Card not found")

    user_normalized = normalize_vietnamese(check_request.user_input)
    viet_normalized = normalize_vietnamese(card.vietnamese)
    eng_normalized = normalize_vietnamese(card.english)

    correct_viet = user_normalized == viet_normalized
    correct_eng = user_normalized == eng_normalized
    correct = correct_viet or correct_eng

    if check_request.record_result or correct:
        card.last_reviewed = datetime.utcnow()
        if correct:
            card.success_count += 1
        else:
            card.fail_count += 1
        db.commit()

    expected = None
    diff = None
    if correct:
        expected = card.vietnamese if correct_viet else card.english

    return CheckResponse(
        correct=correct,
        expected=expected,
        user_input=check_request.user_input,
        diff=diff,
    )


@app.post("/api/give_up", response_model=GiveUpResponse)
async def give_up(
    request: Request,
    give_up_request: GiveUpRequest,
    db: Session = Depends(get_db),
    _: None = Depends(require_auth),
):
    """Give up on a card and reveal the answer."""
    card = db.query(Card).filter(Card.id == give_up_request.card_id).first()

    if not card:
        raise HTTPException(status_code=404, detail="Card not found")

    card.last_reviewed = datetime.utcnow()
    card.fail_count += 1
    db.commit()

    return GiveUpResponse(
        answer=card.vietnamese,
        vietnamese=card.vietnamese,
        english=card.english,
    )


@app.post("/api/hint", response_model=HintResponse)
async def get_hint(
    request: Request,
    hint_request: HintRequest,
    mode: Annotated[QuizMode, Query()] = QuizMode.ENG_TO_VIET,
    db: Session = Depends(get_db),
    _: None = Depends(require_auth),
):
    """Get a hint for the current card."""
    card = db.query(Card).filter(Card.id == hint_request.card_id).first()

    if not card:
        raise HTTPException(status_code=404, detail="Card not found")

    hint_level = max(1, min(3, hint_request.hint_level))
    hint = generate_hint(card, mode, hint_level)

    return HintResponse(hint=hint, hint_level=hint_level)


@app.post("/api/card", response_model=CardResponse)
async def create_card(
    request: Request,
    card: CardCreate,
    db: Session = Depends(get_db),
    _: None = Depends(require_auth),
):
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
    logger.info(f"Created new card: {card.english} -> {card.vietnamese}")
    return db_card


@app.get("/api/cards", response_model=list[CardResponse])
async def list_cards(
    request: Request,
    skip: int = 0,
    limit: int = 100,
    category: Annotated[str | None, Query()] = None,
    db: Session = Depends(get_db),
    _: None = Depends(require_auth),
):
    """List all cards in the deck, optionally filtered by category."""
    query = db.query(Card)
    if category:
        query = query.filter(Card.category == category)
    cards = query.offset(skip).limit(limit).all()
    return cards


@app.get("/api/stats")
async def get_stats(
    request: Request,
    db: Session = Depends(get_db),
    _: None = Depends(require_auth),
):
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
async def list_topics(
    request: Request,
    _: None = Depends(require_auth),
):
    """List all available vocabulary topics from CSV files."""
    topics = get_available_topics()
    return [TopicInfo(name=t["name"], filename=t["filename"]) for t in topics]


@app.get("/api/categories")
async def list_categories(
    request: Request,
    db: Session = Depends(get_db),
    _: None = Depends(require_auth),
):
    """List all categories currently in the database."""
    categories = db.query(Card.category).distinct().filter(Card.category.isnot(None)).all()
    return [c[0] for c in categories]


@app.post("/api/topics/load", response_model=TopicLoadResponse)
async def load_topic(
    request: Request,
    topic_request: TopicLoadRequest,
    db: Session = Depends(get_db),
    _: None = Depends(require_auth),
):
    """Load vocabulary from a CSV file into the database."""
    try:
        count = load_topic_into_db(topic_request.filename, db, topic_request.clear_existing)
        action = "Replaced all cards with" if topic_request.clear_existing else "Added"
        logger.info(f"Loaded {count} cards from {topic_request.filename}")
        return TopicLoadResponse(
            filename=topic_request.filename,
            cards_loaded=count,
            message=f"{action} {count} cards from {topic_request.filename}",
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.post("/api/topics/sync")
async def sync_topics(
    request: Request,
    db: Session = Depends(get_db),
    _: None = Depends(require_auth),
):
    """Sync all CSV files from vocab/ directory to database."""
    if not VOCAB_DIR.exists():
        VOCAB_DIR.mkdir(parents=True)
        return {"message": "Created vocab/ directory. Add CSV files and sync again.", "loaded": {}}

    results = sync_all_topics(db)
    total = sum(results.values())
    logger.info(f"Synced {total} cards from {len(results)} files")
    return {
        "message": f"Synced {total} new cards from {len(results)} files",
        "loaded": results,
    }


@app.delete("/api/cards")
async def clear_all_cards(
    request: Request,
    db: Session = Depends(get_db),
    _: None = Depends(require_auth),
):
    """Delete all cards from the database."""
    count = db.query(Card).count()
    db.query(Card).delete()
    db.commit()
    logger.warning(f"Deleted all {count} cards")
    return {"message": f"Deleted {count} cards"}
