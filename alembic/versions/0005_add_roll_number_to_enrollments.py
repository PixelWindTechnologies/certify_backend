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
    op.execute("""
        DO $$ BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name='enrollments' AND column_name='roll_number'
            ) THEN
                ALTER TABLE enrollments ADD COLUMN roll_number VARCHAR(50);
            END IF;
        END $$;
    """)


def downgrade():
    op.execute("""
        DO $$ BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name='enrollments' AND column_name='roll_number'
            ) THEN
                ALTER TABLE enrollments DROP COLUMN roll_number;
            END IF;
        END $$;
    """)
