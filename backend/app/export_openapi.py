"""Writes `backend/openapi.json` for the frontend codegen step.

Usage: python -m app.export_openapi

The frontend's `generate:api-types` script (openapi-typescript) reads this
file to produce `frontend/src/api/schema.d.ts` — never hand-transcribed
(Consistency Conventions).
"""

from __future__ import annotations

import json
from pathlib import Path

from app.main import app

OUTPUT_PATH = Path(__file__).resolve().parent.parent / "openapi.json"


def export_openapi() -> None:
    schema = app.openapi()
    OUTPUT_PATH.write_text(json.dumps(schema, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote {OUTPUT_PATH}")


if __name__ == "__main__":
    export_openapi()
