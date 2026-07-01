"""Integration test: 50-student exam export produces 50 data rows + header.

Uses an in-memory SQLite database. The test seeds 50 enrollments with score
rows and asserts the CSV structure, encoding, and row count.
"""
import csv
import io
import uuid
from datetime import datetime, timezone, timedelta

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.database import Base, get_db
from app.models.exam import Enrollment, ExamSession
from app.models.telemetry import SessionScore
from app.models.user import User
from app.models.risk import RiskFlag

# Import all models so Base.metadata is complete
from app.models import course, quiz, risk  # noqa: F401

DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture
async def db_session():
    engine = create_async_engine(DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        yield session
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def client(db_session: AsyncSession):
    """FastAPI test client with DB dependency overridden to use in-memory DB."""
    from app.main import app

    async def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac
    app.dependency_overrides.clear()


def _make_jwt(user_id: str, role: str) -> str:
    """Mint a test JWT matching the app's secret and algorithm."""
    from jose import jwt
    from app.config import settings
    return jwt.encode(
        {"sub": user_id, "role": role},
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )


async def _seed_exam(db: AsyncSession, professor_id: str) -> tuple[uuid.UUID, list[str]]:
    """
    Seed one exam with 50 enrolled students, score rows for each,
    and a RiskFlag for the first 5 (to verify the flagged column).
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

    student_ids = []
    for i in range(50):
        student_uuid = uuid.uuid4()
        student_id_str = str(student_uuid)
        student_ids.append(student_id_str)

        user = User(
            id=student_uuid,
            email=f"student{i:02d}@test.com",
            hashed_password="x",
            role="student",
            full_name=f"Student {i:02d}",
        )
        db.add(user)

        enrollment = Enrollment(
            exam_id=exam.id,
            student_id=student_id_str,
        )
        db.add(enrollment)

        score = SessionScore(
            exam_id=exam.id,
            student_id=student_id_str,
            tab_switch_score=0.1,
            paste_score=0.2,
            keystroke_score=0.3,
            focus_loss_score=0.1,
            answer_timing_score=0.2,
            copy_sequence_score=0.1,
            integrity_score=0.4 if i >= 5 else 0.85,
        )
        db.add(score)

        # First 5 students are flagged
        if i < 5:
            db.add(RiskFlag(
                exam_id=exam.id,
                student_id=student_id_str,
                threshold_triggered="HIGH",
                risk_score=0.85,
            ))

    await db.commit()
    return exam.id, student_ids


@pytest.mark.asyncio
async def test_export_row_count(client: AsyncClient, db_session: AsyncSession):
    """CSV must contain exactly 50 data rows plus 1 header row."""
    professor_id = str(uuid.uuid4())
    exam_id, _ = await _seed_exam(db_session, professor_id)

    token = _make_jwt(professor_id, "professor")
    response = await client.get(
        f"/api/sessions/{exam_id}/export",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert "text/csv" in response.headers["content-type"]
    assert f"session_{exam_id}.csv" in response.headers["content-disposition"]

    # Strip BOM before parsing
    content = response.content.lstrip(b"\xef\xbb\xbf").decode("utf-8")
    rows = list(csv.reader(io.StringIO(content)))

    assert rows[0] == [
        "student_id", "name", "student_number", "risk_score",
        "tab_blur_count", "paste_count", "iki_score",
        "first_keypress_score", "answer_time_score", "resize_score",
        "flagged", "exam_duration_seconds",
    ], "Header row does not match expected columns"

    data_rows = rows[1:]
    assert len(data_rows) == 50, f"Expected 50 data rows, got {len(data_rows)}"


@pytest.mark.asyncio
async def test_export_bom_encoding(client: AsyncClient, db_session: AsyncSession):
    """Response must start with UTF-8 BOM bytes for Excel compatibility."""
    professor_id = str(uuid.uuid4())
    exam_id, _ = await _seed_exam(db_session, professor_id)

    token = _make_jwt(professor_id, "professor")
    response = await client.get(
        f"/api/sessions/{exam_id}/export",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.content[:3] == b"\xef\xbb\xbf", "Missing UTF-8 BOM"


@pytest.mark.asyncio
async def test_export_flagged_column(client: AsyncClient, db_session: AsyncSession):
    """First 5 students must have flagged=YES, remainder NO."""
    professor_id = str(uuid.uuid4())
    exam_id, student_ids = await _seed_exam(db_session, professor_id)

    token = _make_jwt(professor_id, "professor")
    response = await client.get(
        f"/api/sessions/{exam_id}/export",
        headers={"Authorization": f"Bearer {token}"},
    )

    content = response.content.lstrip(b"\xef\xbb\xbf").decode("utf-8")
    rows = list(csv.DictReader(io.StringIO(content)))

    flagged_rows = [r for r in rows if r["flagged"] == "YES"]
    assert len(flagged_rows) == 5, f"Expected 5 flagged rows, got {len(flagged_rows)}"


@pytest.mark.asyncio
async def test_export_forbidden_for_student(client: AsyncClient, db_session: AsyncSession):
    """A student JWT must receive 403."""
    professor_id = str(uuid.uuid4())
    exam_id, _ = await _seed_exam(db_session, professor_id)

    token = _make_jwt(str(uuid.uuid4()), "student")
    response = await client.get(
        f"/api/sessions/{exam_id}/export",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_export_forbidden_for_wrong_professor(
    client: AsyncClient, db_session: AsyncSession
):
    """A professor who does not own the exam must receive 403."""
    owner_id = str(uuid.uuid4())
    exam_id, _ = await _seed_exam(db_session, owner_id)

    other_professor_token = _make_jwt(str(uuid.uuid4()), "professor")
    response = await client.get(
        f"/api/sessions/{exam_id}/export",
        headers={"Authorization": f"Bearer {other_professor_token}"},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_export_404_unknown_exam(client: AsyncClient, db_session: AsyncSession):
    """A non-existent exam_id must return 404."""
    token = _make_jwt(str(uuid.uuid4()), "professor")
    response = await client.get(
        f"/api/sessions/{uuid.uuid4()}/export",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 404
