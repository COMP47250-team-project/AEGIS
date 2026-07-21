"""Open-book exam resources + per-student access tracking (AEGIS-121).

Professor (owner, draft-only for mutations):
  POST   /exams/{id}/resources          — add a URL resource to the allowlist
  POST   /exams/{id}/resources/file     — upload a file resource (multipart)
  GET    /exams/{id}/resources          — list the allowlist
  DELETE /exams/{id}/resources/{rid}    — remove a resource
  GET    /exams/{id}/resource-access    — aggregated per-student usage report

Student (enrolled, exam open, open_book, not yet submitted):
  GET    /exams/{id}/resources          — the allowlist to render in the panel
  GET    /exams/{id}/resources/{rid}/file — serve an uploaded file inline
  POST   /exams/{id}/resource-access    — durably record opening a resource
  PATCH  /exams/{id}/resource-access/{aid} — fill in an open's duration on close

Design: tracking is evidence, not enforcement — recording an open never blocks
the student, and the integrity scorer ignores resource_access events.
"""

import logging
import uuid
from collections import defaultdict
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user_id, require_role
from app.models.exam import Enrollment, ExamSession, StudentSession
from app.models.resource import ExamResource, ResourceAccess
from app.models.user import User
from app.routers.exams import _assert_owner, _get_exam_or_404
from app.schemas.exam import (
    ResourceAccessCreate,
    ResourceAccessDurationUpdate,
    ResourceAccessReport,
    ResourceCreate,
    ResourceRead,
    StudentResourceAccess,
    StudentResourceUsage,
)
from app.services import resource_storage

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/exams", tags=["resources"])


# ---------------------------------------------------------------------------
# Shared guards
# ---------------------------------------------------------------------------


async def _assert_editable(exam: ExamSession) -> None:
    """Resources can be edited while the exam is draft or open — only a closed
    exam locks them (its grades/telemetry are final). Open is allowed because a
    professor may curate resources after the exam auto-opens at its scheduled
    start, and adding a reference mid-exam is legitimate (evidence, not lockdown)."""
    if exam.state == "closed":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Resources can't be changed once the exam is closed",
        )


async def _assert_enrolled(
    db: AsyncSession, exam_id: uuid.UUID, student_id: str
) -> None:
    result = await db.execute(
        select(Enrollment).where(
            Enrollment.exam_id == exam_id,
            Enrollment.student_id == student_id,
        )
    )
    if result.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not enrolled in this exam",
        )


async def _assert_student_can_access(
    db: AsyncSession, exam: ExamSession, student_id: str
) -> None:
    """A student may use resources only in an open, open-book exam they're
    enrolled in and haven't already submitted."""
    await _assert_enrolled(db, exam.id, student_id)
    if exam.mode != "open_book":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This is not an open-book exam",
        )
    if exam.state != "open":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Resources are only available while the exam is open",
        )
    session_result = await db.execute(
        select(StudentSession).where(
            StudentSession.exam_id == exam.id,
            StudentSession.student_id == student_id,
        )
    )
    session = session_result.scalar_one_or_none()
    if session is not None and session.submitted_at is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This exam has already been submitted.",
        )


async def _get_resource_or_404(
    db: AsyncSession, exam_id: uuid.UUID, resource_id: uuid.UUID
) -> ExamResource:
    result = await db.execute(
        select(ExamResource).where(
            ExamResource.id == resource_id,
            ExamResource.exam_id == exam_id,
        )
    )
    resource = result.scalar_one_or_none()
    if resource is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Resource not found"
        )
    return resource


# ---------------------------------------------------------------------------
# Professor: manage the allowlist
# ---------------------------------------------------------------------------


@router.post(
    "/{exam_id}/resources",
    response_model=ResourceRead,
    status_code=status.HTTP_201_CREATED,
)
async def add_url_resource(
    exam_id: uuid.UUID,
    body: ResourceCreate,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(require_role("professor")),
) -> ExamResource:
    exam = await _get_exam_or_404(db, exam_id)
    _assert_owner(exam, user_id)
    await _assert_editable(exam)
    resource = ExamResource(
        exam_id=exam_id,
        label=body.label,
        type="url",
        url=body.url,
        embed=body.embed,
    )
    db.add(resource)
    await db.commit()
    await db.refresh(resource)
    return resource


