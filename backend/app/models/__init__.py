# Import all models so SQLAlchemy's Base.metadata and Alembic autogenerate
# can discover every table.  Order matters: referenced tables before referencing ones.
from app.models.user import User  # noqa: F401
from app.models.course import Course  # noqa: F401
from app.models.quiz import Quiz, Question  # noqa: F401
from app.models.exam import (
    ExamSession,
    Enrollment,
    StudentSession,
    ExamAnswer,
)  # noqa: F401
from app.models.telemetry import (
    TelemetryEvent,
    StudentBaseline,
    SessionScore,
)  # noqa: F401
from app.models.group import StudentGroup, GroupMember  # noqa: F401
