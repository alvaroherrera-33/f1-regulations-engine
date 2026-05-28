"""
Rate-limiting utilities shared across routes.

Provides:
- get_client_ip: key function for slowapi that reads the real IP from
  X-Forwarded-For (trusts the leftmost value; prevents header spoofing).
- make_feedback_token / verify_feedback_token: lightweight HMAC tokens so
  that only the browser that received a ChatResponse can submit feedback for it.
"""
import hashlib
import hmac
import secrets
import time

from fastapi import Request

# ── IP extraction ─────────────────────────────────────────────────────────────


def get_client_ip(request: Request) -> str:
    """
    Return the real client IP.

    Render (and most reverse-proxies) append the client IP as the *first*
    value in X-Forwarded-For.  We take that first value so an attacker cannot
    spoof their IP by adding extra entries.
    """
    xff = request.headers.get("x-forwarded-for", "")
    ip = xff.split(",")[0].strip()
    if not ip and request.client:
        ip = request.client.host
    return ip or "unknown"


# ── HMAC feedback token ───────────────────────────────────────────────────────

_FEEDBACK_SECRET: str = ""  # lazy-initialised on first call (per-process)


def _get_feedback_secret() -> str:
    """
    Return the HMAC secret for feedback tokens.

    Uses FEEDBACK_HMAC_SECRET env var if set, otherwise generates a random
    per-process secret (tokens expire on server restart — fine for free tier).
    """
    global _FEEDBACK_SECRET
    if not _FEEDBACK_SECRET:
        try:
            from app.config import settings  # avoid circular import at module level
            _FEEDBACK_SECRET = settings.feedback_hmac_secret or secrets.token_hex(32)
        except Exception:
            _FEEDBACK_SECRET = secrets.token_hex(32)
    return _FEEDBACK_SECRET


def make_feedback_token(query_id: int) -> str:
    """
    Generate a 16-char HMAC-SHA256 token for *query_id* in the current hour.

    The token encodes the hour so it cannot be replayed after at most 2 hours.
    """
    msg = f"{query_id}.{int(time.time()) // 3600}".encode()
    return hmac.new(_get_feedback_secret().encode(), msg, hashlib.sha256).hexdigest()[:16]


def verify_feedback_token(query_id: int, token: str) -> bool:
    """
    Return True if *token* is valid for *query_id* in the current or previous hour.

    Accepts one hour of leeway to handle browser sessions that span an hour boundary.
    Uses hmac.compare_digest to prevent timing attacks.
    """
    secret = _get_feedback_secret()
    now = int(time.time()) // 3600
    for hour in (now, now - 1):
        msg = f"{query_id}.{hour}".encode()
        expected = hmac.new(secret.encode(), msg, hashlib.sha256).hexdigest()[:16]
        if hmac.compare_digest(expected, token):
            return True
    return False
