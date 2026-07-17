"""Datetime utilities for UTC-safe operations with SQLite.

SQLite stores datetimes without timezone info (naive). All datetimes
in this codebase represent UTC. This module provides a utc_now()
function that uses the non-deprecated datetime.now(timezone.utc) API
but returns a naive datetime for DB compatibility.
"""
from datetime import datetime, timedelta, timezone

# Fixed clock-skew tolerance for issued certificates (#207): relying parties
# with clocks slightly behind the CA otherwise reject freshly issued certs.
CERT_NOT_BEFORE_SKEW = timedelta(minutes=15)


def cert_not_before() -> datetime:
    """notBefore for newly issued certificates: utc_now() minus a fixed skew."""
    return utc_now() - CERT_NOT_BEFORE_SKEW


def utc_now() -> datetime:
    """Return current UTC time as a naive datetime.

    Uses the non-deprecated ``datetime.now(timezone.utc)`` internally,
    then strips tzinfo so the result is comparable with naive datetimes
    stored in SQLite via SQLAlchemy.
    """
    return datetime.now(timezone.utc).replace(tzinfo=None)


def to_naive_utc(dt: datetime | None) -> datetime | None:
    """Normalize aware UTC datetimes to naive UTC for DB / utc_now() comparisons."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt
    return dt.astimezone(timezone.utc).replace(tzinfo=None)


def utc_isoformat(dt):
    """Return an ISO 8601 UTC string ending in 'Z', or None.

    Handles both naive-UTC datetimes (from SQLAlchemy/utc_now) and
    timezone-aware datetimes (from the cryptography library etc.).
    """
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.isoformat() + 'Z'
    from datetime import timezone
    return dt.astimezone(timezone.utc).isoformat().replace('+00:00', 'Z')
