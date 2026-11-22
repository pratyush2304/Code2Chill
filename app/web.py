"""Template setup and small helpers shared by the route modules."""
from pathlib import Path
from markupsafe import Markup
from fastapi import Request
from fastapi.templating import Jinja2Templates
from .security import csrf_token

BASE = Path(__file__).parent
templates = Jinja2Templates(directory=BASE / "templates")

# Lucide icon paths (24x24 viewBox), inlined so there is no icon font/JS dependency.
_I = {
    "menu": '<path d="M4 12h16M4 6h16M4 18h16"/>',
    "x": '<path d="M18 6 6 18M6 6l12 12"/>',
    "arrow-up-right": '<path d="M7 7h10v10M7 17 17 7"/>',
    "arrow-right": '<path d="M5 12h14m-7-7 7 7-7 7"/>',
    "arrow-left": '<path d="m12 19-7-7 7-7M19 12H5"/>',
    "calendar": '<rect x="3" y="4" width="18" height="18" rx="2"/><path d="M16 2v4M8 2v4M3 10h18"/>',
    "map-pin": '<path d="M20 10c0 6-8 12-8 12s-8-6-8-12a8 8 0 0 1 16 0Z"/><circle cx="12" cy="10" r="3"/>',
    "users": '<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75"/>',
    "user-plus": '<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M19 8v6M22 11h-6"/>',
    "folder": '<path d="M20 20a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2h-7.9a2 2 0 0 1-1.69-.9L9.6 3.9A2 2 0 0 0 7.93 3H4a2 2 0 0 0-2 2v13a2 2 0 0 0 2 2Z"/>',
    "chevron-down": '<path d="m6 9 6 6 6-6"/>',
    "check": '<circle cx="12" cy="12" r="10"/><path d="m9 12 2 2 4-4"/>',
    "alert": '<circle cx="12" cy="12" r="10"/><path d="M12 8v4M12 16h.01"/>',
    "inbox": '<path d="M22 12h-6l-2 3h-4l-2-3H2"/><path d="M5.45 5.11 2 12v6a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-6l-3.45-6.89A2 2 0 0 0 16.76 4H7.24a2 2 0 0 0-1.79 1.11z"/>',
}


def icon(name: str, size: int = 20, cls: str = "") -> Markup:
    return Markup(f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" '
                  f'stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" '
                  f'class="{cls}" aria-hidden="true">{_I[name]}</svg>')


def fmt_date(d) -> str:
    return f"{d.day} {d:%b %Y}" if d else "Date to be announced"


def initials(name: str) -> str:
    return "".join(w[0] for w in name.split()[:2]).upper()


templates.env.globals.update(icon=icon, fmt_date=fmt_date, initials=initials)


def render(request: Request, name: str, status: int = 200, **ctx):
    ctx.update(csrf=csrf_token(request), flash=request.session.pop("flash", None), path=request.url.path,
               current_user=request.state.current_user,
               is_admin=bool(request.session.get("admin")))
    return templates.TemplateResponse(request, name, ctx, status_code=status)


def flash(request: Request, message: str, kind: str = "ok"):
    request.session["flash"] = {"kind": kind, "text": message}
