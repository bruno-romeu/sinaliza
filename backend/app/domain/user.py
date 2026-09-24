"""Domain model for `User` — pure Python, zero framework imports (AD-2).

`role` is kept as an enum (not a hardcoded literal) purely for future
structural extensibility. It must never gain a second member — there is
exactly one profile, Coordenação Pedagógica (AD-8, RF-02). A second
role/"professor" profile is explicitly out of scope; see the spec's
Boundaries & Constraints.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from enum import Enum


class UserRole(str, Enum):
    COORDENACAO_PEDAGOGICA = "COORDENACAO_PEDAGOGICA"


@dataclass(frozen=True)
class User:
    id: uuid.UUID
    name: str
    email: str
    password_hash: str
    role: UserRole
