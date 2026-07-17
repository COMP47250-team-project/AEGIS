import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class GroupCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    student_emails: list[str] = Field(default_factory=list)


class GroupMemberUpdate(BaseModel):
    add: list[str] = Field(default_factory=list)
    remove: list[str] = Field(default_factory=list)


class MemberRead(BaseModel):
    student_id: str
    email: str
    name: str | None


class SkippedEmail(BaseModel):
    email: str
    reason: str


class GroupSummary(BaseModel):
    id: uuid.UUID
    name: str
    member_count: int
    created_at: datetime


class GroupDetail(BaseModel):
    id: uuid.UUID
    name: str
    created_at: datetime
    members: list[MemberRead]
    skipped: list[SkippedEmail] = Field(default_factory=list)


class ValidateEmails(BaseModel):
    student_emails: list[str] = Field(default_factory=list)
    group_id: uuid.UUID | None = None


class ValidationResult(BaseModel):
    matched: list[MemberRead]
    skipped: list[SkippedEmail]


class EnrollGroup(BaseModel):
    group_id: uuid.UUID
