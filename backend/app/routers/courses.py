import secrets
import string
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from collections.abc import Generator

from ..database import SessionLocal
from ..models import Course, Enrollment, User
from ..schemas.courses import (
    CourseCreate,
    CourseResponse,
    EnrollRequest,
    StudentResponse,
)

router = APIRouter(prefix="/courses", tags=["courses"])


# Dependency to get DB session

def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def generate_access_code() -> str:
    alphabet = string.ascii_uppercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(6))


# POST /courses — professor creates a course
@router.post("/", response_model=CourseResponse, status_code=status.HTTP_201_CREATED)
def create_course(
    payload: CourseCreate,
    db: Session = Depends(get_db),
) -> Course:
    # Check access code uniqueness
    existing = (
        db.query(Course).filter(Course.access_code == payload.access_code).first()
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Access code already exists",
        )
    course = Course(
        name=payload.name,
        access_code=payload.access_code,
    )
    db.add(course)
    db.commit()
    db.refresh(course)
    return course

# GET /courses/{id}/students — professor views enrolled students
# TODO(AEGIS-27): restrict to professor role once JWT middleware is merged
@router.get("/{course_id}/students", response_model=list[StudentResponse])
def get_enrolled_students(
    course_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> list[User]:
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Course not found",
        )
    return [enrollment.student for enrollment in course.enrollments]

# POST /courses/{id}/enroll — student self-enrolls via access code
@router.post("/{course_id}/enroll", status_code=status.HTTP_200_OK)
def enroll_student(
    course_id: uuid.UUID,
    payload: EnrollRequest,
    db: Session = Depends(get_db),
) -> dict[str, str]:
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Course not found",
        )
    if course.access_code != payload.access_code:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid access code",
        )
    # Idempotent enrollment — return 200 if already enrolled
    existing = (
        db.query(Enrollment)
        .filter(
            Enrollment.course_id == course_id,
        )
        .first()
    )
    if existing:
        return {"detail": "Already enrolled"}

    enrollment = Enrollment(course_id=course_id)
    db.add(enrollment)
    db.commit()
    return {"detail": "Enrolled successfully"}


# DELETE /courses/{id}/students/{student_id} — professor removes student
@router.delete("/{course_id}/students/{student_id}", status_code=status.HTTP_200_OK)
def remove_student(
    course_id: uuid.UUID,
    student_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> dict[str, str]:
    enrollment = (
        db.query(Enrollment)
        .filter(
            Enrollment.course_id == course_id,
            Enrollment.student_id == student_id,
        )
        .first()
    )
    if not enrollment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Enrollment not found",
        )
    db.delete(enrollment)
    db.commit()
    return {"detail": "Student removed successfully"}
