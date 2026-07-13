"""
backend/scripts/seed.py

Populates a fresh database with a realistic demo dataset.

Usage (from the backend/ directory):
    python -m scripts.seed

Idempotency strategy: every entity is looked up by its natural key before
insertion. Running this script twice produces identical state, no duplicates.
"""

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from datetime import datetime, timezone, timedelta
from typing import List, Tuple
from bcrypt import hashpw, gensalt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal
from app.models.user import User
from app.models.course import Course
from app.models.quiz import Quiz, Question
from app.models.exam import ExamSession, Enrollment, StudentSession
from app.models.telemetry import TelemetryEvent, StudentBaseline, SessionScore

# ── Password hashing ──────────────────────────────────────────────────────────
DEMO_PASSWORD = hashpw("demo1234".encode(), gensalt(rounds=12)).decode()


# =============================================================================
# Idempotent get-or-create helpers
# =============================================================================


async def get_or_create_user(
    db: AsyncSession,
    email: str,
    full_name: str,
    role: str,
    password: str | None = None,
) -> User:
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if user:
        return user
    hashed = (
        hashpw(password.encode(), gensalt(rounds=12)).decode()
        if password
        else DEMO_PASSWORD
    )
    user = User(
        email=email,
        hashed_password=hashed,
        role=role,
        full_name=full_name,
        is_active=True,
    )
    db.add(user)
    await db.flush()
    return user


async def get_or_create_course(
    db: AsyncSession, code: str, title: str, description: str
) -> Course:
    result = await db.execute(select(Course).where(Course.code == code))
    course = result.scalar_one_or_none()
    if course:
        return course
    course = Course(code=code, title=title, description=description)
    db.add(course)
    await db.flush()
    return course


async def get_or_create_quiz(db: AsyncSession, title: str, created_by: str) -> Quiz:
    result = await db.execute(select(Quiz).where(Quiz.title == title))
    quiz = result.scalar_one_or_none()
    if quiz:
        return quiz
    quiz = Quiz(
        title=title,
        description="Midterm assessment covering fundamental CS concepts.",
        duration_minutes=45,
        is_published=True,
        created_by=created_by,
    )
    db.add(quiz)
    await db.flush()
    return quiz


async def get_or_create_question(
    db: AsyncSession,
    quiz: Quiz,
    position: int,
    **kwargs,  # type: ignore
) -> Question:
    result = await db.execute(
        select(Question).where(
            Question.quiz_id == quiz.id,
            Question.position == position,
        )
    )
    question = result.scalar_one_or_none()
    if question:
        return question
    question = Question(quiz_id=quiz.id, position=position, **kwargs)
    db.add(question)
    await db.flush()
    return question


async def get_or_create_exam_session(
    db: AsyncSession, quiz: Quiz, course: Course, created_by: str
) -> ExamSession:
    result = await db.execute(
        select(ExamSession).where(
            ExamSession.quiz_id == quiz.id,
            ExamSession.course_id == str(course.id),
        )
    )
    exam = result.scalar_one_or_none()
    if exam:
        return exam
    now = datetime.now(timezone.utc)
    exam = ExamSession(
        quiz_id=quiz.id,
        course_id=str(course.id),
        scheduled_start=now - timedelta(days=1),
        duration_minutes=45,
        state="closed",
        created_by=created_by,
        opened_at=now - timedelta(days=1),
        closed_at=now - timedelta(hours=23),
    )
    db.add(exam)
    await db.flush()
    return exam


async def get_or_create_enrollment(
    db: AsyncSession, exam: ExamSession, student: User
) -> Enrollment:
    result = await db.execute(
        select(Enrollment).where(
            Enrollment.exam_id == exam.id,
            Enrollment.student_id == str(student.id),
        )
    )
    enrollment = result.scalar_one_or_none()
    if enrollment:
        return enrollment
    enrollment = Enrollment(
        exam_id=exam.id,
        student_id=str(student.id),
    )
    db.add(enrollment)
    await db.flush()
    return enrollment


async def get_or_create_student_session(
    db: AsyncSession, exam: ExamSession, student: User
) -> StudentSession:
    result = await db.execute(
        select(StudentSession).where(
            StudentSession.exam_id == exam.id,
            StudentSession.student_id == str(student.id),
        )
    )
    ss = result.scalar_one_or_none()
    if ss:
        return ss
    ss = StudentSession(
        exam_id=exam.id,
        student_id=str(student.id),
        consent_at=datetime.now(timezone.utc) - timedelta(days=1),
    )
    db.add(ss)
    await db.flush()
    return ss


# =============================================================================
# Telemetry seeding
# =============================================================================


