"""add results_released_at to exam_sessions

Lets a professor release results for a manually-graded exam (AEGIS-112b).

Revision ID: 0011
Revises: 0010b
Create Date: 2026-07-09

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0011"
down_revision: Union[str, None] = "0010b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "exam_sessions",
        sa.Column("results_released_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("exam_sessions", "results_released_at")
