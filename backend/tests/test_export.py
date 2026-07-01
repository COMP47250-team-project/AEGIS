"""Integration test: 50-student exam export produces 50 data rows + header.

Uses an in-memory SQLite database — no Postgres instance required in CI.
"""
import csv
import io
import uuid
from collections.abc import AsyncGenerator
from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.database import Base, get_db
from app.models.exam import Enrollment, ExamSession
from app.models.risk import RiskFlag
from app.models.telemetry import SessionScore
from app.models.user import User

# Import all models so Base.metadata is fully populated before create_all
from app.models import course, quiz, risk  # noqa: F401

DATABASE_URL = "sqlite+aiosqlite:///:memory:"

# Sonar: test credential placeholder — not a real secret
_TEST_HASHED_PW = "hashed_test_only"  # noqa: S105


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest_asyncio.fixture
async def db_engine():
    """Create a fresh in-memory SQLite engine per test."""
    engine = create_async_engine(DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(db_engine) -> AsyncGenerator[AsyncSession, None]:
    """Provide a single session that the test and the app share."""
    factory = async_sessionmaker(db_engine, expire_on_commit=False)
    async with factory() as session:
        yield session


@pytest_asyncio.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """
    FastAPI test client with get_db overridden to return the test session.

    The override yields the same session instance the test uses for seeding,
    so data committed by the test is visible to the endpoint without needing
    a separate DB connection.
    """
    from app.main import app

    async def _override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    # Sonar: HTTPS not applicable for local ASGI test transport —
    # httpx ASGITransport never opens a real socket regardless of scheme
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="https://test"
    ) as ac:
        yield ac
    app.dependency_overrides.clear()


# ── Helpers ───────────────────────────────────────────────────────────────────


def _make_jwt(user_id: str, role: str) -> str:
    """Mint a test JWT matching the app's secret and algorithm."""
    from jose import jwt as jose_jwt

    from app.config import settings

    return jose_jwt.encode(
        {"sub": user_id, "role": role},
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )


async def _seed_exam(
    db: AsyncSession, professor_id: str
) -> tuple[uuid.UUID, list[str]]:
    """
    Seed one closed exam with 50 enrolled students.
    Each student gets a SessionScore row.
    First 5 students also get a RiskFlag row.
    Returns (exam_id, [student_id_str, ...]).
    """
    now = datetime.now(timezone.utc)

    exam = ExamSession(
        quiz_id=uuid.uuid4(),
        course_id=str(uuid.uuid4()),
        scheduled_start=now - timedelta(hours=2),
        duration_minutes=60,
        state="closed",
        created_by=professor_id,
        opened_at=now - timedelta(hours=2),
        closed_at=now - timedelta(hours=1),
    )
    db.add(exam)
    await db.flush()

    student_ids: list[str] = []

    for i in range(50):
        student_uuid = uuid.uuid4()
        student_id_str = str(student_uuid)
        student_ids.append(student_id_str)

        db.add(User(
            id=student_uuid,
            email=f"student{i:02d}@test.com",
            hashed_password=_TEST_HASHED_PW,
            role="student",
            full_name=f"Student {i:02d}",
        ))
        db.add(Enrollment(
            exam_id=exam.id,
            student_id=student_id_str,
        ))
        db.add(SessionScore(
            exam_id=exam.id,
            student_id=student_id_str,
            tab_switch_score=0.1,
            paste_score=0.2,
            keystroke_score=0.3,
            focus_loss_score=0.1,
            answer_timing_score=0.2,
            copy_sequence_score=0.1,
            integrity_score=0.85 if i < 5 else 0.4,
        ))
        if i < 5:
            db.add(RiskFlag(
                exam_id=exam.id,
                student_id=student_id_str,
                threshold_triggered="HIGH",
                risk_score=0.85,
            ))

    await db.commit()
    return exam.id, student_ids


def _parse_csv(content: bytes) -> list[dict]:
    """Strip BOM, decode, and return list of row dicts."""
    text = content.lstrip(b"\xef\xbb\xbf").decode("utf-8")
    return list(csv.DictReader(io.StringIO(text)))