async def seed_telemetry(db: AsyncSession, exam: ExamSession, student: User) -> None:
    """
    Insert a realistic sequence of telemetry events for one student.
    The sequence tells a deliberate story: normal typing → tab switch →
    paste → fast burst inconsistent with baseline → copy sequence →
    focus loss → recovery to normal rhythm.

    Skipped entirely if any telemetry already exists for this exam + student.
    """
    result = await db.execute(
        select(TelemetryEvent).where(
            TelemetryEvent.exam_id == exam.id,
            TelemetryEvent.student_id == str(student.id),
        )
    )
    if result.scalar_one_or_none():
        return

    student_id_str = str(student.id)
    base_ts = datetime.now(timezone.utc) - timedelta(hours=23, minutes=55)

    events = [
        # Normal keystroke rhythm at exam start
        {
            "event_type": "keystroke_burst",
            "payload": {
                "intervals_ms": [210, 195, 230, 180, 205, 220],
                "question_position": 0,
            },
            "occurred_at": base_ts + timedelta(seconds=10),
        },
        # Student leaves the exam tab
        {
            "event_type": "tab_hidden",
            "payload": {"duration_ms": 4200},
            "occurred_at": base_ts + timedelta(seconds=42),
        },
        # Student returns
        {
            "event_type": "tab_visible",
            "payload": {"away_duration_ms": 4200},
            "occurred_at": base_ts + timedelta(seconds=46),
        },
        # Paste event — suspicious signal
        {
            "event_type": "paste",
            "payload": {"text_length": 143, "question_position": 1},
            "occurred_at": base_ts + timedelta(seconds=60),
        },
        # Fast keystroke burst immediately after paste — inconsistent with baseline
        {
            "event_type": "keystroke_burst",
            "payload": {
                "intervals_ms": [72, 68, 81, 75, 70],
                "question_position": 1,
            },
            "occurred_at": base_ts + timedelta(seconds=62),
        },
        # Ctrl+A → Ctrl+C → Ctrl+V copy sequence detected
        {
            "event_type": "copy_sequence",
            "payload": {
                "sequence": ["ctrl_a", "ctrl_c", "ctrl_v"],
                "question_position": 1,
            },
            "occurred_at": base_ts + timedelta(seconds=75),
        },
        # Focus lost — possible alt-tab to another application
        {
            "event_type": "focus_lost",
            "payload": {
                "window_from": {"w": 1440, "h": 900},
                "window_to": {"w": 1024, "h": 768},
            },
            "occurred_at": base_ts + timedelta(seconds=90),
        },
        # Focus returned
        {
            "event_type": "focus_gained",
            "payload": {"away_duration_ms": 3100},
            "occurred_at": base_ts + timedelta(seconds=93),
        },
        # Typing returns to normal rhythm on Q3
        {
            "event_type": "keystroke_burst",
            "payload": {
                "intervals_ms": [200, 215, 195, 210, 205],
                "question_position": 2,
            },
            "occurred_at": base_ts + timedelta(seconds=150),
        },
    ]

    for ev in events:
        db.add(
            TelemetryEvent(
                exam_id=exam.id,
                student_id=student_id_str,
                event_type=ev["event_type"],
                payload=ev["payload"],
                occurred_at=ev["occurred_at"],
            )
        )

    # ── Baseline (computed from the first normal keystroke burst) ─────────────
    baseline_result = await db.execute(
        select(StudentBaseline).where(
            StudentBaseline.exam_id == exam.id,
            StudentBaseline.student_id == student_id_str,
        )
    )
    if not baseline_result.scalar_one_or_none():
        db.add(
            StudentBaseline(
                exam_id=exam.id,
                student_id=student_id_str,
                mean_keystroke_interval_ms=206.7,
                keystroke_stddev_ms=18.4,
                sample_count=6,
            )
        )

    # ── Score (elevated due to paste + copy_sequence + tab switch) ────────────
    score_result = await db.execute(
        select(SessionScore).where(
            SessionScore.exam_id == exam.id,
            SessionScore.student_id == student_id_str,
        )
    )
    if not score_result.scalar_one_or_none():
        db.add(
            SessionScore(
                exam_id=exam.id,
                student_id=student_id_str,
                tab_switch_score=0.45,
                paste_score=0.80,
                keystroke_score=0.72,
                focus_loss_score=0.38,
                answer_timing_score=0.25,
                copy_sequence_score=0.85,
                integrity_score=0.63,  # non-trivial on purpose — better for demo
                reviewer_notes=None,
            )
        )

    await db.flush()


# =============================================================================
# Main
# =============================================================================


