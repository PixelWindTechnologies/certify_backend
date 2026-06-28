"""add must_change_password to users

Revision ID: 0002_must_change_password
Revises: 0001_initial
Create Date: 2026-06-19

"""
from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "users",
        sa.Column("must_change_password", sa.Boolean(), nullable=False, server_default=sa.true()),
    )


def downgrade():
    op.drop_column("users", "must_change_password")
