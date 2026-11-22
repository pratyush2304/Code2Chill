"""Password hashing (stdlib scrypt), CSRF tokens, and a tiny in-memory rate limiter."""
import hashlib, hmac, os, secrets, time
from collections import defaultdict, deque
from fastapi import HTTPException, Request


def hash_password(pw: str) -> str:
    salt = os.urandom(16)
    h = hashlib.scrypt(pw.encode(), salt=salt, n=2**14, r=8, p=1)
    return f"scrypt${salt.hex()}${h.hex()}"


_DUMMY = hash_password(secrets.token_hex(8))  # compared against when the email is unknown, to keep timing flat


def verify_password(pw: str, stored: str | None) -> bool:
    _, salt, h = (stored or _DUMMY).split("$")
    calc = hashlib.scrypt(pw.encode(), salt=bytes.fromhex(salt), n=2**14, r=8, p=1)
    return hmac.compare_digest(calc.hex(), h) and stored is not None


def csrf_token(request: Request) -> str:
    return request.session.setdefault("csrf", secrets.token_urlsafe(24))


async def verify_csrf(request: Request):
    form = await request.form()
    sent = str(form.get("csrf", ""))
    if not hmac.compare_digest(sent, request.session.get("csrf", "\0")):
        raise HTTPException(403, "Invalid or missing CSRF token. Reload the page and try again.")


_hits: dict[tuple, deque] = defaultdict(deque)


def rate_limit(bucket: str, max_hits: int, window: int = 900):
    """Per-IP sliding window. In-memory, so per process; use Redis or a proxy limit if you scale out."""
    def dep(request: Request):
        key = (bucket, request.client.host if request.client else "?")
        q, t = _hits[key], time.monotonic()
        while q and q[0] < t - window:
            q.popleft()
        if len(q) >= max_hits:
            raise HTTPException(429, "Too many attempts. Please wait a few minutes.")
        q.append(t)
    return dep
