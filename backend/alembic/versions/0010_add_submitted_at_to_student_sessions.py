"""add submitted_at to student_sessions

Marks when a student finishes an exam so re-entry / resubmission can be blocked
(AEGIS-111).

Revision ID: 0010
Revises: 0009
Create Date: 2026-07-09

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0010"
down_revision: Union[str, None] = "0009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "student_sessions",
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("student_sessions", "submitted_at")
