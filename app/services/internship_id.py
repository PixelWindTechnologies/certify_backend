"""
Generates the unique internship / certificate identifier:

    PW/VSP/<CourseCode>/<StudentNumber>

Example: PW/VSP/DA/0001
"""
from sqlalchemy.orm import Session

from app.models.models import Course, Enrollment


def build_internship_id(course: Course, student_sequence: int) -> str:
    student_part = f"{student_sequence:04d}"
    return f"PW/VSP/{course.code}/{student_part}"


def next_student_sequence(db: Session, course_id: str, college_id: str) -> int:
    count = db.query(Enrollment).filter(Enrollment.course_id == course_id, Enrollment.college_id == college_id).count()
    return count + 1
