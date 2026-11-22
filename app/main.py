import os, secrets, threading
from contextlib import asynccontextmanager
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from starlette.middleware.sessions import SessionMiddleware

from . import content
from .admin import router as admin_router
from .db import Base, SessionLocal, engine, get_db, migrate_schema
from .forms import clean
from .models import Application, Event, Member, Message, Project, Registration, User
from .security import hash_password, rate_limit, verify_csrf, verify_password
from .seed import ensure_admin, ensure_demo_data
from .web import BASE, flash, render


@asynccontextmanager
async def lifespan(app):
    Base.metadata.create_all(engine)
    migrate_schema()
    ensure_admin()
    ensure_demo_data()
    yield


app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
_secret = os.getenv("SECRET_KEY")
if not _secret:
    print("WARNING: SECRET_KEY not set; using a random one (sessions reset on restart).")
app.mount("/static", StaticFiles(directory=BASE / "static"), name="static")
app.include_router(admin_router)


@app.middleware("http")
async def headers(request: Request, call_next):
    request.state.current_user = None
    uid = request.session.get("user_id")
    if uid:
        with SessionLocal() as db:
            request.state.current_user = db.get(User, uid)
    r = await call_next(request)
    r.headers.update({"X-Content-Type-Options": "nosniff", "X-Frame-Options": "DENY", "Referrer-Policy": "same-origin"})
    return r

# SessionMiddleware wraps the request context so the middleware above can resolve a user ID
# without placing names, emails, or roles in the signed (readable) session cookie.
app.add_middleware(SessionMiddleware, secret_key=_secret or secrets.token_urlsafe(32), max_age=8 * 3600,
                   same_site="lax", https_only=os.getenv("COOKIE_SECURE") == "1",
                   session_cookie="code2chill_session")


@app.exception_handler(HTTPException)
async def http_error(request: Request, exc: HTTPException):
    return render(request, "error.html", exc.status_code, code=exc.status_code, message=exc.detail)


def published_events(db: Session):
    return db.scalars(select(Event).where(Event.published).order_by(Event.date.desc().nulls_last(), Event.id.desc())).all()


@app.get("/")
def home(request: Request, db: Session = Depends(get_db)):
    return render(request, "home.html", events=published_events(db)[:3], about=content.about)

@app.get("/register")
def register_page(request: Request):
    if request.session.get("user_id"): return RedirectResponse("/profile", 303)
    return render(request, "register.html", form={}, error=None)

@app.post("/register", dependencies=[Depends(verify_csrf), Depends(rate_limit("user-register", 10))])
async def register_user(request: Request, db: Session = Depends(get_db)):
    f = await request.form()
    values = {k: str(f.get(k, "")).strip() for k in ("name", "email", "username")}
    pw = str(f.get("password", "")); error = None
    values["email"] = values["email"].lower(); values["username"] = values["username"].lower()
    if not values["name"] or len(values["name"]) > 200: error = "Enter a name (up to 200 characters)."
    elif not __import__("re").fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", values["email"]): error = "Enter a valid email address."
    elif not __import__("re").fullmatch(r"[a-z0-9_]{3,40}", values["username"]): error = "Username must be 3–40 letters, numbers, or underscores."
    elif len(pw) < 8: error = "Password must be at least 8 characters."
    elif db.scalar(select(User).where((User.email == values["email"]) | (User.username == values["username"]))): error = "That email or username is already in use."
    if error: return render(request, "register.html", 400, form=values, error=error)
    user = User(**values, password_hash=hash_password(pw)); db.add(user)
    try:
        db.commit(); db.refresh(user)
    except IntegrityError:
        db.rollback()
        return render(request, "register.html", 400, form=values, error="That email or username is already in use.")
    request.session.clear(); request.session["user_id"] = user.id
    flash(request, "Welcome to Code2Chill.")
    return RedirectResponse("/profile", 303)

@app.get("/login")
def login_page(request: Request):
    return render(request, "login.html", error=None)

@app.post("/login", dependencies=[Depends(verify_csrf), Depends(rate_limit("user-login", 10))])
async def login_user(request: Request, db: Session = Depends(get_db)):
    f = await request.form(); identity = str(f.get("identity", "")).strip().lower(); pw = str(f.get("password", ""))
    user = db.scalar(select(User).where((User.email == identity) | (User.username == identity)))
    if not verify_password(pw, user.password_hash if user else None):
        return render(request, "login.html", 401, error="Invalid username/email or password.")
    request.session.clear(); request.session["user_id"] = user.id
    return RedirectResponse("/profile", 303)

