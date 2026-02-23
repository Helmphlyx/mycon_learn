"""Tests for the MyCon Learn API."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models import Card

# Use in-memory SQLite for testing
TEST_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(
    TEST_DATABASE_URL,
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


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(autouse=True)
def setup_database():
    """Create tables before each test and drop after."""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def sample_card():
    """Create a sample card in the database."""
    db = TestingSessionLocal()
    card = Card(vietnamese="xin chào", english="hello", category="greetings")
    db.add(card)
    db.commit()
    db.refresh(card)
    db.close()
    return card


class TestCardAPI:
    def test_create_card(self, client):
        response = client.post(
            "/api/card",
            json={"vietnamese": "cảm ơn", "english": "thank you", "category": "greetings"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["vietnamese"] == "cảm ơn"
        assert data["english"] == "thank you"
        assert data["id"] is not None

    def test_get_random_card(self, client, sample_card):
        response = client.get("/api/card/random?mode=eng_to_viet")
        assert response.status_code == 200
        data = response.json()
        assert data["prompt"] == "hello"
        assert data["mode"] == "eng_to_viet"

    def test_get_random_card_viet_to_eng(self, client, sample_card):
        response = client.get("/api/card/random?mode=viet_to_eng")
        assert response.status_code == 200
        data = response.json()
        assert data["prompt"] == "xin chào"
        assert data["mode"] == "viet_to_eng"

    def test_no_cards_returns_404(self, client):
        response = client.get("/api/card/random")
        assert response.status_code == 404

    def test_list_cards(self, client, sample_card):
        response = client.get("/api/cards")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["vietnamese"] == "xin chào"


class TestCheckAnswer:
    def test_correct_answer_vietnamese(self, client, sample_card):
        response = client.post(
            "/api/check",
            json={"card_id": sample_card.id, "user_input": "xin chào"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["correct"] is True

    def test_correct_answer_english(self, client, sample_card):
        response = client.post(
            "/api/check",
            json={"card_id": sample_card.id, "user_input": "hello"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["correct"] is True

    def test_incorrect_answer(self, client, sample_card):
        response = client.post(
            "/api/check",
            json={"card_id": sample_card.id, "user_input": "wrong"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["correct"] is False

    def test_wrong_diacritics_is_incorrect(self, client, sample_card):
        """Test that 'xin chao' (no diacritics) is NOT accepted for 'xin chào'."""
        response = client.post(
            "/api/check",
            json={"card_id": sample_card.id, "user_input": "xin chao"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["correct"] is False

    def test_whitespace_normalized(self, client, sample_card):
        """Test that leading/trailing whitespace is stripped."""
        response = client.post(
            "/api/check",
            json={"card_id": sample_card.id, "user_input": "  xin chào  "},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["correct"] is True

    def test_case_insensitive(self, client, sample_card):
        """Test that comparison is case-insensitive."""
        response = client.post(
            "/api/check",
            json={"card_id": sample_card.id, "user_input": "XIN CHÀO"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["correct"] is True


class TestHints:
    def test_hint_level_1(self, client, sample_card):
        response = client.post(
            "/api/hint?mode=eng_to_viet",
            json={"card_id": sample_card.id, "hint_level": 1},
        )
        assert response.status_code == 200
        data = response.json()
        # "xin chào" -> "___(3) ____(4)" (with letter counts)
        assert data["hint"] == "___(3) ____(4)"
        assert data["hint_level"] == 1

    def test_hint_level_2(self, client, sample_card):
        response = client.post(
            "/api/hint?mode=eng_to_viet",
            json={"card_id": sample_card.id, "hint_level": 2},
        )
        assert response.status_code == 200
        data = response.json()
        # "xin chào" -> "x__ c___"
        assert data["hint"] == "x__ c___"
        assert data["hint_level"] == 2

    def test_hint_level_3_reveals_answer(self, client, sample_card):
        response = client.post(
            "/api/hint?mode=eng_to_viet",
            json={"card_id": sample_card.id, "hint_level": 3},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["hint"] == "xin chào"
        assert data["hint_level"] == 3


class TestStats:
    def test_initial_stats(self, client):
        response = client.get("/api/stats")
        assert response.status_code == 200
        data = response.json()
        assert data["total_cards"] == 0
        assert data["total_attempts"] == 0

    def test_stats_after_attempts(self, client, sample_card):
        # Make a correct attempt (auto-recorded)
        client.post(
            "/api/check",
            json={"card_id": sample_card.id, "user_input": "hello"},
        )
        # Give up on a card (records failure via /api/give_up)
        client.post(
            "/api/give_up",
            json={"card_id": sample_card.id},
        )

        response = client.get("/api/stats")
        data = response.json()
        assert data["total_cards"] == 1
        assert data["total_attempts"] == 2
        assert data["total_success"] == 1
        assert data["total_fail"] == 1
        assert data["accuracy"] == 50.0

    def test_incorrect_not_recorded_by_default(self, client, sample_card):
        """Test that incorrect attempts don't record stats unless record_result=True."""
        # Make incorrect attempt without recording
        client.post(
            "/api/check",
            json={"card_id": sample_card.id, "user_input": "wrong"},
        )

        response = client.get("/api/stats")
        data = response.json()
        assert data["total_attempts"] == 0  # Not recorded

    def test_incorrect_recorded_when_requested(self, client, sample_card):
        """Test that incorrect attempts record when record_result=True."""
        client.post(
            "/api/check",
            json={"card_id": sample_card.id, "user_input": "wrong", "record_result": True},
        )

        response = client.get("/api/stats")
        data = response.json()
        assert data["total_fail"] == 1