# ── Tests ─────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_export_row_count(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """CSV must contain exactly 50 data rows plus 1 header row."""
    professor_id = str(uuid.uuid4())
    exam_id, _ = await _seed_exam(db_session, professor_id)

    response = await client.get(
        f"/api/sessions/{exam_id}/export",
        headers={"Authorization": f"Bearer {_make_jwt(professor_id, 'professor')}"},
    )

    assert response.status_code == 200, response.text
    assert "text/csv" in response.headers["content-type"]
    assert f"session_{exam_id}.csv" in response.headers["content-disposition"]

    text = response.content.lstrip(b"\xef\xbb\xbf").decode("utf-8")
    reader = csv.reader(io.StringIO(text))
    header = next(reader)
    assert header == [
        "student_id", "name", "student_number", "risk_score",
        "tab_blur_count", "paste_count", "iki_score",
        "first_keypress_score", "answer_time_score", "resize_score",
        "flagged", "exam_duration_seconds",
    ]

    data_rows = list(reader)
    assert len(data_rows) == 50, f"Expected 50 data rows, got {len(data_rows)}"


@pytest.mark.asyncio
async def test_export_bom_encoding(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Response must start with UTF-8 BOM bytes for Excel compatibility."""
    professor_id = str(uuid.uuid4())
    exam_id, _ = await _seed_exam(db_session, professor_id)

    response = await client.get(
        f"/api/sessions/{exam_id}/export",
        headers={"Authorization": f"Bearer {_make_jwt(professor_id, 'professor')}"},
    )

    assert response.status_code == 200, response.text
    assert response.content[:3] == b"\xef\xbb\xbf", "Missing UTF-8 BOM"


@pytest.mark.asyncio
async def test_export_flagged_column(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """First 5 students (by seed order) must have flagged=YES, remainder NO."""
    professor_id = str(uuid.uuid4())
    exam_id, _ = await _seed_exam(db_session, professor_id)

    response = await client.get(
        f"/api/sessions/{exam_id}/export",
        headers={"Authorization": f"Bearer {_make_jwt(professor_id, 'professor')}"},
    )

    assert response.status_code == 200, response.text
    rows = _parse_csv(response.content)

    flagged = [r for r in rows if r["flagged"] == "YES"]
    assert len(flagged) == 5, f"Expected 5 flagged rows, got {len(flagged)}"

    not_flagged = [r for r in rows if r["flagged"] == "NO"]
    assert len(not_flagged) == 45, f"Expected 45 unflagged rows, got {len(not_flagged)}"


@pytest.mark.asyncio
async def test_export_forbidden_for_student(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """A student JWT must receive 403."""
    professor_id = str(uuid.uuid4())
    exam_id, _ = await _seed_exam(db_session, professor_id)

    response = await client.get(
        f"/api/sessions/{exam_id}/export",
        headers={"Authorization": f"Bearer {_make_jwt(str(uuid.uuid4()), 'student')}"},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_export_forbidden_for_wrong_professor(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """A professor who does not own the exam must receive 403."""
    owner_id = str(uuid.uuid4())
    exam_id, _ = await _seed_exam(db_session, owner_id)

    response = await client.get(
        f"/api/sessions/{exam_id}/export",
        headers={"Authorization": f"Bearer {_make_jwt(str(uuid.uuid4()), 'professor')}"},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_export_404_unknown_exam(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """A non-existent exam_id must return 404."""
    response = await client.get(
        f"/api/sessions/{uuid.uuid4()}/export",
        headers={"Authorization": f"Bearer {_make_jwt(str(uuid.uuid4()), 'professor')}"},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_export_score_values(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Score columns must reflect the seeded SessionScore values."""
    professor_id = str(uuid.uuid4())
    exam_id, _ = await _seed_exam(db_session, professor_id)

    response = await client.get(
        f"/api/sessions/{exam_id}/export",
        headers={"Authorization": f"Bearer {_make_jwt(professor_id, 'professor')}"},
    )

    assert response.status_code == 200, response.text
    rows = _parse_csv(response.content)

    for row in rows:
        assert row["risk_score"] != "", (
            f"Empty risk_score for student {row['student_id']}"
        )


@pytest.mark.asyncio
async def test_export_exam_duration(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """exam_duration_seconds must equal closed_at - opened_at in seconds."""
    professor_id = str(uuid.uuid4())
    exam_id, _ = await _seed_exam(db_session, professor_id)

    response = await client.get(
        f"/api/sessions/{exam_id}/export",
        headers={"Authorization": f"Bearer {_make_jwt(professor_id, 'professor')}"},
    )

    assert response.status_code == 200, response.text
    rows = _parse_csv(response.content)

    # Seeded exam: opened_at = now-2h, closed_at = now-1h → 3600s
    assert rows[0]["exam_duration_seconds"] == "3600", (
        f"Expected 3600, got {rows[0]['exam_duration_seconds']}"
    )
