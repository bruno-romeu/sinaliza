"""`application/home` has no error cases of its own (spec-3-3 I/O Matrix):
`GET /home` only ever reads already-committed rows, and `GET /home/search`
has no "not found" case — an empty match is a normal, successful result.
This module intentionally defines nothing yet; it exists so a future error
case has an obvious home, mirroring `application/trajectory/errors.py`'s
precedent."""

from __future__ import annotations