async def seed() -> None:
    async with AsyncSessionLocal() as db:
        try:
            print("Starting seed...\n")

            # ── Super admin (AEGIS-107) ───────────────────────────────────────
            print("  [0/7] Super admin...")
            await get_or_create_user(
                db,
                "admin@aegis.ie",
                "AEGIS Super Admin",
                "super_admin",
                password="SuperAdmin123!",
            )

            # ── Professors ────────────────────────────────────────────────────
            print("  [1/7] Professors...")
            prof1 = await get_or_create_user(
                db, "alice.smith@demo.ac.uk", "Dr. Alice Smith", "professor"
            )
            await get_or_create_user(
                db, "robert.jones@demo.ac.uk", "Dr. Robert Jones", "professor"
            )

            # ── Students ──────────────────────────────────────────────────────
            print("  [2/7] Students...")
            student_data = [
                ("emma.johnson@demo.ac.uk", "Emma Johnson"),
                ("liam.williams@demo.ac.uk", "Liam Williams"),
                ("olivia.brown@demo.ac.uk", "Olivia Brown"),
                ("noah.davis@demo.ac.uk", "Noah Davis"),
                ("ava.miller@demo.ac.uk", "Ava Miller"),
                ("elijah.wilson@demo.ac.uk", "Elijah Wilson"),
                ("sophia.moore@demo.ac.uk", "Sophia Moore"),
                ("james.taylor@demo.ac.uk", "James Taylor"),
                ("isabella.anderson@demo.ac.uk", "Isabella Anderson"),
                ("oliver.thomas@demo.ac.uk", "Oliver Thomas"),
            ]
            students = [
                await get_or_create_user(db, email, name, "student")
                for email, name in student_data
            ]

            # ── Course ────────────────────────────────────────────────────────
            print("  [3/7] Course...")
            course = await get_or_create_course(
                db,
                code="CS101",
                title="Introduction to Computer Science",
                description="Foundational CS concepts: data structures, algorithms, networking.",
            )

            # ── Quiz + 5 questions ────────────────────────────────────────────
            print("  [4/7] Quiz and questions...")
            quiz = await get_or_create_quiz(
                db,
                title="Midterm Exam — Data Structures",
                created_by=str(prof1.id),
            )
            await get_or_create_question(
                db,
                quiz,
                position=0,
                type="mcq",
                prompt="Which data structure uses LIFO ordering?",
                options=["Queue", "Stack", "Linked List", "Tree"],
                correct_answer="Stack",
            )
            await get_or_create_question(
                db,
                quiz,
                position=1,
                type="mcq",
                prompt="What is the time complexity of binary search on a sorted array?",
                options=["O(n)", "O(n²)", "O(log n)", "O(1)"],
                correct_answer="O(log n)",
            )
            await get_or_create_question(
                db,
                quiz,
                position=2,
                type="mcq",
                prompt="Which sorting algorithm has the best average-case time complexity?",
                options=[
                    "Bubble Sort",
                    "Insertion Sort",
                    "Merge Sort",
                    "Selection Sort",
                ],
                correct_answer="Merge Sort",
            )
            await get_or_create_question(
                db,
                quiz,
                position=3,
                type="short",
                prompt="Explain the difference between a stack and a queue in your own words.",
                options=None,
                correct_answer=None,
            )
            await get_or_create_question(
                db,
                quiz,
                position=4,
                type="short",
                prompt="What is a hash collision and how can it be resolved?",
                options=None,
                correct_answer=None,
            )

            # ── Exam session (closed) ─────────────────────────────────────────
            print("  [5/7] Exam session...")
            exam = await get_or_create_exam_session(
                db, quiz, course, created_by=str(prof1.id)
            )

            # ── Enrollments + student sessions for all 10 students ────────────
            print("  [6/7] Enrollments and student sessions...")
            student_sessions: List[Tuple[User, StudentSession]] = []
            for student in students:
                await get_or_create_enrollment(db, exam, student)
                ss = await get_or_create_student_session(db, exam, student)
                student_sessions.append((student, ss))

            # ── Telemetry, baselines, scores for first 3 students ─────────────
            print("  [7/7] Telemetry, baselines, and scores...")
            for student, _ in student_sessions[:3]:
                await seed_telemetry(db, exam, student)

            await db.commit()

            print("\nSeed complete.")
            print("─" * 50)
            print("  Demo credentials  (password: demo1234)")
            print()
            print("  PROFESSORS")
            print("    alice.smith@demo.ac.uk")
            print("    robert.jones@demo.ac.uk")
            print()
            print("  STUDENTS")
            for email, _ in student_data:
                print(f"    {email}")
            print("─" * 50)

        except Exception as exc:
            await db.rollback()
            print(f"\nSeed FAILED — rolled back.\n  Error: {exc}")
            raise


if __name__ == "__main__":
    asyncio.run(seed())
