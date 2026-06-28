"""add aicte_internship_id to enrollments

Revision ID: 0003_aicte_internship_id
Revises: 0002_must_change_password
Create Date: 2026-06-22

"""
from alembic import op
import sqlalchemy as sa

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "enrollments",
        sa.Column("aicte_internship_id", sa.String(length=100), nullable=True),
    )


def downgrade():
    op.drop_column("enrollments", "aicte_internship_id")