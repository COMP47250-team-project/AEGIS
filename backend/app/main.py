import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers import (
    admin,
    auth,
    courses,
    exams,
    groups,
    health,
    quizzes,
    sessions,
    student,
    telemetry,
    users,
)
from app.routers.export import router as export_router

logger = logging.getLogger(__name__)

app = FastAPI(
    title="AEGIS",
    description="Adaptive Exam Guardian and Integrity System",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.backend_cors_origins,
    allow_origin_regex=r"https://.*\.azurecontainerapps\.io",  # allow all ACA subdomains
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(admin.router)
app.include_router(quizzes.router)
app.include_router(exams.router)
app.include_router(courses.router)
app.include_router(student.router)
app.include_router(users.router)
app.include_router(telemetry.router)
app.include_router(sessions.router)
app.include_router(groups.router)
app.include_router(export_router)
app.include_router(health.router)
