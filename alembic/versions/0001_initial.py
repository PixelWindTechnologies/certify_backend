"""initial schema

Revision ID: 0001_initial
Revises:
Create Date: 2026-06-18

"""
from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "colleges",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("code", sa.String(50), nullable=False, unique=True),
        sa.Column("address", sa.Text(), nullable=True),
        sa.Column("contact_email", sa.String(255), nullable=True),
        sa.Column("contact_phone", sa.String(20), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )

    op.create_table(
        "users",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("role", sa.Enum("SUPER_ADMIN", "COLLEGE_ADMIN", "STUDENT", name="userrole"), nullable=False),
        sa.Column("college_id", sa.String(36), sa.ForeignKey("colleges.id"), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("last_login_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )

    op.create_table(
        "courses",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("code", sa.String(20), nullable=False, unique=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("duration_weeks", sa.Integer(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )

    op.create_table(
        "students",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=True, unique=True),
        sa.Column("college_id", sa.String(36), sa.ForeignKey("colleges.id"), nullable=False),
        sa.Column("full_name", sa.String(255), nullable=False),
        sa.Column("father_name", sa.String(255), nullable=True),
        sa.Column("phone", sa.String(20), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("gender", sa.String(20), nullable=True),
        sa.Column("roll_number", sa.String(50), nullable=True),
        sa.Column("department", sa.String(100), nullable=True),
        sa.Column("section", sa.String(50), nullable=True),
        sa.Column("graduation_year", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("college_id", "email", name="uq_student_email_per_college"),
    )
    op.create_index("ix_students_email", "students", ["email"])

    op.create_table(
        "enrollments",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("student_id", sa.String(36), sa.ForeignKey("students.id"), nullable=False),
        sa.Column("course_id", sa.String(36), sa.ForeignKey("courses.id"), nullable=False),
        sa.Column("college_id", sa.String(36), sa.ForeignKey("colleges.id"), nullable=False),
        sa.Column("internship_id", sa.String(100), nullable=False, unique=True),
        sa.Column("student_sequence", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            sa.Enum("ACTIVE", "COMPLETED", "DROPPED", name="enrollmentstatus"),
            nullable=False,
            server_default="ACTIVE",
        ),
        sa.Column(
            "certificate_approval",
            sa.Enum("PENDING", "APPROVED", "REJECTED", name="certificateapproval"),
            nullable=False,
            server_default="PENDING",
        ),
        sa.Column("admission_date", sa.Date(), nullable=True),
        sa.Column("relieving_date", sa.Date(), nullable=True),
        sa.Column("performance_grade", sa.String(10), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_enrollments_internship_id", "enrollments", ["internship_id"])

    op.create_table(
        "certificate_templates",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("file_path", sa.String(500), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("layout_config", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )

    op.create_table(
        "signatures",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("label", sa.String(255), nullable=False),
        sa.Column("image_path", sa.String(500), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )

    op.create_table(
        "certificates",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("enrollment_id", sa.String(36), sa.ForeignKey("enrollments.id"), nullable=False, unique=True),
        sa.Column("issue_date", sa.Date(), nullable=False),
        sa.Column("pdf_path", sa.String(500), nullable=True),
        sa.Column("qr_code_path", sa.String(500), nullable=True),
        sa.Column(
            "verification_status",
            sa.Enum("VALID", "REVOKED", name="verificationstatus"),
            nullable=False,
            server_default="VALID",
        ),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("template_id", sa.String(36), sa.ForeignKey("certificate_templates.id"), nullable=True),
        sa.Column("revoked_at", sa.DateTime(), nullable=True),
        sa.Column("revoked_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )

    op.create_table(
        "audit_logs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("entity_type", sa.String(100), nullable=False),
        sa.Column("entity_id", sa.String(36), nullable=True),
        sa.Column("old_value", sa.JSON(), nullable=True),
        sa.Column("new_value", sa.JSON(), nullable=True),
        sa.Column("timestamp", sa.DateTime(), nullable=False),
    )

    op.create_table(
        "verification_logs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("certificate_id", sa.String(36), sa.ForeignKey("certificates.id"), nullable=False),
        sa.Column("ip_address", sa.String(64), nullable=True),
        sa.Column("user_agent", sa.String(500), nullable=True),
        sa.Column("timestamp", sa.DateTime(), nullable=False),
    )

    # Future-ready modules (schema only)
    op.create_table(
        "future_attendance",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("enrollment_id", sa.String(36), sa.ForeignKey("enrollments.id"), nullable=False),
        sa.Column("session_date", sa.Date(), nullable=True),
        sa.Column("status", sa.String(20), nullable=True),
        sa.Column("remarks", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )

    op.create_table(
        "future_assessments",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("enrollment_id", sa.String(36), sa.ForeignKey("enrollments.id"), nullable=False),
        sa.Column("title", sa.String(255), nullable=True),
        sa.Column("score", sa.Integer(), nullable=True),
        sa.Column("max_score", sa.Integer(), nullable=True),
        sa.Column("assessed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )

    op.create_table(
        "future_projects",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("enrollment_id", sa.String(36), sa.ForeignKey("enrollments.id"), nullable=False),
        sa.Column("title", sa.String(255), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("submission_link", sa.String(500), nullable=True),
        sa.Column("grade", sa.String(10), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )

    op.create_table(
        "future_placements",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("student_id", sa.String(36), sa.ForeignKey("students.id"), nullable=False),
        sa.Column("company_name", sa.String(255), nullable=True),
        sa.Column("role_title", sa.String(255), nullable=True),
        sa.Column("package_lpa", sa.String(20), nullable=True),
        sa.Column("placed_on", sa.Date(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )


def downgrade():
    op.drop_table("future_placements")
    op.drop_table("future_projects")
    op.drop_table("future_assessments")
    op.drop_table("future_attendance")
    op.drop_table("verification_logs")
    op.drop_table("audit_logs")
    op.drop_table("certificates")
    op.drop_table("signatures")
    op.drop_table("certificate_templates")
    op.drop_table("enrollments")
    op.drop_table("students")
    op.drop_table("courses")
    op.drop_table("users")
    op.drop_table("colleges")
