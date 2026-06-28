"""
Excel bulk-import service.

Validates uploaded spreadsheets against the required template, finds or
creates students (never duplicating an existing student), creates a new
Enrollment for every row, and returns a detailed import report.
"""
import re
from datetime import date
from io import BytesIO

import pandas as pd
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.models import Student, Course, Enrollment, User, UserRole, TrainingType
from app.services.certificate_job import finalize_enrollment_if_eligible
from app.services.internship_id import build_internship_id, next_student_sequence

REQUIRED_COLUMNS = [
    "Student Name",
    "Father Name",
    "Gender",
    "Phone Number",
    "Email Address",
    "Graduation Year",
    "College Name",
    "Course Name",
]
OPTIONAL_COLUMNS = [
    "Performance Grade", "Internship Start Date",
    "Internship End Date", "Internship ID", "AICTE Internship ID",
    "Training Type", "Roll Number",
]

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PHONE_RE = re.compile(r"^[+]?\d{10,13}$")


def default_password_for_phone(phone: str) -> str:
    """PW@ + last 4 digits of the phone number, per the student login spec."""
    digits = re.sub(r"\D", "", phone)
    return f"PW@{digits[-4:]}"


def _clean(value) -> str:
    """Safely stringifies an optional Excel cell. pandas gives NaN (a float)
    for blank cells — naively doing str(value) on that produces the literal
    string "nan", which would otherwise get stored as real data. This
    returns "" for any blank/missing cell, the stripped string otherwise."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    return str(value).strip()


def build_template_workbook() -> bytes:
    """Builds the downloadable Excel template with required + optional columns."""
    columns = REQUIRED_COLUMNS + OPTIONAL_COLUMNS
    df = pd.DataFrame(columns=columns)
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Students")
    return buffer.getvalue()


def _validate_row(row: dict) -> list[str]:
    errors = []
    for col in REQUIRED_COLUMNS:
        if pd.isna(row.get(col)) or _clean(row.get(col)) == "":
            errors.append(f"Missing required field: {col}")

    email = _clean(row.get("Email Address"))
    if email and not EMAIL_RE.match(email):
        errors.append("Invalid email format")

    phone = _clean(row.get("Phone Number"))
    if phone and not PHONE_RE.match(phone.replace(" ", "")):
        errors.append("Invalid phone number format")

    return errors


def process_import(db: Session, college_id: str, file_bytes: bytes) -> dict:
    df = pd.read_excel(BytesIO(file_bytes))
    df.columns = [str(c).strip() for c in df.columns]

    missing_cols = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing_cols:
        return {
            "success_count": 0,
            "failure_count": len(df),
            "errors": [
                {"row_number": 0, "errors": [f"Missing column(s): {', '.join(missing_cols)}"], "raw_data": {}}
            ],
        }

    success_count = 0
    errors = []
    accounts_created = 0
    students_by_email: dict[str, Student] = {}
    seen_internship_ids_in_file = set()

    for idx, raw_row in df.iterrows():
        row = raw_row.to_dict()
        row_errors = _validate_row(row)

        email = _clean(row.get("Email Address")).lower()

        course_name = _clean(row.get("Course Name"))

        # Optional per-row dates. Tolerant of mixed formats (matches the same
        # day-first parsing used when cleaning import sheets) — an unparsable
        # date is simply ignored rather than failing the whole row, since
        # these are nice-to-have, not required for the student to be created.
        start_date_value = row.get("Internship Start Date")
        end_date_value = row.get("Internship End Date")
        parsed_start = pd.to_datetime(start_date_value, dayfirst=True, errors="coerce") if not pd.isna(start_date_value) else None
        parsed_end = pd.to_datetime(end_date_value, dayfirst=True, errors="coerce") if not pd.isna(end_date_value) else None
        if parsed_start is not None and pd.isna(parsed_start):
            parsed_start = None
        if parsed_end is not None and pd.isna(parsed_end):
            parsed_end = None

        # Course must already exist — matched case-insensitively and trimmed
        # so minor capitalization differences don't block an otherwise valid row.
        course = (
            db.query(Course)
            .filter(func.lower(Course.name) == course_name.lower())
            .first()
        ) if course_name else None
        if not course and course_name:
            row_errors.append(f"Course not found: {course_name}")

        # Optional per-row batch names are ignored because enrollments are now
        # tracked directly at the course and college level rather than with
        # separate batch entities.

        # Optional admin-supplied Internship ID. If given, it's used exactly
        # as typed instead of the auto-generated format — but it still has to
        # be unique, both against the database and against earlier rows in
        # this same file.
        custom_internship_id = _clean(row.get("Internship ID"))
        if custom_internship_id:
            if custom_internship_id in seen_internship_ids_in_file:
                row_errors.append(f"Duplicate Internship ID within uploaded file: {custom_internship_id}")
            elif db.query(Enrollment).filter(Enrollment.internship_id == custom_internship_id).first():
                row_errors.append(f"Internship ID already in use: {custom_internship_id}")
            else:
                seen_internship_ids_in_file.add(custom_internship_id)

        training_type_value = _clean(row.get("Training Type")).upper().replace(" ", "_")
        training_type = TrainingType.INTERNSHIP
        if training_type_value:
            if training_type_value in TrainingType.__members__:
                training_type = TrainingType[training_type_value]
            else:
                row_errors.append(
                    "Invalid Training Type: must be INTERNSHIP or INDUSTRIAL_TRAINING"
                )

        # AICTE's own ID for this internship — entirely separate from our
        # internship_id above, shown in a different spot on the certificate.
        # No uniqueness check here: AICTE manages that on their end, not us.
        aicte_internship_id = _clean(row.get("AICTE Internship ID")) or None

        if row_errors:
            errors.append({"row_number": int(idx) + 2, "errors": row_errors, "raw_data": {k: str(v) for k, v in row.items()}})
            continue

        # Find-or-create the student for this email, across this college.
        student = students_by_email.get(email)
        if student is None:
            student = (
                db.query(Student)
                .filter(Student.college_id == college_id, Student.email == email)
                .first()
            )
            if not student:
                student = Student(
                    college_id=college_id,
                    full_name=_clean(row.get("Student Name")),
                    father_name=_clean(row.get("Father Name")) or None,
                    phone=_clean(row.get("Phone Number")),
                    email=email,
                    gender=_clean(row.get("Gender")) or None,
                    graduation_year=int(row.get("Graduation Year")) if not pd.isna(row.get("Graduation Year")) else None,
                )
                db.add(student)
                db.flush()
            students_by_email[email] = student

        # Find-or-create the student's login account. Never overwrites an
        # existing account's password — only happens the first time a
        # student is created with no linked login yet.
        if not student.user_id:
            phone_value = _clean(row.get("Phone Number"))
            existing_user = db.query(User).filter(User.email == email).first()
            if existing_user:
                # An account with this email already exists (e.g. created by
                # a previous import attempt). Link it if it's a free-standing
                # student account; otherwise leave it alone.
                if existing_user.role == UserRole.STUDENT and not existing_user.student_profile:
                    student.user_id = existing_user.id
            else:
                login_user = User(
                    email=email,
                    password_hash=hash_password(default_password_for_phone(phone_value)),
                    role=UserRole.STUDENT,
                    college_id=college_id,
                    must_change_password=True,
                )
                db.add(login_user)
                db.flush()
                student.user_id = login_user.id
                accounts_created += 1

        sequence = next_student_sequence(db, course.id, college_id)
        internship_id = custom_internship_id if custom_internship_id else build_internship_id(course, sequence)

        enrollment = Enrollment(
            student_id=student.id,
            course_id=course.id,
            college_id=college_id,
            training_type=training_type,
            internship_id=internship_id,
            roll_number=_clean(row.get("Roll Number")) or None,
            aicte_internship_id=aicte_internship_id,
            student_sequence=sequence,
            admission_date=parsed_start.date() if parsed_start is not None else date.today(),
            relieving_date=parsed_end.date() if parsed_end is not None else None,
            performance_grade=_clean(row.get("Performance Grade")) or None,
        )
        db.add(enrollment)
        finalize_enrollment_if_eligible(db, enrollment)
        success_count += 1

    db.commit()

    return {
        "success_count": success_count,
        "failure_count": len(errors),
        "errors": errors,
        "accounts_created": accounts_created,
    }