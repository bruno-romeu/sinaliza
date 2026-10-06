"""The only two sources of determinism in the synthetic generator.

Determinism here comes from **explicit derivation, never from ambient state**.
A single `random.Random(seed)` consumed top-to-bottom would work today and
break tomorrow: the moment Story 2.2 draws one extra value early in the
sequence, every value drawn after it shifts, and an already-published base
stops being reproducible from its recorded seed. Deriving each value from its
own `(seed, labels)` address removes that coupling — a new generated concern
can only change the values it addresses itself.

Both primitives are *specified* algorithms (RFC 4122 UUIDv5 over SHA-1;
BLAKE2b), stable across CPython versions, platforms and word sizes. That
matters: `random.shuffle`/`random.choice` are implementation details whose
output has changed between CPython releases, so "byte-identical on any
machine" would be a hope about the standard library rather than a property of
the construction.
"""

from __future__ import annotations

import hashlib
import uuid

#: Fixed module namespace for every generated id. Frozen forever: changing it
#: silently re-keys every base ever generated, which is exactly the failure
#: `SyntheticGenerationRun.generator_version` exists to make visible.
NAMESPACE = uuid.UUID("6f2b7b2a-0d4e-5c9f-9a3a-1e5d9c7b40e1")

#: 16 bytes — plenty of entropy for ordering/selection, and narrow enough that
#: the derived integers stay cheap to compare.
_DIGEST_SIZE = 16


def _address(seed: int, labels: tuple[str, ...]) -> str:
    """The canonical `"{seed}|{label}|{label}..."` address of one derived
    value. Kept in one place so `stable_uuid` and `derived_key` can never
    drift apart on separator or ordering."""
    return "|".join((str(seed), *labels))


def stable_uuid(seed: int, *labels: str) -> uuid.UUID:
    """The id of the entity addressed by `(seed, *labels)`.

    Same address, same uuid — on any machine, in any process, forever.
    """
    return uuid.uuid5(NAMESPACE, _address(seed, labels))


def derived_key(seed: int, *labels: str) -> int:
    """A deterministic non-negative integer for the choice addressed by
    `(seed, *labels)` — used as a sort key or a modular selector, never as a
    stream position."""
    digest = hashlib.blake2b(
        _address(seed, labels).encode("utf-8"), digest_size=_DIGEST_SIZE
    ).digest()
    return int.from_bytes(digest, "big")
