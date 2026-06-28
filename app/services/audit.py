"""
Audit logging helper. Every sensitive mutation should call record().
"""
from sqlalchemy.orm import Session

from app.models.models import AuditLog


def record(
    db: Session,
    user_id: str | None,
    action: str,
    entity_type: str,
    entity_id: str | None = None,
    old_value: dict | None = None,
    new_value: dict | None = None,
):
    log = AuditLog(
        user_id=user_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        old_value=old_value,
        new_value=new_value,
    )
    db.add(log)
    db.commit()
