"""Single source of truth for "today" (AD-5) — pure Python, zero framework
imports (AD-2).

Every read that must never leak data beyond "now" — the rolling window in
`domain/trajectory.py` and the `filter_as_of` repository helper alike —
computes "today" through `as_of()`, never through `date.today()` /
`datetime.now()` directly, so the whole demo can be pinned to a fixed date
via `SINALIZA_DEMO_AS_OF` without touching any call site.

The override is read fresh from `os.environ` on every call (never cached at
import time or via `functools.lru_cache`) so a test can flip the env var
between assertions and a long-lived process would still track a change to
it without a restart.
"""

from __future__ import annotations

import os
from datetime import date, datetime, timezone

_ENV_VAR = "SINALIZA_DEMO_AS_OF"


def as_of() -> date:
    """Returns "today" — real UTC date, unless `SINALIZA_DEMO_AS_OF` (an
    ISO-8601 date string, e.g. "2026-09-24") is set, in which case that date
    is used instead (demo/test-only override)."""
    override = os.environ.get(_ENV_VAR)
    if override:
        try:
            return date.fromisoformat(override)
        except ValueError as exc:
            raise ValueError(
                f"{_ENV_VAR}={override!r} is not a valid ISO-8601 date "
                "(expected format: YYYY-MM-DD)."
            ) from exc
    return datetime.now(timezone.utc).date()
