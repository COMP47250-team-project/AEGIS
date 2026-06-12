from .database import Base
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime,ForeignKey,PrimaryKeyConstraint, CheckConstraint
from sqlalchemy.sql.sqltypes import TIMESTAMP
from sqlalchemy.sql.expression import text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from datetime import datetime
import uuid
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import relationship, Mapped, mapped_column



#--------------------------------------------
# User
#--------------------------------------------

class User(Base):
    __tablename__ = 'users'
    __table_args__ = (CheckConstraint("role IN('student','professor')",name="ck_users_role"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True),primary_key=True, server_default=text("gen_random_uuid()"))
    email: Mapped[str] = mapped_column(String,unique=True,nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    role: Mapped[str] = mapped_column(String, nullable=False)
    password_hash: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=False, server_default=text('now()'))
    
    taught_courses: Mapped[List["Course"]] = relationship("Course", back_populates='professor', foreign_keys='Course.professor_id')
    enrollments: Mapped[List["Enrollment"]] = relationship("Enrollment", back_populates='student', cascade='all, delete-orphan')
    student_sessions: Mapped[List["StudentSession"]] = relationship("StudentSession", back_populates='student', cascade='all, delete-orphan')
    baselines: Mapped[List["StudentBaseline"]] = relationship("StudentBaseline",back_populates='student',cascade='all, delete-orphan')
    

#--------------------------------------------
# Course
#--------------------------------------------

class Course(Base):
    __tablename__ = 'courses'
    id: Mapped[uuid.UUID]= mapped_column(UUID(as_uuid=True),primary_key=True, server_default=text("gen_random_uuid()"))
    professor_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id",ondelete='SET NULL'),nullable=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=False, server_default=text('now()'))
    
    professor: Mapped[Optional["User"]] = relationship("User",back_populates="taught_courses",foreign_keys=[professor_id])
    quizzes: Mapped[List["Quiz"]] = relationship("Quiz", back_populates='course', cascade='all, delete-orphan')
    enrollments: Mapped[List["Enrollment"]] = relationship("Enrollment",back_populates='course',cascade='all, delete-orphan')
    access_code: Mapped[str] = mapped_column(String(6), nullable=False, unique=True)


#--------------------------------------------
# Enrollment
#--------------------------------------------

class Enrollment(Base):
    __tablename__ = 'enrollments'
    __table_args__ = (PrimaryKeyConstraint('student_id','course_id',name='pk_enrollments'),)
    student_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    course_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("courses.id", ondelete="CASCADE"), nullable=False)
    
    student: Mapped['User'] = relationship('User', back_populates='enrollments')
    course: Mapped['Course'] = relationship('Course',back_populates='enrollments')

#--------------------------------------------
# Quiz
#--------------------------------------------

class Quiz(Base):
    __tablename__ = 'quizzes'
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True),primary_key=True, server_default=text("gen_random_uuid()"))
    course_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True),ForeignKey("courses.id",ondelete='CASCADE'), nullable=True)
    title: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True),nullable=False,server_default=text('now()'))
    
    course: Mapped[Optional["Course"]] = relationship('Course', back_populates='quizzes')
    questions: Mapped[List['Question']] = relationship("Question", back_populates='quiz', cascade='all, delete-orphan', order_by="Question.order_index",)
    exam_sessions: Mapped[List["ExamSession"]] = relationship("ExamSession",back_populates="quiz",cascade="all, delete-orphan")
#--------------------------------------------
# Question
#--------------------------------------------

class Question(Base):
    __tablename__ = 'questions'
    __table_args__ = (CheckConstraint("type IN ('multiple_choice', 'short_answer')", name="ck_questions_type"),CheckConstraint("format IN ('text', 'image_only', 'unicode_skewed')",name="ck_questions_format"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True),primary_key=True, server_default=text("gen_random_uuid()"))
    quiz_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True),ForeignKey('quizzes.id',ondelete='CASCADE'),nullable=True)
    type: Mapped[str] = mapped_column(String, nullable=False)
    format: Mapped[str] = mapped_column(String, nullable=False, server_default=text("'text'"))
    
    content: Mapped[Dict[str, Any]] = mapped_column(JSONB, nullable=False)
    order_index: Mapped[int] = mapped_column(Integer, nullable=False)
    quiz: Mapped[Optional["Quiz"]] = relationship("Quiz", back_populates="questions")
    answers: Mapped[List["Answer"]] = relationship("Answer", back_populates="question", passive_deletes=True)

#--------------------------------------------
# ExamSession
#--------------------------------------------

