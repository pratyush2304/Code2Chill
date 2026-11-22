from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session
from .db import get_db
from .forms import clean
from .models import Admin, Application, Event, Member, Message, Project, Registration, User
from .security import rate_limit, verify_csrf, verify_password
from .web import flash, render

router = APIRouter(prefix="/admin")

# tab -> (model, form spec). Specs drive both the "add" form and server-side validation.
EDIT = {
    "events": (Event, [("title", "Title", "text", True), ("summary", "Summary", "text", False), ("category", "Category", "text", False),
                       ("date", "Date", "date", False), ("venue", "Venue", "text", False), ("capacity", "Capacity", "int", False),
                       ("published", "Published", "bool", False)]),
    "projects": (Project, [("name", "Name", "text", True), ("description", "Description", "text", False),
                           ("stack", "Stack (comma separated)", "text", False), ("github", "GitHub URL", "url", False),
                           ("demo", "Demo URL", "url", False), ("image", "Image URL", "url", False)]),
    "team": (Member, [("name", "Name", "text", True), ("role", "Role", "text", False), ("bio", "Bio", "text", False),
                      ("order", "Order", "int", False)]),
}
INBOX = {"applications": Application, "messages": Message, "registrations": Registration, "users": User}
TABS = [*EDIT, *INBOX]


def is_admin(request: Request) -> bool:
    return bool(request.session.get("admin"))


def need_admin(request: Request):
    if not is_admin(request):
        raise HTTPException(401, "Please sign in.")


def row(tab, r):
    """Normalise any record into (title, meta, status) for the list."""
    if tab == "events":
        return r.title, " · ".join(filter(None, [str(r.date or ""), r.category, "" if r.published else "draft"])), None
    if tab == "projects":
        return r.name, ", ".join(r.stack or []), None
    if tab == "team":
        return r.name, r.role, None
    if tab == "applications":
        return r.name, f"{r.email} — {r.why}", r.status
    if tab == "messages":
        return r.name, f"{r.email} — {r.body}", None
    if tab == "users":
        return r.name, f"@{r.username} · {r.email} · {r.role}", None
    return r.name, f"{r.email} → {r.event.title}", None


@router.get("")
def dashboard(request: Request, tab: str = "events", db: Session = Depends(get_db)):
    if not is_admin(request):
        return RedirectResponse("/admin/login", 303)
    if tab not in TABS:
        tab = "events"
    model = (EDIT.get(tab) or (INBOX[tab], None))[0]
    rows = [(r.id, *row(tab, r)) for r in db.scalars(select(model).order_by(model.id.desc())).all()]
    return render(request, "admin.html", tab=tab, tabs=TABS, spec=(EDIT.get(tab) or (0, []))[1], rows=rows, errors={}, form={})

@router.get("/login")
def login_page(request: Request):
    if is_admin(request): return RedirectResponse("/admin", 303)
    return render(request, "admin_login.html", error=None)


@router.post("/login", dependencies=[Depends(verify_csrf), Depends(rate_limit("login", 10))])
async def login(request: Request, db: Session = Depends(get_db)):
    f = await request.form()
    a = db.scalar(select(Admin).where(Admin.email == str(f.get("email", "")).strip().lower()))
    if not verify_password(str(f.get("password", "")), a.hash if a else None):
        return render(request, "admin_login.html", 401, error="Invalid credentials")
    request.session.clear()  # fresh session on login (fixation defence)
    request.session["admin"] = a.id
    return RedirectResponse("/admin", 303)


@router.post("/logout", dependencies=[Depends(verify_csrf)])
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/admin", 303)


@router.post("/applications/{id}/status", dependencies=[Depends(need_admin), Depends(verify_csrf)])
async def set_status(id: int, request: Request, db: Session = Depends(get_db)):
    status = str((await request.form()).get("status"))
    a = db.get(Application, id)
    if not a or status not in ("new", "accepted", "rejected"):
        raise HTTPException(400, "Bad request")
    a.status = status; db.commit()
    return RedirectResponse("/admin?tab=applications", 303)


@router.post("/{tab}", dependencies=[Depends(need_admin), Depends(verify_csrf)])
async def create(tab: str, request: Request, db: Session = Depends(get_db)):
    if tab not in EDIT:
        raise HTTPException(404, "Not found")
    model, spec = EDIT[tab]
    values, errors = clean(await request.form(), spec)
    if errors:
        rows = [(r.id, *row(tab, r)) for r in db.scalars(select(model).order_by(model.id.desc())).all()]
        return render(request, "admin.html", 400, tab=tab, tabs=TABS, spec=spec, rows=rows, errors=errors, form=values)
    if tab == "projects":
        values["stack"] = [s.strip() for s in (values["stack"] or "").split(",") if s.strip()]
    if tab == "events":
        values["category"] = values["category"] or "general"
    if tab == "team":
        values["order"] = values["order"] or 0
    db.add(model(**values)); db.commit()
    flash(request, "Added.")
    return RedirectResponse(f"/admin?tab={tab}", 303)


@router.get("/{tab}/{id}/edit")
def edit_page(tab: str, id: int, request: Request, db: Session = Depends(get_db)):
    if not is_admin(request): return RedirectResponse("/admin/login", 303)
    if tab not in EDIT: raise HTTPException(404, "Not found")
    model, spec = EDIT[tab]
    obj = db.get(model, id)
    if not obj: raise HTTPException(404, "Record not found")
    values = {name: getattr(obj, name) for name, *_ in spec}
    if tab == "projects": values["stack"] = ", ".join(obj.stack or [])
    return render(request, "admin_edit.html", tab=tab, id=id, title=row(tab, obj)[0], spec=spec, form=values, errors={})


@router.post("/{tab}/{id}/edit", dependencies=[Depends(need_admin), Depends(verify_csrf)])
async def edit_record(tab: str, id: int, request: Request, db: Session = Depends(get_db)):
    if tab not in EDIT: raise HTTPException(404, "Not found")
    model, spec = EDIT[tab]
    obj = db.get(model, id)
    if not obj: raise HTTPException(404, "Record not found")
    values, errors = clean(await request.form(), spec)
    if errors:
        return render(request, "admin_edit.html", 400, tab=tab, id=id, title=row(tab, obj)[0], spec=spec, form=values, errors=errors)
    if tab == "projects": values["stack"] = [s.strip() for s in (values["stack"] or "").split(",") if s.strip()]
    if tab == "events": values["category"] = values["category"] or "general"
    if tab == "team": values["order"] = values["order"] or 0
    for key, value in values.items(): setattr(obj, key, value)
    db.commit(); flash(request, "Changes saved.")
    return RedirectResponse(f"/admin?tab={tab}", 303)


@router.post("/{tab}/{id}/delete", dependencies=[Depends(need_admin), Depends(verify_csrf)])
def delete(tab: str, id: int, request: Request, db: Session = Depends(get_db)):
    model = (EDIT.get(tab) or (INBOX.get(tab), 0))[0]
    if not model or tab == "users":
        raise HTTPException(404, "Not found")
    if obj := db.get(model, id):
        db.delete(obj); db.commit()
    flash(request, "Deleted.")
    return RedirectResponse(f"/admin?tab={tab}", 303)
