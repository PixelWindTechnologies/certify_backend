from datetime import date, timedelta
import sys
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db.database import Base
from app.models.models import (
    CertificateApproval,
    College,
    Course,
    Enrollment,
    EnrollmentStatus,
    Student,
)
from app.services.certificate_job import finalize_enrollment_if_eligible


def test_finalize_enrollment_if_eligible_marks_completed_and_approved_when_relieving_date_passed():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    db = Session()

    try:
        college = College(name="Test College", code="TC01")
        course = Course(name="Test Course", code="TC")
        student = Student(
            college=college,
            full_name="Test Student",
            phone="1234567890",
            email="student@example.com",
        )
        enrollment = Enrollment(
            student=student,
            course=course,
            college=college,
            internship_id="INT-001",
            student_sequence=1,
            status=EnrollmentStatus.ACTIVE,
            certificate_approval=CertificateApproval.PENDING,
            relieving_date=date.today() - timedelta(days=1),
        )
        db.add_all([college, course, student, enrollment])
        db.commit()

        changed = finalize_enrollment_if_eligible(db, enrollment)

        assert changed is True
        assert enrollment.status == EnrollmentStatus.COMPLETED
        assert enrollment.certificate_approval == CertificateApproval.APPROVED
    finally:
        db.close()
