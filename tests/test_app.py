import os, re
os.environ.update(DATABASE_URL="sqlite:///./test.db", SECRET_KEY="t", ADMIN_EMAIL="a@b.co", ADMIN_PASSWORD="pw12345")
import pytest
from fastapi.testclient import TestClient
from app.db import Base, engine, SessionLocal
from sqlalchemy import delete, func, select
from app.main import app
from app import security
from app.models import Event, Member, Project, User
from app.seed import ensure_demo_data


@pytest.fixture()
def c():
    Base.metadata.drop_all(engine); security._hits.clear()
    with TestClient(app) as client:
        # Startup seeds a first-run demo site; keep route tests isolated and deterministic.
        with SessionLocal() as db:
            for table in reversed(Base.metadata.sorted_tables):
                if table.name != "admins": db.execute(delete(table))
            db.commit()
        yield client
    Base.metadata.drop_all(engine)


def tok(c, path):
    return re.search(r'name="csrf" value="([^"]+)"', c.get(path).text).group(1)


def login(c):
    r = c.post("/admin/login", data={"csrf": tok(c, "/admin"), "email": "a@b.co", "password": "pw12345"}, follow_redirects=False)
    assert r.status_code == 303


def add(c, tab, **data):
    r = c.post(f"/admin/{tab}", data={"csrf": tok(c, f"/admin?tab={tab}"), **data}, follow_redirects=False)
    assert r.status_code == 303, r.text


def test_public_pages_render(c):
    for p in ["/", "/events", "/projects", "/team", "/join", "/contact", "/admin", "/nope"]:
        assert c.get(p).status_code == 200
    assert "Lakshay Kalra" in c.get("/team").text


def test_csrf_required(c):
    assert c.post("/contact", data={"name": "x", "email": "x@y.co", "body": "hi"}).status_code == 403


def test_contact_and_join_validation(c):
    r = c.post("/contact", data={"csrf": tok(c, "/contact"), "name": "A", "email": "bad", "body": "hi"})
    assert r.status_code == 400 and "valid email" in r.text
    r = c.post("/join", data={"csrf": tok(c, "/join"), "name": "A", "email": "a@x.co", "why": "code"}, follow_redirects=True)
    assert "Application received" in r.text


def test_admin_requires_login_and_bad_password(c):
    assert c.post("/admin/events", data={"title": "x"}).status_code in (401, 403)
    r = c.post("/admin/login", data={"csrf": tok(c, "/admin"), "email": "a@b.co", "password": "wrong"})
    assert r.status_code == 401 and "Invalid credentials" in r.text


def test_event_lifecycle_and_capacity(c):
    login(c)
    add(c, "events", title="Hack Night", category="hack", date="2026-12-01", capacity="1", published="on")
    add(c, "events", title="Secret", published="")  # draft
    assert "Hack Night" in c.get("/events").text and "Secret" not in c.get("/events").text
    assert c.get("/events/2").status_code == 404
    reg = lambda e: c.post("/events/1/register", data={"csrf": tok(c, "/events/1"), "name": "N", "email": e}, follow_redirects=True)
    assert "registered" in reg("n@x.co").text
    assert "full" in c.post("/events/1/register", data={"csrf": tok(c, "/events/1"), "name": "M", "email": "m@x.co"}).text


def test_duplicate_registration(c):
    login(c); add(c, "events", title="E", published="on")
    d = {"name": "N", "email": "n@x.co"}
    c.post("/events/1/register", data={"csrf": tok(c, "/events/1"), **d})
    r = c.post("/events/1/register", data={"csrf": tok(c, "/events/1"), **d})
    assert r.status_code == 400 and "already registered" in r.text


def test_projects_url_validation_and_xss(c):
    login(c)
    r = c.post("/admin/projects", data={"csrf": tok(c, "/admin?tab=projects"), "name": "P", "github": "javascript:alert(1)"})
    assert r.status_code == 400
    add(c, "projects", name="<script>x</script>", stack="py, fastapi", github="https://github.com/a/b")
    html = c.get("/projects").text
    assert "<script>x</script>" not in html and "&lt;script&gt;" in html and "fastapi" in html


def test_application_status_and_delete(c):
    c.post("/join", data={"csrf": tok(c, "/join"), "name": "A", "email": "a@x.co", "why": "y"})
    login(c)
    c.post("/admin/applications/1/status", data={"csrf": tok(c, "/admin?tab=applications"), "status": "accepted"})
    assert "[accepted]" in c.get("/admin?tab=applications").text
    c.post("/admin/applications/1/delete", data={"csrf": tok(c, "/admin?tab=applications")})
    assert "Nothing here yet" in c.get("/admin?tab=applications").text


def test_login_rate_limit(c):
    t = tok(c, "/admin")
    codes = [c.post("/admin/login", data={"csrf": t, "email": "a@b.co", "password": "x"}).status_code for _ in range(12)]
    assert codes[-1] == 429


def test_member_registration_login_profile_and_logout(c):
    r = c.post("/register", data={"csrf": tok(c, "/register"), "name": "Test Member", "email": "member@example.com",
                                  "username": "member1", "password": "secure-pass-123"}, follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/profile"
    assert "Test Member" in c.get("/profile").text
    c.post("/logout", data={"csrf": tok(c, "/profile")}, follow_redirects=False)
    assert c.get("/profile", follow_redirects=False).status_code == 303
    r = c.post("/login", data={"csrf": tok(c, "/login"), "identity": "member1", "password": "secure-pass-123"}, follow_redirects=False)
    assert r.status_code == 303
    assert "member@example.com" in c.get("/profile").text


def test_member_registration_validation_and_duplicate(c):
    form = {"name": "Member", "email": "member@example.com", "username": "member1", "password": "short"}
    r = c.post("/register", data={"csrf": tok(c, "/register"), **form})
    assert r.status_code == 400 and "at least 8" in r.text
    form["password"] = "secure-pass-123"
    c.post("/register", data={"csrf": tok(c, "/register"), **form})
    r = c.post("/register", data={"csrf": tok(c, "/register"), **form})
    assert r.status_code == 400 and "already in use" in r.text


def test_admin_can_edit_content(c):
    login(c)
    add(c, "projects", name="Editable", description="Before")
    r = c.get("/admin/projects/1/edit")
    assert r.status_code == 200
    r = c.post("/admin/projects/1/edit", data={"csrf": tok(c, "/admin/projects/1/edit"), "name": "Editable",
              "description": "After", "stack": "Python", "github": "", "demo": "", "image": ""}, follow_redirects=True)
    assert r.status_code == 200 and "Changes saved" in r.text
    assert "After" in c.get("/projects").text


def test_starter_seed_is_idempotent(c):
    ensure_demo_data()
    with SessionLocal() as db:
        counts_before = [db.scalar(select(func.count()).select_from(model)) for model in (Event, Project, Member, User)]
    ensure_demo_data()
    with SessionLocal() as db:
        counts_after = [db.scalar(select(func.count()).select_from(model)) for model in (Event, Project, Member, User)]
    assert counts_before == counts_after


def test_user_session_cookie_survives_new_client(c):
    c.post("/register", data={"csrf": tok(c, "/register"), "name": "Persistent Member", "email": "persist@example.com",
                              "username": "persist1", "password": "secure-pass-123"}, follow_redirects=False)
    cookie = c.cookies.get("code2chill_session")
    with TestClient(app) as restarted:
        restarted.cookies.set("code2chill_session", cookie)
        assert "Persistent Member" in restarted.get("/profile").text