@app.post("/logout", dependencies=[Depends(verify_csrf)])
def user_logout(request: Request):
    request.session.clear(); return RedirectResponse("/", 303)

@app.get("/profile")
def profile(request: Request, db: Session = Depends(get_db)):
    user = db.get(User, request.session.get("user_id")) if request.session.get("user_id") else None
    if not user: return RedirectResponse("/login", 303)
    regs = db.scalars(select(Registration).where(Registration.user_id == user.id).order_by(Registration.id.desc())).all()
    return render(request, "profile.html", user=user, registrations=regs)


@app.get("/events")
def events(request: Request, db: Session = Depends(get_db)):
    evs = published_events(db)
    return render(request, "events.html", events=evs, cats=["all", *dict.fromkeys(e.category for e in evs)])


def get_event(db: Session, id: int) -> Event:
    ev = db.scalar(select(Event).where(Event.id == id, Event.published))
    if not ev:
        raise HTTPException(404, "Event not found.")
    return ev


REG = [("name", "Full name", "text", True), ("email", "Email", "email", True)]
_reg_lock = threading.Lock()


@app.get("/events/{id}")
def event_detail(id: int, request: Request, db: Session = Depends(get_db)):
    return render(request, "event.html", e=get_event(db, id), form={}, errors={})


@app.post("/events/{id}/register", dependencies=[Depends(verify_csrf), Depends(rate_limit("register", 20))])
async def register(id: int, request: Request, db: Session = Depends(get_db)):
    ev = get_event(db, id)
    values, errors = clean(await request.form(), REG)
    if not errors:
        # The lock makes count-then-insert atomic within one process. Behind multiple workers,
        # enforce capacity in the database instead (e.g. SELECT ... FOR UPDATE on Postgres).
        with _reg_lock:
            taken = db.scalar(select(func.count()).select_from(Registration).where(Registration.event_id == ev.id))
            if ev.capacity and taken >= ev.capacity:
                errors["_"] = "This event is full."
            else:
                try:
                    uid = request.session.get("user_id")
                    if uid:
                        values["user_id"] = uid
                    db.add(Registration(event_id=ev.id, **values)); db.commit()
                except IntegrityError:
                    db.rollback(); errors["_"] = "This email is already registered."
    if errors:
        return render(request, "event.html", 400, e=ev, form=values, errors=errors)
    flash(request, "You're registered.")
    return RedirectResponse(f"/events/{id}", 303)


@app.get("/projects")
def projects(request: Request, db: Session = Depends(get_db)):
    return render(request, "projects.html", projects=db.scalars(select(Project).order_by(Project.id.desc())).all())


@app.get("/team")
def team(request: Request, db: Session = Depends(get_db)):
    more = db.scalars(select(Member).order_by(Member.order, Member.id)).all()
    return render(request, "team.html", leader=content.leader, core=content.core, more=more)


JOIN = [("name", "Full name", "text", True), ("email", "Email", "email", True),
        ("roll_no", "Roll number (optional)", "text", False), ("branch", "Branch (optional)", "text", False),
        ("why", "Why do you want to join?", "area", True)]
CONTACT = [("name", "Name", "text", True), ("email", "Email", "email", True), ("body", "Message", "area", True)]


def simple_form(path, title, spec, model, cta, done):
    page = lambda request, status=200, values=None, errors=None: render(  # noqa: E731
        request, "form.html", status, title=title, spec=spec, cta=cta, form=values or {}, errors=errors or {})

    @app.get(path, name=f"{path}-get")
    def get(request: Request):
        return page(request)

    @app.post(path, name=f"{path}-post", dependencies=[Depends(verify_csrf), Depends(rate_limit(path, 10))])
    async def post(request: Request, db: Session = Depends(get_db)):
        values, errors = clean(await request.form(), spec)
        if errors:
            return page(request, 400, values, errors)
        db.add(model(**values)); db.commit()
        flash(request, done)
        return RedirectResponse(path, 303)


simple_form("/join", "Join us", JOIN, Application, "Apply", "Application received. We'll be in touch.")
simple_form("/contact", "Contact", CONTACT, Message, "Send message", "Message sent.")


@app.get("/{rest:path}", include_in_schema=False)
def fallback():
    return RedirectResponse("/", 307)
