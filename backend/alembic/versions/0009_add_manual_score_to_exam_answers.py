"""add manual_score to exam_answers

Revision ID: 0009
Revises: 0008
Create Date: 2026-07-08

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0009"
down_revision: Union[str, None] = "0008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "exam_answers",
        sa.Column("manual_score", sa.Float(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("exam_answers", "manual_score")
