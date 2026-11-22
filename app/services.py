from sqlalchemy.orm import Session
from sqlalchemy import select, func
from .models import AuditLog, Event, Registration, Application, Message, Project, Member

def log_action(db: Session, admin_email: str, action: str, table: str, target_id: int, changes: dict = None):
    audit = AuditLog(admin_email=admin_email, action=action, target_table=table, target_id=target_id, changes=changes or {})
    db.add(audit)

def get_published_events(db: Session):
    return db.scalars(
        select(Event)
        .where(Event.published == True, Event.is_deleted == False)
        .order_by(Event.date.desc().nulls_last(), Event.id.desc())
    ).all()

def register_user_for_event(db: Session, event_id: int, name: str, email: str):
    ev = db.scalar(select(Event).where(Event.id == event_id, Event.published == True))
    if not ev:
        return False, "Event not found."
    
    taken = db.scalar(select(func.count()).select_from(Registration).where(Registration.event_id == ev.id))
    if ev.capacity and taken >= ev.capacity:
        return False, "This event is full."
    
    existing = db.scalar(select(Registration).where(Registration.event_id == ev.id, Registration.email == email))
    if existing:
        return False, "This email is already registered."
    
    reg = Registration(event_id=ev.id, name=name, email=email)
    db.add(reg)
    db.commit()
    return True, "Successfully registered."