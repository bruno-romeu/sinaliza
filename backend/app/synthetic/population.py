"""Pure construction of one synthetic population — zero I/O, zero SQLAlchemy
imports (AD-2's spirit applied to the generator: this module is unit-testable
in complete isolation from a database).

Every id, split assignment and name index is derived from `(config.seed, ...)`
via `app.synthetic.rng` — never drawn from ambient randomness — so calling
`build_population` twice with the same `GenerationConfig` always returns the
same population, byte for byte (RNF-13's determinism claim, verified in
`tests/test_synthetic_generation.py` by content hash, not row count).
"""

from __future__ import annotations

import math
import uuid
from dataclasses import dataclass
from decimal import Decimal

from app.domain.student import DatasetSplit, SyntheticProfile
from app.synthetic.calibration import TRAIN_EVAL_SPLIT_RATIO
from app.synthetic.names import compose_classroom_name, compose_name
from app.synthetic.profiles import assign_profile
from app.synthetic.rng import derived_key, stable_uuid


@dataclass(frozen=True)
class GenerationConfig:
    seed: int
    student_count: int = 200
    students_per_classroom: int = 25
    #: Named, documented constant (Story 2.3) — see
    #: `calibration.TRAIN_EVAL_SPLIT_RATIO` for provenance/rationale. Never
    #: redeclare the bare number here; change the calibration constant
    #: instead if the default proportion ever needs to move.
    train_ratio: float | Decimal = TRAIN_EVAL_SPLIT_RATIO.value
    academic_year: int = 2026

    def __post_init__(self) -> None:
        if self.seed < 0:
            raise ValueError("seed must be >= 0")
        if self.student_count < 1:
            raise ValueError("student_count must be >= 1")
        if self.students_per_classroom < 2:
            raise ValueError("students_per_classroom must be >= 2")
        if not (0 < float(self.train_ratio) < 1):
            raise ValueError("train_ratio must be strictly between 0 and 1")


@dataclass(frozen=True)
class GeneratedClassroom:
    id: uuid.UUID
    name: str
    academic_year: int


@dataclass(frozen=True)
class GeneratedStudent:
    id: uuid.UUID
    name: str
    dataset_split: DatasetSplit
    synthetic_profile: SyntheticProfile


@dataclass(frozen=True)
class GeneratedEnrollment:
    id: uuid.UUID
    student_id: uuid.UUID
    classroom_id: uuid.UUID


@dataclass(frozen=True)
class GeneratedPopulation:
    classrooms: tuple[GeneratedClassroom, ...]
    students: tuple[GeneratedStudent, ...]
    enrollments: tuple[GeneratedEnrollment, ...]


def _classroom_sizes(student_count: int, students_per_classroom: int) -> list[int]:
    """Split `student_count` into classroom sizes of `students_per_classroom`
    each, except the last classroom, which absorbs whatever remains
    (Assumption 2) — never an independent, possibly-empty remainder
    classroom.

    A remainder of exactly 1 is folded into the previous classroom instead
    of being left standalone: every classroom must contain both TRAIN and
    EVAL_DEMO students, which is impossible in a classroom of size 1."""
    num_classrooms = math.ceil(student_count / students_per_classroom)
    sizes = [students_per_classroom] * (num_classrooms - 1)
    sizes.append(student_count - students_per_classroom * (num_classrooms - 1))

    if len(sizes) > 1 and sizes[-1] == 1:
        sizes[-2] += sizes.pop()

    return sizes


def build_population(config: GenerationConfig) -> GeneratedPopulation:
    """Deterministically build classrooms, students and enrollments for
    `config`. Every student belongs to exactly one classroom. `dataset_split`
    is assigned per classroom (Design Notes: "Split assigned per classroom,
    not by independent coin flips") so both splits appear in every classroom
    and the realised global ratio is exactly predictable, never a hope about
    independent Bernoulli draws."""
    seed = config.seed
    sizes = _classroom_sizes(config.student_count, config.students_per_classroom)

    classrooms: list[GeneratedClassroom] = []
    students: list[GeneratedStudent] = []
    enrollments: list[GeneratedEnrollment] = []

    # Carry the rounding remainder across classrooms so the realised global
    # TRAIN share matches `train_ratio` exactly, rather than drifting from
    # rounding each classroom's local count independently (e.g. 200
    # students / 25 per classroom / train_ratio=0.7 would otherwise round
    # 17.5 up in every classroom, yielding a global ratio of 0.72).
    train_ratio = float(config.train_ratio)
    cumulative_students = 0
    cumulative_train_target = 0

    student_index = 0
    for classroom_index, size in enumerate(sizes):
        classroom_id = stable_uuid(seed, "classroom", str(classroom_index))
        classrooms.append(
            GeneratedClassroom(
                id=classroom_id,
                name=compose_classroom_name(classroom_index),
                academic_year=config.academic_year,
            )
        )

        # Build this classroom's students first (ids known), then order them
        # by their own derived split key so TRAIN/EVAL_DEMO assignment never
        # depends on insertion/global order — only on (seed, student_id).
        classroom_student_ids: list[uuid.UUID] = []
        for _ in range(size):
            student_id = stable_uuid(seed, "student", str(student_index))
            classroom_student_ids.append(student_id)
            student_index += 1

        ordered = sorted(
            classroom_student_ids,
            key=lambda sid: derived_key(seed, "split", str(sid)),
        )
        cumulative_students += size
        new_cumulative_train_target = round(cumulative_students * train_ratio)
        train_count = new_cumulative_train_target - cumulative_train_target

        # Every classroom must contain both TRAIN and EVAL_DEMO students, so
        # clamp this classroom's share into [1, size - 1]. The cumulative
        # bookkeeping is updated with the *clamped* value (not the raw
        # ratio-derived one) so later classrooms' diffs stay consistent with
        # what was actually assigned here.
        train_count = max(1, min(size - 1, train_count))
        cumulative_train_target += train_count
        train_ids = set(ordered[:train_count])

        # Re-walk in original (name-index) order so student `name`/`id`
        # pairing stays stable regardless of the split-ordering step above.
        for offset, student_id in enumerate(classroom_student_ids):
            name_index = student_index - size + offset
            split = DatasetSplit.TRAIN if student_id in train_ids else DatasetSplit.EVAL_DEMO
            students.append(
                GeneratedStudent(
                    id=student_id,
                    name=compose_name(name_index),
                    dataset_split=split,
                    synthetic_profile=assign_profile(seed, student_id),
                )
            )
            enrollment_id = stable_uuid(seed, "enrollment", str(name_index))
            enrollments.append(
                GeneratedEnrollment(
                    id=enrollment_id,
                    student_id=student_id,
                    classroom_id=classroom_id,
                )
            )

    return GeneratedPopulation(
        classrooms=tuple(classrooms),
        students=tuple(students),
        enrollments=tuple(enrollments),
    )
