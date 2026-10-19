"""Validation + normalisation layer.

Decides whether an incoming record is *well-formed and believable*.
Anything that fails is classified as FALSE_POSITIVE (junk / fake / malformed).
"""
import re

EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9\-]+(\.[A-Za-z0-9\-]+)*\.[A-Za-z]{2,}$")
FAKE_NAMES = {"test", "testing", "asdf", "qwerty", "abc", "xxx", "none", "null",
              "na", "n/a", "unknown", "admin", "user", "name", "foo", "bar", "demo"}
FAKE_DOMAINS = {"example.com", "example.org", "test.com", "mailinator.com",
                "10minutemail.com", "guerrillamail.com", "tempmail.com",
                "yopmail.com", "trashmail.com"}


def normalise_name(name: str) -> str:
    name = re.sub(r"[^a-z\s]", "", (name or "").lower())
    return re.sub(r"\s+", " ", name).strip()


def normalise_email(email: str) -> str:
    email = (email or "").strip().lower()
    if "@" not in email:
        return email
    local, domain = email.rsplit("@", 1)
    if domain in ("gmail.com", "googlemail.com"):      # gmail ignores dots and +tags
        local = local.split("+")[0].replace(".", "")
        domain = "gmail.com"
    else:
        local = local.split("+")[0]
    return f"{local}@{domain}"


def normalise_phone(phone: str) -> str:
    digits = re.sub(r"\D", "", phone or "")
    return digits[-10:] if len(digits) >= 10 else digits


def validate(record: dict):
    """Return (is_valid, reason)."""
    name = (record.get("name") or "").strip()
    email = (record.get("email") or "").strip()
    phone = (record.get("phone") or "").strip()

    if not name or not email:
        return False, "name and email are required"
    n = normalise_name(name)
    if len(n) < 2:
        return False, "name is too short or has no letters"
    if n in FAKE_NAMES or re.fullmatch(r"(.)\1{2,}", n.replace(" ", "")):
        return False, f"name looks like placeholder/fake data: '{name}'"
    if not EMAIL_RE.match(email):
        return False, f"invalid email format: '{email}'"
    if email.rsplit("@", 1)[1].lower() in FAKE_DOMAINS:
        return False, "email uses a disposable/placeholder domain"
    if phone:
        p = normalise_phone(phone)
        if len(p) != 10 or len(set(p)) == 1:
            return False, f"invalid phone number: '{phone}'"
    return True, "ok"
