"""
Seed script. Run with:  python -m app.scripts.seed

Creates the first SUPER_ADMIN account plus a sample college, course and
batch so the system is immediately usable after deployment.
"""
from datetime import date

from app.db.database import SessionLocal, Base, engine
from app.core.config import settings
from app.core.security import hash_password
from app.models.models import User, UserRole, College, Course


def run():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        if not db.query(User).filter(User.email == settings.FIRST_SUPER_ADMIN_EMAIL).first():
            admin = User(
                email=settings.FIRST_SUPER_ADMIN_EMAIL,
                password_hash=hash_password(settings.FIRST_SUPER_ADMIN_PASSWORD),
                role=UserRole.SUPER_ADMIN,
                must_change_password=False,
            )
            db.add(admin)
            print(f"Created super admin: {settings.FIRST_SUPER_ADMIN_EMAIL}")

        college = db.query(College).filter(College.code == "DEMO").first()
        if not college:
            college = College(name="Demo Engineering College", code="DEMO", contact_email="contact@demo.edu")
            db.add(college)
            db.flush()
            print("Created demo college")

        course = db.query(Course).filter(Course.code == "DA").first()
        if not course:
            course = Course(name="Data Analytics Internship", code="DA", duration_weeks=8)
            db.add(course)
            db.flush()
            print("Created demo internship course")

        industrial_course = db.query(Course).filter(Course.code == "IT").first()
        if not industrial_course:
            industrial_course = Course(name="Industrial Training", code="IT", duration_weeks=12)
            db.add(industrial_course)
            db.flush()
            print("Created demo industrial training course")

        db.commit()
        print("Seed complete.")
    finally:
        db.close()


if __name__ == "__main__":
    run()