@router.post(
    "/{exam_id}/resources/file",
    response_model=ResourceRead,
    status_code=status.HTTP_201_CREATED,
)
async def add_file_resource(
    exam_id: uuid.UUID,
    file: UploadFile = File(...),
    label: str = Form(""),
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(require_role("professor")),
) -> ExamResource:
    exam = await _get_exam_or_404(db, exam_id)
    _assert_owner(exam, user_id)
    await _assert_editable(exam)

    if file.content_type not in resource_storage.ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only PDF files are supported for open-book resources",
        )

    data = await file.read()
    if len(data) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Uploaded file is empty"
        )
    if len(data) > resource_storage.MAX_FILE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=(
                f"File exceeds the "
                f"{resource_storage.MAX_FILE_BYTES // (1024 * 1024)} MB limit"
            ),
        )

    blob_ref = resource_storage.build_blob_ref(exam_id)
    try:
        await resource_storage.store_file(blob_ref, data)
    except Exception:
        logger.exception("Failed to store resource file for exam %s", exam_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to store the uploaded file",
        )

    resource = ExamResource(
        exam_id=exam_id,
        label=(label.strip() or file.filename or "Untitled document"),
        type="file",
        blob_ref=blob_ref,
        embed=True,  # in-app viewer serves it same-origin, so it always embeds
    )
    db.add(resource)
    await db.commit()
    await db.refresh(resource)
    return resource


@router.get("/{exam_id}/resources", response_model=list[ResourceRead])
async def list_resources(
    exam_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
) -> list[ExamResource]:
    """List an exam's resources.

    The owning professor can always list them; a student may list them only when
    they can actually access the exam (enrolled, open, open-book, not submitted).
    """
    exam = await _get_exam_or_404(db, exam_id)
    if exam.created_by != user_id:
        await _assert_student_can_access(db, exam, user_id)
    result = await db.execute(
        select(ExamResource)
        .where(ExamResource.exam_id == exam_id)
        .order_by(ExamResource.created_at)
    )
    return list(result.scalars().all())


@router.delete(
    "/{exam_id}/resources/{resource_id}", status_code=status.HTTP_204_NO_CONTENT
)
async def delete_resource(
    exam_id: uuid.UUID,
    resource_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(require_role("professor")),
) -> None:
    exam = await _get_exam_or_404(db, exam_id)
    _assert_owner(exam, user_id)
    await _assert_editable(exam)
    resource = await _get_resource_or_404(db, exam_id, resource_id)
    await db.delete(resource)
    await db.commit()


# ---------------------------------------------------------------------------
# File serving (student or owning professor)
# ---------------------------------------------------------------------------


@router.get("/{exam_id}/resources/{resource_id}/file")
async def serve_resource_file(
    exam_id: uuid.UUID,
    resource_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
) -> Response:
    """Serve an uploaded file inline.

    Reachable by the owning professor (any state, for review) or an enrolled
    student while the exam is open. Served with a fixed safe content-type +
    nosniff so a stored file can't be interpreted as active content.
    """
    exam = await _get_exam_or_404(db, exam_id)
    if exam.created_by != user_id:
        await _assert_student_can_access(db, exam, user_id)

    resource = await _get_resource_or_404(db, exam_id, resource_id)
    if resource.type != "file" or not resource.blob_ref:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="No file for this resource"
        )

    try:
        data = await resource_storage.load_file(resource.blob_ref)
    except FileNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="File not found in storage"
        )
    except Exception:
        logger.exception("Failed to load resource file %s", resource.blob_ref)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load the file",
        )

    return Response(
        content=data,
        media_type="application/pdf",
        headers={
            "Content-Disposition": "inline",
            "X-Content-Type-Options": "nosniff",
        },
    )


# ---------------------------------------------------------------------------
# Student: record resource access (durable)
# ---------------------------------------------------------------------------


@router.post("/{exam_id}/resource-access", status_code=status.HTTP_201_CREATED)
async def record_resource_access(
    exam_id: uuid.UUID,
    body: ResourceAccessCreate,
    db: AsyncSession = Depends(get_db),
    student_id: str = Depends(require_role("student")),
) -> dict:
    """Durably record that the student opened a resource.

    Mirrors submit_answers' discipline: one row per open, committed to the DB
    (this is the authoritative record the professor grades against). The row is
    created immediately on open so a link the student opens and then abandons
    (tab close) is still captured; its duration is filled in later via PATCH.
    The lightweight telemetry event emitted client-side is only for the live
    timeline. Recording never blocks the student.
    """
    exam = await _get_exam_or_404(db, exam_id)
    await _assert_student_can_access(db, exam, student_id)
    # The resource must belong to this exam.
    await _get_resource_or_404(db, exam_id, body.resource_id)

    access = ResourceAccess(
        exam_id=exam_id,
        student_id=student_id,
        resource_id=body.resource_id,
        opened_at=datetime.now(timezone.utc),
        duration_ms=body.duration_ms,
    )
    db.add(access)
    await db.commit()
    await db.refresh(access)
    return {"recorded": True, "id": str(access.id)}


