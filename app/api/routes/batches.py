from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_super_admin
from app.db.database import get_db
from app.models.models import Batch, Course, User, UserRole
from app.schemas.schemas import BatchCreate, BatchOut
from app.services.audit import record
from app.services.internship_id import next_batch_number, build_batch_name

router = APIRouter(prefix="/batches", tags=["batches"])


@router.get("", response_model=list[BatchOut])
def list_batches(
    college_id: str | None = None,
    course_id: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    query = db.query(Batch)
    if user.role == UserRole.COLLEGE_ADMIN:
        query = query.filter(Batch.college_id == user.college_id)
    elif college_id:
        query = query.filter(Batch.college_id == college_id)
    if course_id:
        query = query.filter(Batch.course_id == course_id)
    return query.order_by(Batch.created_at.desc()).all()


@router.post("", response_model=BatchOut, status_code=status.HTTP_201_CREATED)
def create_batch(payload: BatchCreate, db: Session = Depends(get_db), user: User = Depends(require_super_admin)):
    course = db.query(Course).filter(Course.id == payload.course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    batch_number = next_batch_number(db, payload.course_id, payload.college_id)
    name = build_batch_name(course, batch_number, payload.start_date)

    batch = Batch(
        course_id=payload.course_id,
        college_id=payload.college_id,
        name=name,
        batch_number=batch_number,
        start_date=payload.start_date,
        end_date=payload.end_date,
    )
    db.add(batch)
    db.commit()
    record(db, user.id, "BATCH_CREATED", "Batch", batch.id, None, {"name": name})
    return batch
