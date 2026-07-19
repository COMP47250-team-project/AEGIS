"""add has_telemetry to session_scores (AEGIS-118)

Distinguishes a real 0 integrity score (student produced zero telemetry,
e.g. never joined the exam) from a score that was actually computed from
telemetry. Idempotent: guards on existing column so a re-run is a no-op.

Revision ID: 0013
Revises: 0012
Create Date: 2026-07-18

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0013"
down_revision: Union[str, None] = "0012"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    columns = {c["name"] for c in inspector.get_columns("session_scores")}
    if "has_telemetry" not in columns:
        op.add_column(
            "session_scores",
            sa.Column(
                "has_telemetry",
                sa.Boolean(),
                nullable=False,
                server_default="true",
            ),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    columns = {c["name"] for c in inspector.get_columns("session_scores")}
    if "has_telemetry" in columns:
        op.drop_column("session_scores", "has_telemetry")
