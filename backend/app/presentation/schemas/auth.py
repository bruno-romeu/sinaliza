from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    email: str = Field(min_length=1, max_length=255)
    password: str = Field(min_length=1, max_length=255)


class UserOut(BaseModel):
    id: str
    name: str
    email: str
    # Single-value on purpose (AD-8: never a second role) — reflected in the
    # API contract and the generated frontend types, not just the domain enum.
    role: Literal["COORDENACAO_PEDAGOGICA"]


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut
