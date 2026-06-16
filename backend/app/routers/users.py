"""User lookup endpoints — used by the professor enrollment UI."""

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user_id
from app.models.user import User

router = APIRouter(prefix="/users", tags=["users"])


class StudentListItem(BaseModel):
    id: str
    email: str
    name: str | None


@router.get("/students", response_model=list[StudentListItem])
async def list_students(
    db: AsyncSession = Depends(get_db),
    _: str = Depends(get_current_user_id),
) -> list[StudentListItem]:
    """Return all registered students (used by professor enrollment UI)."""
    result = await db.execute(
        select(User)
        .where(User.role == "student", User.is_active == True)  # noqa: E712
        .order_by(User.full_name, User.email)
    )
    return [
        StudentListItem(id=str(u.id), email=u.email, name=u.full_name)
        for u in result.scalars().all()
    ]