@router.patch("/{exam_id}/resource-access/{access_id}", status_code=status.HTTP_200_OK)
async def update_resource_access_duration(
    exam_id: uuid.UUID,
    access_id: uuid.UUID,
    body: ResourceAccessDurationUpdate,
    db: AsyncSession = Depends(get_db),
    student_id: str = Depends(require_role("student")),
) -> dict:
    """Fill in the duration on a previously-recorded open (on close / switch /
    submit), so each view is a single row rather than an open+close pair.

    Best-effort from the client's perspective — a missed update just leaves the
    duration null (a hard tab-close can drop it), never blocking the student.
    Scoped to the calling student's own rows.
    """
    exam = await _get_exam_or_404(db, exam_id)
    await _assert_student_can_access(db, exam, student_id)

    result = await db.execute(
        select(ResourceAccess).where(
            ResourceAccess.id == access_id,
            ResourceAccess.exam_id == exam_id,
            ResourceAccess.student_id == student_id,
        )
    )
    access = result.scalar_one_or_none()
    if access is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Access record not found"
        )
    access.duration_ms = body.duration_ms
    await db.commit()
    return {"updated": True}


# ---------------------------------------------------------------------------
# Professor: aggregated resource-access report
# ---------------------------------------------------------------------------


@router.get("/{exam_id}/resource-access", response_model=ResourceAccessReport)
async def get_resource_access_report(
    exam_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(require_role("professor")),
) -> ResourceAccessReport:
    """Per-student resource usage for the grade view (owner-only)."""
    exam = await _get_exam_or_404(db, exam_id)
    _assert_owner(exam, user_id)

    resource_result = await db.execute(
        select(ExamResource).where(ExamResource.exam_id == exam_id)
    )
    resources = {r.id: r for r in resource_result.scalars().all()}

    access_result = await db.execute(
        select(ResourceAccess)
        .where(ResourceAccess.exam_id == exam_id)
        .order_by(ResourceAccess.opened_at)
    )
    accesses = list(access_result.scalars().all())

    # Group by (student, resource); rows arrive ordered by opened_at so the
    # first row per group is the first access.
    by_student: dict[str, dict[uuid.UUID, StudentResourceUsage]] = defaultdict(dict)
    for a in accesses:
        resource = resources.get(a.resource_id)
        if resource is None:
            continue  # resource deleted — skip its orphaned access rows
        per_resource = by_student[a.student_id]
        usage = per_resource.get(a.resource_id)
        if usage is None:
            per_resource[a.resource_id] = StudentResourceUsage(
                resource_id=a.resource_id,
                label=resource.label,
                url=resource.url,
                type=resource.type,  # type: ignore[arg-type]
                first_access=a.opened_at,
                total_duration_ms=a.duration_ms or 0,
                open_count=1,
            )
        else:
            usage.total_duration_ms += a.duration_ms or 0
            usage.open_count += 1

    # Resolve student display names in one batch.
    student_ids = list(by_student.keys())
    name_map: dict[str, User] = {}
    if student_ids:
        valid_uuids = []
        for sid in student_ids:
            try:
                valid_uuids.append(uuid.UUID(sid))
            except ValueError:
                continue
        if valid_uuids:
            users_result = await db.execute(
                select(User).where(User.id.in_(valid_uuids))
            )
            for u in users_result.scalars().all():
                name_map[str(u.id)] = u

    students: list[StudentResourceAccess] = []
    for sid, per_resource in by_student.items():
        user = name_map.get(sid)
        usages = sorted(per_resource.values(), key=lambda u: u.first_access)
        students.append(
            StudentResourceAccess(
                student_id=sid,
                student_name=user.full_name if user else None,
                student_email=user.email if user else None,
                resources=usages,
            )
        )

    students.sort(key=lambda s: (s.student_name or s.student_email or s.student_id))
    return ResourceAccessReport(exam_id=exam_id, students=students)
