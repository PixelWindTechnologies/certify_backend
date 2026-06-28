from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_super_admin
from app.db.database import get_db
from app.models.models import College, Student, User, UserRole
from app.schemas.schemas import CollegeCreate, CollegeOut, CollegeUpdate
from app.services.audit import record
from app.core.security import hash_password

router = APIRouter(prefix="/colleges", tags=["colleges"])


@router.get("", response_model=list[CollegeOut])
def list_colleges(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if user.role == UserRole.COLLEGE_ADMIN:
        return db.query(College).filter(College.id == user.college_id).all()
    return db.query(College).order_by(College.created_at.desc()).all()


@router.get("/{college_id}", response_model=CollegeOut)
def get_college(college_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    college = db.query(College).filter(College.id == college_id).first()
    if not college:
        raise HTTPException(status_code=404, detail="College not found")
    if user.role == UserRole.COLLEGE_ADMIN and user.college_id != college_id:
        raise HTTPException(status_code=403, detail="Not allowed")
    return college


@router.post("", response_model=CollegeOut, status_code=status.HTTP_201_CREATED)
def create_college(payload: CollegeCreate, db: Session = Depends(get_db), user: User = Depends(require_super_admin)):
    if db.query(College).filter(College.code == payload.code).first():
        raise HTTPException(status_code=400, detail="College code already exists")

    college = College(
        name=payload.name,
        code=payload.code,
        address=payload.address,
        contact_email=payload.contact_email,
        contact_phone=payload.contact_phone,
    )
    db.add(college)
    db.flush()

    if payload.admin_email and payload.admin_password:
        admin_user = User(
            email=payload.admin_email,
            password_hash=hash_password(payload.admin_password),
            role=UserRole.COLLEGE_ADMIN,
            college_id=college.id,
            must_change_password=False,
        )
        db.add(admin_user)

    db.commit()
    record(db, user.id, "COLLEGE_CREATED", "College", college.id, None, {"name": college.name, "code": college.code})
    return college


@router.put("/{college_id}", response_model=CollegeOut)
def update_college(
    college_id: str,
    payload: CollegeUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_super_admin),
):
    college = db.query(College).filter(College.id == college_id).first()
    if not college:
        raise HTTPException(status_code=404, detail="College not found")

    old_value = {"name": college.name, "is_active": college.is_active}
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(college, field, value)
    db.commit()

    record(db, user.id, "COLLEGE_UPDATED", "College", college.id, old_value, payload.model_dump(exclude_unset=True))
    return college


@router.delete("/{college_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_college(college_id: str, db: Session = Depends(get_db), user: User = Depends(require_super_admin)):
    college = db.query(College).filter(College.id == college_id).first()
    if not college:
        raise HTTPException(status_code=404, detail="College not found")

    if db.query(User).filter(User.college_id == college_id).first() or db.query(Student).filter(Student.college_id == college_id).first():
        raise HTTPException(
            status_code=400,
            detail="Cannot delete a college with linked users or students. Remove related records first.",
        )

    db.delete(college)
    db.commit()
    record(db, user.id, "COLLEGE_DELETED", "College", college.id, None, {"name": college.name, "code": college.code})
    return Response(status_code=status.HTTP_204_NO_CONTENT)
