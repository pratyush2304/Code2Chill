# Code2Chill — Python full-stack

The Code2Chill club site rebuilt in Python: **FastAPI + SQLAlchemy + Jinja2**, server-rendered, same design and pages as the MERN version
(Home, Events + detail/registration, Projects, Team, Join, Contact, Admin).

Python 3.10+. No Node needed to run it.

## Run
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # change SECRET_KEY and the local admin/demo passwords
set -a; source .env; set +a # optional: app also reads simple .env files at startup
uvicorn app.main:app --reload
```
Open http://localhost:8000. Create a member account at `/register`; sign in to the management dashboard at `/admin/login` with the configured admin username and password. Tables, starter projects/events/team, and the demo member are created on first startup; `python -m app.seed` can run the idempotent seeding step manually.

## Layout
```
app/main.py       public routes (events, member auth, projects, team, join, contact)
app/admin.py      admin login + CRUD + inboxes (applications, messages, registrations)
app/models.py     SQLAlchemy models        app/forms.py    validation
app/security.py   scrypt hashing, CSRF, rate limiting
app/content.py    club copy, leader, core team (edit here)
app/templates/    Jinja pages              app/static/     compiled CSS + small vanilla JS
assets/input.css  Tailwind source (theme tokens + components)
tests/            pytest suite
```

## Changing styles
The compiled stylesheet `app/static/css/app.css` is committed. After editing templates or `assets/input.css`:
`npm install && npm run css` (Tailwind v4 CLI).

## Tests
`pip install -r requirements-dev.txt && pytest`

## Deploy
Set `SECRET_KEY`, `ADMIN_*`, `COOKIE_SECURE=1` (HTTPS) and `DATABASE_URL` (e.g. Postgres: `postgresql+psycopg://…`, add the driver to requirements),
then run `uvicorn app.main:app --host 0.0.0.0 --port $PORT` behind HTTPS.

## Differences from the MERN version
- Server-rendered pages + session cookie auth (CSRF-protected forms) instead of a JSON API + JWT in localStorage. There is no `/api`.
- SQLite by default instead of MongoDB (SQLAlchemy, so Postgres/MySQL work via `DATABASE_URL`).
- Members can register, log in, view their profile, and see event registrations linked to their account. Guest event registration remains available.
- Admin additions: events have a Published checkbox (drafts hidden from the public), projects take a comma-separated stack, URLs must be http(s).
- Set `SECRET_KEY` to a stable random value so signed sessions persist across server restarts. Local example credentials are admin `admin` / `local-admin-password` and member `demo` / `Code2ChillDemo123!`; replace them before exposing the app beyond a local development environment. `ADMIN_EMAIL` remains supported for older configurations; `ADMIN_USERNAME` is preferred.
- Event capacity is enforced with a lock + a unique (event, email) constraint. The lock is per process; with several workers, enforce capacity in the DB.
- Rate limiting is in-memory per process.
