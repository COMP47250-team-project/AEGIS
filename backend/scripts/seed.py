"""Seed script: creates a sample quiz with 5 questions (mix of MCQ and short-answer).

Usage:
    cd backend
    python scripts/seed.py
"""

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app.database import AsyncSessionLocal, engine
from app.models.quiz import Base, Question, Quiz


SEED_QUIZ = {
    "title": "Introduction to Computer Science",
    "description": "A sample quiz covering fundamental CS concepts.",
    "duration_minutes": 30,
    "is_published": False,
    "created_by": "seed-script",
}

SEED_QUESTIONS = [
    {
        "type": "mcq",
        "prompt": "Which data structure operates on a LIFO (Last In, First Out) principle?",
        "options": ["Queue", "Stack", "Linked List", "Tree"],
        "correct_answer": "Stack",
        "position": 0,
    },
    {
        "type": "mcq",
        "prompt": "What is the time complexity of binary search on a sorted array?",
        "options": ["O(n)", "O(n log n)", "O(log n)", "O(1)"],
        "correct_answer": "O(log n)",
        "position": 1,
    },
    {
        "type": "short",
        "prompt": "Describe in one sentence what a hash function does.",
        "options": None,
        "correct_answer": None,
        "position": 2,
    },
    {
        "type": "mcq",
        "prompt": "Which sorting algorithm has the best average-case time complexity?",
        "options": ["Bubble Sort", "Insertion Sort", "Merge Sort", "Selection Sort"],
        "correct_answer": "Merge Sort",
        "position": 3,
    },
    {
        "type": "short",
        "prompt": "What does TCP stand for and why is it considered reliable?",
        "options": None,
        "correct_answer": None,
        "position": 4,
    },
]


async def seed() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as session:
        quiz = Quiz(**SEED_QUIZ)
        session.add(quiz)
        await session.flush()  # populate quiz.id

        for q_data in SEED_QUESTIONS:
            question = Question(quiz_id=quiz.id, **q_data)
            session.add(question)

        await session.commit()
        print(
            f"Seeded quiz '{quiz.title}' (id={quiz.id}) with {len(SEED_QUESTIONS)} questions."
        )


if __name__ == "__main__":
    asyncio.run(seed())
