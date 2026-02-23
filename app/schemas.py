from datetime import datetime
from pydantic import BaseModel


class CardBase(BaseModel):
    vietnamese: str
    english: str
    category: str | None = None
    difficulty_level: int = 1


class CardCreate(CardBase):
    pass


class CardResponse(CardBase):
    id: int
    success_count: int
    fail_count: int
    last_reviewed: datetime | None
    mastered: bool

    model_config = {"from_attributes": True}


class CardQuiz(BaseModel):
    """Card data sent during quiz (hides the answer based on mode)."""
    id: int
    prompt: str
    mode: str
    category: str | None = None


class CheckRequest(BaseModel):
    card_id: int
    user_input: str
    record_result: bool = False  # Only record stats when True (on final attempt)
    mark_mastered: bool = False  # Mark the card as mastered (answered correctly with ≤2 hints)


class CheckResponse(BaseModel):
    correct: bool
    expected: str | None = None  # Only included when correct or gave_up
    user_input: str
    diff: str | None = None
    attempts: int | None = None  # Track attempt count


class GiveUpRequest(BaseModel):
    card_id: int


class GiveUpResponse(BaseModel):
    answer: str
    vietnamese: str
    english: str


class HintRequest(BaseModel):
    card_id: int
    hint_level: int  # 1, 2, or 3


class HintResponse(BaseModel):
    hint: str
    hint_level: int


class TopicInfo(BaseModel):
    """Information about an available vocabulary topic."""
    name: str
    filename: str


class TopicLoadRequest(BaseModel):
    """Request to load a topic from CSV file."""
    filename: str
    clear_existing: bool = False


class TopicLoadResponse(BaseModel):
    """Response after loading a topic."""
    filename: str
    cards_loaded: int
    message: str


class ResetMasteryRequest(BaseModel):
    """Request to reset mastery for a category."""
    category: str | None = None  # None means reset all cards