class ExamSession(Base):
    __tablename__ = 'exam_sessions'
    __table_args__ = (CheckConstraint("status IN ('scheduled', 'active', 'ended')", name="ck_exam_sessions_status"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True),primary_key=True, server_default=text("gen_random_uuid()"))
    quiz_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True),ForeignKey('quizzes.id',ondelete='CASCADE'), nullable=True)
    starts_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True),nullable=False)
    ends_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True),nullable=False)
    status: Mapped[Optional[str]] = mapped_column(String, server_default=text("'scheduled'"))
    
    quiz: Mapped[Optional["Quiz"]] = relationship("Quiz", back_populates="exam_sessions")
    student_sessions: Mapped[List["StudentSession"]] = relationship("StudentSession", back_populates="exam_session", cascade="all, delete-orphan")
    baselines: Mapped[List["StudentBaseline"]] = relationship("StudentBaseline", back_populates="exam_session", cascade="all, delete-orphan")
    

#--------------------------------------------
# StudentSession
#--------------------------------------------

class StudentSession(Base):
    __tablename__ = 'student_sessions'
    __table_args__ = (CheckConstraint("status IN ('not_started', 'in_progress', 'submitted')",name="ck_student_sessions_status",),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True),primary_key=True, server_default=text("gen_random_uuid()"))
    exam_session_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("exam_sessions.id",ondelete="CASCADE"), nullable=True)
    student_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id",ondelete="CASCADE"), nullable=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True),nullable=True,server_default=text('now()'))
    submitted_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True),nullable=True,server_default=text('now()'))
    status: Mapped[Optional[str]] = mapped_column(String, server_default=text("'not_started'"))
    
    exam_session: Mapped[Optional["ExamSession"]] = relationship("ExamSession", back_populates="student_sessions")
    student: Mapped[Optional["User"]] = relationship("User", back_populates="student_sessions")
    answers: Mapped[List["Answer"]] = relationship("Answer", back_populates="student_session", cascade="all, delete-orphan")
    telemetry_events: Mapped[List["TelemetryEvent"]] = relationship("TelemetryEvent", back_populates="student_session", cascade="all, delete-orphan")
    session_score: Mapped[Optional["SessionScore"]] = relationship("SessionScore",back_populates="student_session",cascade="all, delete-orphan",uselist=False,)
    

#--------------------------------------------
# Answer
#--------------------------------------------

class Answer(Base):
    __tablename__ = 'answers'
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True),primary_key=True, server_default=text("gen_random_uuid()"))
    student_session_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("student_sessions.id",ondelete="CASCADE"), nullable=True)
    question_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("questions.id",ondelete="SET NULL"), nullable=True)
    content: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    time_to_answer_ms:Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    submitted_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=False, server_default=text('now()'))
    
    student_session: Mapped[Optional["StudentSession"]] = relationship("StudentSession", back_populates="answers")
    question: Mapped[Optional["Question"]] = relationship("Question", back_populates="answers")


#--------------------------------------------
# Telemetry Event
#--------------------------------------------

class TelemetryEvent(Base):
    __tablename__ = 'telemetry_events'
    __table_args__ = (
        CheckConstraint(
            "event_type IN ('tab_blur', 'tab_focus', 'paste', 'key_interval', "
            "'key_burst', 'resize', 'answer_start', 'answer_submit')",
            name="ck_telemetry_events_event_type",
        ),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True),primary_key=True, server_default=text("gen_random_uuid()"))
    student_session_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("student_sessions.id",ondelete="CASCADE"), nullable=True)
    event_type: Mapped[str] = mapped_column(String, nullable=False)
    payload:Mapped[Dict[str,Any]] = mapped_column(JSONB, nullable=False)
    client_ts: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    server_ts: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), server_default=text('now()'))
    
    student_session: Mapped[Optional["StudentSession"]] = relationship("StudentSession", back_populates="telemetry_events")


#--------------------------------------------
# StudentBaseLine
#--------------------------------------------

class StudentBaseline(Base):
    __tablename__ = 'student_baselines'
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True),primary_key=True, server_default=text("gen_random_uuid()"))
    student_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id",ondelete="CASCADE"), nullable=True)
    exam_session_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("exam_sessions.id",ondelete="CASCADE"), nullable=True)
    avg_key_interval_ms: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    p90_key_interval_ms:Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    computed_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=False, server_default=text('now()'))
    
    student: Mapped[Optional["User"]] = relationship("User", back_populates="baselines")
    exam_session: Mapped[Optional["ExamSession"]] = relationship("ExamSession", back_populates="baselines")


#--------------------------------------------
# SessionScore
#--------------------------------------------

class SessionScore(Base):
    __tablename__ = 'session_scores'
    __table_args__ = (CheckConstraint("confidence_score BETWEEN 0 AND 1", name="ck_session_scores_confidence"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True),primary_key=True, server_default=text("gen_random_uuid()"))
    student_session_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("student_sessions.id", ondelete="CASCADE"), nullable=True)
    confidence_score: Mapped[float] = mapped_column(Float,nullable=False)
    tab_blur_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    paste_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    keystroke_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    resize_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    time_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    flagged_event_count: Mapped[Optional[int]] = mapped_column(Integer, server_default=text("0"), nullable=True)
    computed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), server_default=text("now()"))
    
    
    student_session: Mapped[Optional["StudentSession"]] = relationship("StudentSession", back_populates="session_score")