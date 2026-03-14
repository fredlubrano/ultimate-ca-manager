"""Datetime utilities for UTC-safe operations with SQLite.

SQLite stores datetimes without timezone info (naive). All datetimes
in this codebase represent UTC. This module provides a utc_now()
function that uses the non-deprecated datetime.now(timezone.utc) API
but returns a naive datetime for DB compatibility.
"""
from datetime import datetime, timezone


def utc_now() -> datetime:
    """Return current UTC time as a naive datetime.

    Uses the non-deprecated ``datetime.now(timezone.utc)`` internally,
    then strips tzinfo so the result is comparable with naive datetimes
    stored in SQLite via SQLAlchemy.
    """
    return datetime.now(timezone.utc).replace(tzinfo=None)
