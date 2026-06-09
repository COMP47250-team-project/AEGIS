from .database import Base
from sqlalchemy import Column, Integer, String, FLoat, Boolean, ForeignKey,PrimaryKeyConstraint
from sqlalchemy.sql.sqltypes import TIMESTAMP
from sqlalchemy.sql.expression import text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from datetime import datetime
import uuid
from typing import Optional, List, Dict, ANy
from sqlalchemy.orm import relationship, Mapped, mapped_cloumn



#--------------------------------------------
# User
#--------------------------------------------

class User(Base):
    __tablename__ = 'users'
    id: Mapped[uuid.UUID] = mapped_column(UUID,primary_key=True, server_default=text(gen_random_uuid())),
    email: Mapped[str] = mapped_column(String,unique=True,nullable=False),
    name: Mapped[str] = mapped_column(String, nullable=False),
    role: Mapped[str] = mapped_column(String, nullable=False),
    created_at[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True),nullable=False,server_default=text('now()'))
    

#--------------------------------------------
# Course
#--------------------------------------------

class Course(Base):
    __tablename__ = 'courses'
    id: Mapped[uuid.UUID] = mapped_column(UUID,primary_key=True, server_default=text(gen_random_uuid())),
    professor_id: Mapped[id] = mapped_column(Integer,nullable=False),
    name: Mapped[str] = mapped_column(String, nullable=False),
    created_at[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True),nullable=False,server_default=text('now()'))
    


#--------------------------------------------
# Enrollment
#--------------------------------------------

class Enrollment(Base):
    __tablename__ = 'enrollements'
    student_id: Mapped[uuid.UUID] = mapped_column(UUID,primary_key=True, server_default=text(gen_random_uuid())),
    course_id: Mapped[uuid.UUID] = mapped_column(UUID,primary_key=True, server_default=text(gen_random_uuid())),
    

#--------------------------------------------
# Quiz
#--------------------------------------------

class Quiz(Base):
    __tablename__ = 'quizzes'
    id: Mapped[uuid.UUID] = mapped_column(UUID,primary_key=True, server_default=text(gen_random_uuid())),
    course_id: Mapped[id] = mapped_column(Integer,nullable=False),
    title: Mapped[str] = mapped_column(String, nullable=False),
    created_at[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True),nullable=False,server_default=text('now()'))
    

#--------------------------------------------
# Question
#--------------------------------------------

class Question(Base):
    __tablename__ = 'questions'
    id: Mapped[uuid.UUID] = mapped_column(UUID,primary_key=True, server_default=text(gen_random_uuid())),
    quiz_id: Mapped[id] = mapped_column(Integer,nullable=False),
    type: Mapped[str] = mapped_column(String, nullable=False),
    format: Mapped[str] = mapped_column(String, nullable=False)

#--------------------------------------------
# ExamSession
#--------------------------------------------

class ExamSession(Base):
    __tablename__ = 'exam_sessions'
    id: Mapped[uuid.UUID] = mapped_column(UUID,primary_key=True, server_default=text(gen_random_uuid())),
    quiz_id: Mapped[uuid.UUID] = mapped_column(UUID,primary_key=True, server_default=text(gen_random_uuid())),
    starts_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True),nullable=False,server_default=text('now()')),
    ends_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True),nullable=False,server_default=text('now()')),
    status:Mapped[str] = mapped_column(String, nullable=False)
    

#--------------------------------------------
# StudentSession
#--------------------------------------------

class StudentSession(Base):
    __tablename__ = 'student_sessions'
    id: Mapped[uuid.UUID] = mapped_column(UUID,primary_key=True, server_default=text(gen_random_uuid())),
    exam_session_id: Mapped[uuid.UUID] = mapped_column(UUID, primary_key=True, server_default=text(gen_random_uuid())),
    student_id: Mapped[uuid.UUID] = mapped_column(UUID,primary_key=True, server_default=text(gen_random_uuid())),
    started_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True),nullable=False,server_default=text('now()')),
    submitted_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True),nullable=False,server_default=text('now()')),
    status:Mapped[str] = mapped_column(String, nullable=False)
    

#--------------------------------------------
# Answer
#--------------------------------------------

class Answer(Base):
    __tablename__ = 'answers'
    id: Mapped[uuid.UUID] = mapped_column(UUID,primary_key=True, server_default=text(gen_random_uuid())),
    student_session_id: Mapped[uuid.UUID] = mapped_column(UUID, primary_key=True, server_default=text(gen_random_uuid())),
    question_id: Mapped[uuid.UUID] = mapped_column(UUID,primary_key=True, server_default=text(gen_random_uuid())),
    content: Mapped[str] = mapped_column(String, nullable=False),
    time_to_answer_ms:Mapped[str] = mapped_column(String, nullable=False)
    submitted_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True),nullable=False,server_default=text('now()'))


#--------------------------------------------
# Telemetry Event
#--------------------------------------------

class TelemetryEvent(Base):
    __tablename__ = 'telemetry_events'
    id: Mapped[uuid.UUID] = mapped_column(UUID,primary_key=True, server_default=text(gen_random_uuid())),
    student_session_id: Mapped[uuid.UUID] = mapped_column(UUID, primary_key=True, server_default=text(gen_random_uuid())),
    event_type: Mapped[str] = mapped_column(String, nullable=False),
    payload:Mapped[Dict[str,Any]] = mapped_column(String, nullable=False)
    client_ts: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=False, server_default=text('now()')),
    server_ts: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True),nullable=False,server_default=text('now()'))


#--------------------------------------------
# StudentBaseLine
#--------------------------------------------

class StudentBaseLine(Base):
    __tablename__ = 'student_baselines'
    id: Mapped[uuid.UUID] = mapped_column(UUID,primary_key=True, server_default=text(gen_random_uuid())),
    student_id: Mapped[uuid.UUID] = mapped_column(UUID, primary_key=True, server_default=text(gen_random_uuid())),
    exam_session_id: Mapped[uuid.UUID] = mapped_column(UUID,primary_key=True, server_default=text(gen_random_uuid())),
    avg_key_interval_ms: Mapped[Optional[float]] = mapped_column(Float, nullable=False),
    p90_key_interval_ms:Mapped[Optional[float]] = mapped_column(Float, nullable=False)
    computed_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True),nullable=False,server_default=text('now()'))


#--------------------------------------------
# SessionScore
#--------------------------------------------

class SessionScore(Base):
    __tablename__ = 'session_scores'
    id: Mapped[uuid.UUID] = mapped_column(UUID,primary_key=True, server_default=text(gen_random_uuid())),
    student_session_id: Mapped[uuid.UUID] = mapped_column(UUID, primary_key=True, server_default=text(gen_random_uuid()))