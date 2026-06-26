from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers import auth, courses, exams, quizzes, sessions, student, telemetry
from app.routers import users

app = FastAPI(
    title="AEGIS",
    description="Adaptive Exam Guardian and Integrity System",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.backend_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(quizzes.router)
app.include_router(exams.router)
app.include_router(courses.router)
app.include_router(student.router)
app.include_router(users.router)
app.include_router(telemetry.router)
app.include_router(sessions.router)


@app.get("/healthz", tags=["health"])
async def healthz() -> dict[str, str]:
    return {"status": "ok"}
