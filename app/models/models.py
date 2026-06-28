"""
SQLAlchemy ORM models.

Covers: users, roles, colleges, courses, students, enrollments,
certificates, certificate_templates, audit_logs, verification_logs and the
future-ready modules (attendance, assessments, projects, placements) which
are schema-only for now, per the project spec.
"""
import enum
import uuid
from datetime import datetime, date

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    JSON,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.db.database import Base


def gen_uuid() -> str:
    return str(uuid.uuid4())


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------
class UserRole(str, enum.Enum):
    SUPER_ADMIN = "SUPER_ADMIN"
    COLLEGE_ADMIN = "COLLEGE_ADMIN"
    STUDENT = "STUDENT"


class EnrollmentStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"
    DROPPED = "DROPPED"


class CertificateApproval(str, enum.Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class VerificationStatus(str, enum.Enum):
    VALID = "VALID"
    REVOKED = "REVOKED"


class TrainingType(str, enum.Enum):
    INTERNSHIP = "INTERNSHIP"
    INDUSTRIAL_TRAINING = "INDUSTRIAL_TRAINING"


# ---------------------------------------------------------------------------
# Core tables
# ---------------------------------------------------------------------------
class User(Base):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=gen_uuid)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    role = Column(Enum(UserRole), nullable=False)
    college_id = Column(String(36), ForeignKey("colleges.id"), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    must_change_password = Column(Boolean, default=True, nullable=False)
    last_login_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    college = relationship("College", back_populates="users")
    student_profile = relationship("Student", back_populates="user", uselist=False)


class College(Base):
    __tablename__ = "colleges"

    id = Column(String(36), primary_key=True, default=gen_uuid)
    name = Column(String(255), nullable=False)
    code = Column(String(50), unique=True, nullable=False)
    address = Column(Text, nullable=True)
    contact_email = Column(String(255), nullable=True)
    contact_phone = Column(String(20), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    users = relationship("User", back_populates="college")
    students = relationship("Student", back_populates="college")


class Course(Base):
    __tablename__ = "courses"

    id = Column(String(36), primary_key=True, default=gen_uuid)
    name = Column(String(255), nullable=False)
    code = Column(String(20), unique=True, nullable=False)  # e.g. DA, WD, ML
    description = Column(Text, nullable=True)
    duration_weeks = Column(Integer, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class Student(Base):
    __tablename__ = "students"

    id = Column(String(36), primary_key=True, default=gen_uuid)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=True, unique=True)
    college_id = Column(String(36), ForeignKey("colleges.id"), nullable=False)

    full_name = Column(String(255), nullable=False)
    father_name = Column(String(255), nullable=True)
    phone = Column(String(20), nullable=False)
    email = Column(String(255), nullable=False, index=True)
    gender = Column(String(20), nullable=True)
    roll_number = Column(String(50), nullable=True)
    department = Column(String(100), nullable=True)
    section = Column(String(50), nullable=True)
    graduation_year = Column(Integer, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    college = relationship("College", back_populates="students")
    user = relationship("User", back_populates="student_profile")
    enrollments = relationship("Enrollment", back_populates="student")

    __table_args__ = (
        # A student is never duplicated within the same college.
        UniqueConstraint("college_id", "email", name="uq_student_email_per_college"),
    )


class Enrollment(Base):
    """A student's participation in one course at a college. One student -> many enrollments."""

    __tablename__ = "enrollments"

    id = Column(String(36), primary_key=True, default=gen_uuid)
    student_id = Column(String(36), ForeignKey("students.id"), nullable=False)
    course_id = Column(String(36), ForeignKey("courses.id"), nullable=False)
    college_id = Column(String(36), ForeignKey("colleges.id"), nullable=False)
    training_type = Column(
        Enum(TrainingType),
        nullable=False,
        default=TrainingType.INTERNSHIP,
        server_default=TrainingType.INTERNSHIP.value,
    )

    internship_id = Column(String(100), unique=True, nullable=False, index=True)
    roll_number = Column(String(50), nullable=True)
    aicte_internship_id = Column(String(100), nullable=True)  # AICTE's own ID for this internship, separate from ours
    student_sequence = Column(Integer, nullable=False)  # sequential number within a course/college group

    status = Column(Enum(EnrollmentStatus), default=EnrollmentStatus.ACTIVE, nullable=False)
    certificate_approval = Column(Enum(CertificateApproval), default=CertificateApproval.PENDING, nullable=False)

    admission_date = Column(Date, nullable=True)
    relieving_date = Column(Date, nullable=True)
    performance_grade = Column(String(10), nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    student = relationship("Student", back_populates="enrollments")
    course = relationship("Course")
    college = relationship("College")
    certificate = relationship("Certificate", back_populates="enrollment", uselist=False)


class Certificate(Base):
    __tablename__ = "certificates"

    id = Column(String(36), primary_key=True, default=gen_uuid)  # this IS the public certificate id
    enrollment_id = Column(String(36), ForeignKey("enrollments.id"), unique=True, nullable=False)

    issue_date = Column(Date, default=date.today, nullable=False)
    pdf_path = Column(String(500), nullable=True)
    qr_code_path = Column(String(500), nullable=True)
    verification_status = Column(Enum(VerificationStatus), default=VerificationStatus.VALID, nullable=False)
    version = Column(Integer, default=1, nullable=False)
    template_id = Column(String(36), ForeignKey("certificate_templates.id"), nullable=True)

    revoked_at = Column(DateTime, nullable=True)
    revoked_reason = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    enrollment = relationship("Enrollment", back_populates="certificate")
    template = relationship("CertificateTemplate")


class CertificateTemplate(Base):
    __tablename__ = "certificate_templates"

    id = Column(String(36), primary_key=True, default=gen_uuid)
    name = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False)
    is_active = Column(Boolean, default=False, nullable=False)
    layout_config = Column(JSON, nullable=True)  # field coordinates for the PDF engine
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class Signature(Base):
    __tablename__ = "signatures"

    id = Column(String(36), primary_key=True, default=gen_uuid)
    label = Column(String(255), nullable=False, default="Authorized Signatory")
    image_path = Column(String(500), nullable=False)
    is_active = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(String(36), primary_key=True, default=gen_uuid)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=True)
    action = Column(String(100), nullable=False)  # e.g. STUDENT_UPDATED, CERTIFICATE_REVOKED
    entity_type = Column(String(100), nullable=False)
    entity_id = Column(String(36), nullable=True)
    old_value = Column(JSON, nullable=True)
    new_value = Column(JSON, nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)


class VerificationLog(Base):
    __tablename__ = "verification_logs"

    id = Column(String(36), primary_key=True, default=gen_uuid)
    certificate_id = Column(String(36), ForeignKey("certificates.id"), nullable=False)
    ip_address = Column(String(64), nullable=True)
    user_agent = Column(String(500), nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)


# ---------------------------------------------------------------------------
# Future-ready modules — schema and architecture only, not implemented yet.
# ---------------------------------------------------------------------------
class FutureAttendance(Base):
    __tablename__ = "future_attendance"

    id = Column(String(36), primary_key=True, default=gen_uuid)
    enrollment_id = Column(String(36), ForeignKey("enrollments.id"), nullable=False)
    session_date = Column(Date, nullable=True)
    status = Column(String(20), nullable=True)  # PRESENT / ABSENT / LEAVE
    remarks = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class FutureAssessment(Base):
    __tablename__ = "future_assessments"

    id = Column(String(36), primary_key=True, default=gen_uuid)
    enrollment_id = Column(String(36), ForeignKey("enrollments.id"), nullable=False)
    title = Column(String(255), nullable=True)
    score = Column(Integer, nullable=True)
    max_score = Column(Integer, nullable=True)
    assessed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class FutureProject(Base):
    __tablename__ = "future_projects"

    id = Column(String(36), primary_key=True, default=gen_uuid)
    enrollment_id = Column(String(36), ForeignKey("enrollments.id"), nullable=False)
    title = Column(String(255), nullable=True)
    description = Column(Text, nullable=True)
    submission_link = Column(String(500), nullable=True)
    grade = Column(String(10), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class FuturePlacement(Base):
    __tablename__ = "future_placements"

    id = Column(String(36), primary_key=True, default=gen_uuid)
    student_id = Column(String(36), ForeignKey("students.id"), nullable=False)
    company_name = Column(String(255), nullable=True)
    role_title = Column(String(255), nullable=True)
    package_lpa = Column(String(20), nullable=True)
    placed_on = Column(Date, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)