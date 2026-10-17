"""Offline ML pipeline package (spec-5-1).

Everything under `app/ml/` only imports domain models/ports, never
`presentation/` (spec Always) — this package has no FastAPI route, no
`composition.py` wiring, and is reachable only via `python -m app.ml.train`
(AD-3).
"""
