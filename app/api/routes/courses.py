from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_super_admin
from app.db.database import get_db
from app.models.models import Course, Enrollment, User
from app.schemas.schemas import CourseCreate, CourseOut, CourseUpdate
from app.services.audit import record

router = APIRouter(prefix="/courses", tags=["courses"])


@router.get("", response_model=list[CourseOut])
def list_courses(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return db.query(Course).order_by(Course.name).all()


@router.post("", response_model=CourseOut, status_code=status.HTTP_201_CREATED)
def create_course(payload: CourseCreate, db: Session = Depends(get_db), user: User = Depends(require_super_admin)):
    if db.query(Course).filter(Course.code == payload.code).first():
        raise HTTPException(status_code=400, detail="Course code already exists")
    course = Course(**payload.model_dump())
    db.add(course)
    db.commit()
    record(db, user.id, "COURSE_CREATED", "Course", course.id, None, payload.model_dump())
    return course


@router.put("/{course_id}", response_model=CourseOut)
def update_course(
    course_id: str, payload: CourseUpdate, db: Session = Depends(get_db), user: User = Depends(require_super_admin)
):
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    old_value = {"name": course.name, "is_active": course.is_active}
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(course, field, value)
    db.commit()
    record(db, user.id, "COURSE_UPDATED", "Course", course.id, old_value, payload.model_dump(exclude_unset=True))
    return course


@router.delete("/{course_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_course(course_id: str, db: Session = Depends(get_db), user: User = Depends(require_super_admin)):
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    if db.query(Enrollment).filter(Enrollment.course_id == course_id).first():
        raise HTTPException(status_code=400, detail="Cannot delete a course with enrollments. Remove related enrollments first.")

    db.delete(course)
    db.commit()
    record(db, user.id, "COURSE_DELETED", "Course", course.id, None, {"name": course.name, "code": course.code})
    return Response(status_code=status.HTTP_204_NO_CONTENT)
