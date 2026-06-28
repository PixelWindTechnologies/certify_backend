from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.database import get_db
from app.models.models import (
    College,
    Student,
    Enrollment,
    EnrollmentStatus,
    Certificate,
    VerificationStatus,
    Course,
    User,
    UserRole,
)
from app.schemas.schemas import DashboardStats

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/dashboard", response_model=DashboardStats)
def dashboard_stats(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    college_filter = user.college_id if user.role == UserRole.COLLEGE_ADMIN else None

    student_query = db.query(Student)
    enrollment_query = db.query(Enrollment)
    certificate_query = db.query(Certificate).join(Enrollment)

    if college_filter:
        student_query = student_query.filter(Student.college_id == college_filter)
        enrollment_query = enrollment_query.filter(Enrollment.college_id == college_filter)
        certificate_query = certificate_query.filter(Enrollment.college_id == college_filter)

    return DashboardStats(
        total_colleges=db.query(College).count() if not college_filter else 1,
        total_students=student_query.count(),
        total_enrollments=enrollment_query.count(),
        active_students=enrollment_query.filter(Enrollment.status == EnrollmentStatus.ACTIVE).count(),
        completed_students=enrollment_query.filter(Enrollment.status == EnrollmentStatus.COMPLETED).count(),
        dropped_students=enrollment_query.filter(Enrollment.status == EnrollmentStatus.DROPPED).count(),
        certificates_generated=certificate_query.count(),
        certificates_revoked=certificate_query.filter(Certificate.verification_status == VerificationStatus.REVOKED).count(),
    )


@router.get("/courses")
def course_statistics(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    query = db.query(Course.id, Course.name, func.count(Enrollment.id).label("enrollment_count"))
    query = query.outerjoin(Enrollment, Enrollment.course_id == Course.id)
    if user.role == UserRole.COLLEGE_ADMIN:
        query = query.filter(Enrollment.college_id == user.college_id)
    rows = query.group_by(Course.id, Course.name).all()
    return [{"course_id": r[0], "course_name": r[1], "enrollment_count": r[2]} for r in rows]


@router.get("/colleges")
def college_statistics(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    rows = (
        db.query(College.id, College.name, func.count(Student.id).label("student_count"))
        .outerjoin(Student, Student.college_id == College.id)
        .group_by(College.id, College.name)
        .all()
    )
    return [{"college_id": r[0], "college_name": r[1], "student_count": r[2]} for r in rows]
