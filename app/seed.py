import os
from sqlalchemy import select
from .db import Base, SessionLocal, engine
from datetime import date
from .models import Admin, Event, Member, Project, User
from .security import hash_password

def ensure_admin():
    username = os.getenv("ADMIN_USERNAME") or os.getenv("ADMIN_EMAIL")
    pw = os.getenv("ADMIN_PASSWORD", "local-admin-password")
    email = (username or "admin").strip().lower()
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        a = db.scalar(select(Admin).where(Admin.email == email.lower()))
        if a:
            a.hash = hash_password(pw)
        else:
            db.add(Admin(email=email.lower(), hash=hash_password(pw)))
        db.commit()
    return True

def ensure_demo_data():
    """Seed starter records and a local demo member without duplicating existing content."""
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        if not db.scalar(select(Project.id).limit(1)):
            db.add_all([
                Project(name="Campus Connect", description="A student built hub for campus communities.", stack=["FastAPI", "SQLite"], github="https://github.com/"),
                Project(name="Chill Scheduler", description="A lightweight way to plan club events.", stack=["Python", "JavaScript"]),
            ])
        if not db.scalar(select(Event.id).limit(1)):
            db.add_all([
                Event(title="Code2Chill Kickoff", summary="Meet the community and find your next project.", category="community", date=date(2026, 12, 5), venue="Chitkara University", published=True),
                Event(title="Build Night", summary="An evening of small experiments and shared learning.", category="workshop", date=date(2026, 12, 12), venue="Innovation Lab", published=True),
            ])
        if not db.scalar(select(Member.id).limit(1)):
            db.add_all([Member(name="Aarav Sharma", role="Community Lead", bio="Helping students build together.", order=1),
                        Member(name="Mira Singh", role="Events Lead", bio="Making room for learning and collaboration.", order=2)])
        demo_pw = os.getenv("DEMO_USER_PASSWORD", "Code2ChillDemo123!")
        demo = db.scalar(select(User).where(User.username == "demo"))
        if not demo:
            db.add(User(name="Demo Member", email="demo@code2chill.local", username="demo", role="member", password_hash=hash_password(demo_pw)))
        db.commit()

if __name__ == "__main__":
    ensure_admin(); ensure_demo_data()
    print("Seed data ready")
