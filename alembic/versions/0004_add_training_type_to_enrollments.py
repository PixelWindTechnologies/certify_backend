"""add training_type to enrollments and migrate legacy batch schema
Revision ID: 0004_add_training_type_to_enrollments
Revises: 0003_aicte_internship_id
Create Date: 2026-06-26
"""
from alembic import op
import sqlalchemy as sa

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade():
    # Create enum type first
    op.execute("CREATE TYPE trainingtype AS ENUM ('INTERNSHIP', 'INDUSTRIAL_TRAINING')")

    op.add_column(
        "enrollments",
        sa.Column(
            "training_type",
            sa.Enum("INTERNSHIP", "INDUSTRIAL_TRAINING", name="trainingtype"),
            nullable=False,
            server_default="INTERNSHIP",
        ),
    )
    op.add_column(
        "enrollments",
        sa.Column("course_id", sa.String(36), sa.ForeignKey("courses.id"), nullable=True),
    )
    op.add_column(
        "enrollments",
        sa.Column("college_id", sa.String(36), sa.ForeignKey("colleges.id"), nullable=True),
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM information_schema.tables
                WHERE table_name = 'batches'
                  AND table_schema = 'public'
            ) THEN
                UPDATE enrollments
                SET course_id = batches.course_id,
                    college_id = batches.college_id
                FROM batches
                WHERE enrollments.batch_id = batches.id;
            END IF;
        END
        $$;
        """
    )
    op.alter_column("enrollments", "course_id", nullable=False)
    op.alter_column("enrollments", "college_id", nullable=False)
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM information_schema.columns
                WHERE table_name = 'enrollments'
                  AND column_name = 'batch_id'
                  AND table_schema = 'public'
            ) THEN
                ALTER TABLE enrollments DROP COLUMN batch_id;
            END IF;
        END
        $$;
        """
    )


def downgrade():
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM information_schema.columns
                WHERE table_name = 'enrollments'
                  AND column_name = 'batch_id'
                  AND table_schema = 'public'
            ) THEN
                ALTER TABLE enrollments ADD COLUMN batch_id VARCHAR(36);
            END IF;
        END
        $$;
        """
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM information_schema.tables
                WHERE table_name = 'batches'
                  AND table_schema = 'public'
            ) THEN
                UPDATE enrollments
                SET batch_id = batches.id
                FROM batches
                WHERE enrollments.course_id = batches.course_id
                  AND enrollments.college_id = batches.college_id;
            END IF;
        END
        $$;
        """
    )
    op.alter_column("enrollments", "batch_id", nullable=True)
    op.drop_column("enrollments", "college_id")
    op.drop_column("enrollments", "course_id")
    op.drop_column("enrollments", "training_type")
    op.execute("DROP TYPE trainingtype")
