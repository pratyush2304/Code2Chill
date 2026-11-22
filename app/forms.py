"""Tiny declarative validation: spec rows are (name, label, kind, required)."""
import re
from datetime import date

EMAIL = re.compile(r"^\S+@\S+\.\S+$")


def clean(form, spec):
    """Return (values, errors). Values keep the raw strings so a failed form can be re-shown."""
    out, errors = {}, {}
    for name, label, kind, required in spec:
        raw = form.get(name)
        v = "" if raw is None else str(raw).strip()
        if kind == "bool":
            out[name] = bool(raw)
            continue
        if len(v) > 2000:
            errors[name] = f"{label} is too long."
        elif not v:
            if required:
                errors[name] = f"{label} is required."
            out[name] = None if kind in ("date", "int") else ""
            continue
        elif kind == "email" and not EMAIL.match(v):
            errors[name] = "Enter a valid email address."
        elif kind == "url" and not re.match(r"^https?://\S+$", v):
            errors[name] = f"{label} must start with http:// or https://"
        elif kind == "date":
            try:
                out[name] = date.fromisoformat(v); continue
            except ValueError:
                errors[name] = "Enter a valid date."
        elif kind == "int":
            if v.lstrip("-").isdigit() and 0 <= int(v) <= 10**6:
                out[name] = int(v); continue
            errors[name] = f"{label} must be a whole number."
        out[name] = v.lower() if kind == "email" else v
    return out, errors
