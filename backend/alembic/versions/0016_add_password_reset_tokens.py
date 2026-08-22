"""add password_reset_tokens table (FR-7)

Supports the forgot-password / password-reset flow: each row holds the
SHA-256 hash of a single-use, time-limited token.  Tokens expire after 1 hour
and are marked used=True on first consumption so they cannot be replayed.

Idempotent: guarded by inspector so a re-run or a DB already populated by
Base.metadata.create_all() is a no-op, following the project's 0014/0015 pattern.

Revision ID: 0016
Revises: 0015
Create Date: 2026-07-31
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0016"
down_revision: Union[str, None] = "0015"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if "password_reset_tokens" not in inspector.get_table_names():
        op.create_table(
            "password_reset_tokens",
            sa.Column("id", sa.Uuid(), primary_key=True),
            sa.Column(
                "user_id",
                sa.Uuid(),
                sa.ForeignKey("users.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("token_hash", sa.String(length=64), unique=True, nullable=False),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("used", sa.Boolean(), nullable=False, server_default="false"),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        )
        op.create_index(
            "ix_password_reset_tokens_user_id", "password_reset_tokens", ["user_id"]
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if "password_reset_tokens" in inspector.get_table_names():
        op.drop_index(
            "ix_password_reset_tokens_user_id", table_name="password_reset_tokens"
        )
        op.drop_table("password_reset_tokens")
