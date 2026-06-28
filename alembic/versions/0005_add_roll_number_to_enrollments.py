"""add roll number to enrollments

Revision ID: 0005_add_roll_number_to_enrollments
Revises: 0004_add_training_type_to_enrollments
Create Date: 2026-06-28
"""
from alembic import op
import sqlalchemy as sa

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "enrollments",
        sa.Column("roll_number", sa.String(50), nullable=True),
    )


def downgrade():
    op.drop_column("enrollments", "roll_number")
