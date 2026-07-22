"""create risk_flags table

The RiskFlag ORM model (app/models/risk.py) has existed since the risk-flag
feature was built, but no migration ever created its table — the test suite
only passed because tests bypass Alembic entirely via Base.metadata.create_all().
Any real deployment crashes with UndefinedTableError the moment a student's
integrity score crosses RISK_THRESHOLD, rolling back score computation for
every student in that exam (discovered via live testing, AEGIS-114/118).
Idempotent: guards on the existing table so a re-run is a no-op.

Revision ID: 0014
Revises: 0013
Create Date: 2026-07-20

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0014"
down_revision: Union[str, None] = "0013"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if "risk_flags" not in inspector.get_table_names():
        op.create_table(
            "risk_flags",
            sa.Column("id", sa.Uuid(), primary_key=True),
            sa.Column(
                "exam_id",
                sa.Uuid(),
                sa.ForeignKey("exam_sessions.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("student_id", sa.String(length=255), nullable=False),
            sa.Column(
                "threshold_triggered",
                sa.String(length=20),
                nullable=False,
                server_default="HIGH",
            ),
            sa.Column("risk_score", sa.Float(), nullable=False),
            sa.Column("flagged_at", sa.DateTime(timezone=True), nullable=False),
        )
        op.create_index("ix_risk_flags_exam_id", "risk_flags", ["exam_id"])
        op.create_index("ix_risk_flags_student_id", "risk_flags", ["student_id"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if "risk_flags" in inspector.get_table_names():
        op.drop_index("ix_risk_flags_student_id", table_name="risk_flags")
        op.drop_index("ix_risk_flags_exam_id", table_name="risk_flags")
        op.drop_table("risk_flags")
