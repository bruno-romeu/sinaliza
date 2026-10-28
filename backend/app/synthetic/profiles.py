"""Deterministic trajectory rules for each `SyntheticProfile` (Story 2.2).

Pure module: zero I/O, zero SQLAlchemy imports, unit-testable standalone
(AD-2's spirit, Story 2.1's `population.py` precedent). Every value this
module returns is derived only from `(seed, student_id, ...)` via
`app.synthetic.rng` — never ambient randomness — so the same seed reproduces
a byte-identical base (RNF-13).

Rules implemented here (spec Boundaries & Constraints):

- `STABLE` holds every rate constant across the year.
- `FALLING_ATTENDANCE` linearly interpolates the daily presence probability
  from `DAILY_ATTENDANCE_RATE_BASELINE` to `DAILY_ATTENDANCE_RATE_AT_RISK_FLOOR`
  over the school-day sequence; grades/assignments unaffected.
- `FALLING_GRADES` shifts the student's grade quantile (the same quantile
  `STABLE` uses against `GRADE_DISTRIBUTION`) linearly toward 0 over the
  period sequence (Assumption 2: `shifted = quantile * (1 - progress)`);
  attendance/assignments unaffected.
- `COMBINED_DETERIORATION` applies the attendance decay, the grade-quantile
  shift, and a linear interpolation of assignment non-delivery from
  `ASSIGNMENT_NON_DELIVERY_RATE_BASELINE` to
  `ASSIGNMENT_NON_DELIVERY_RATE_AT_RISK_CEILING`, all together.

Progress fraction is indexed by school day for attendance (finer-grained,
Assumption 3) and by period for grades/assignments; in both cases
`index / (total - 1)`, or `1.0` when only one point exists so a
deteriorating profile still shows its worst state instead of behaving like
`STABLE` under division-by-zero avoidance (Assumption 3).
"""

from __future__ import annotations

import uuid
from decimal import ROUND_HALF_UP, Decimal

from app.domain.assignment_submission import AssignmentSubmissionStatus
from app.domain.student import SyntheticProfile
from app.synthetic.calibration import (
    ASSIGNMENT_NON_DELIVERY_RATE_AT_RISK_CEILING,
    ASSIGNMENT_NON_DELIVERY_RATE_BASELINE,
    ASSIGNMENT_PARTIAL_DELIVERY_RATE_BASELINE,
    DAILY_ATTENDANCE_RATE_AT_RISK_FLOOR,
    DAILY_ATTENDANCE_RATE_BASELINE,
    GRADE_DISTRIBUTION,
    GRADE_SCALE_MAX,
    GRADE_SCALE_MIN,
    SYNTHETIC_PROFILE_PROPORTIONS,
)
from app.synthetic.rng import derived_key

#: `derived_key` draws from a 16-byte (128-bit) digest (`rng._DIGEST_SIZE`).
#: Dividing by this span turns the integer into a fraction in `[0, 1)`.
_KEY_SPACE = 2**128

#: Half-width of the per-período quantile variation around a student's
#: habitual level for a subject (spec-ui-4).
_GRADE_PERIOD_VARIATION = 0.06

#: Profiles whose grade-quantile shift (Assumption 2) applies.
_GRADE_DECLINING_PROFILES = (SyntheticProfile.FALLING_GRADES, SyntheticProfile.COMBINED_DETERIORATION)

#: Profiles whose daily-attendance decay applies.
_ATTENDANCE_DECLINING_PROFILES = (
    SyntheticProfile.FALLING_ATTENDANCE,
    SyntheticProfile.COMBINED_DETERIORATION,
)

#: Profiles whose assignment non-delivery ceiling applies.
_ASSIGNMENT_DECLINING_PROFILES = (SyntheticProfile.COMBINED_DETERIORATION,)


def _fraction(seed: int, *labels: str) -> float:
    """A deterministic fraction in `[0, 1)` addressed by `(seed, *labels)`."""
    return derived_key(seed, *labels) / _KEY_SPACE


def _progress(index: int, total: int) -> float:
    """`index / (total - 1)`, or `1.0` when `total <= 1` (Assumption 3) so a
    deteriorating profile still reaches its worst state rather than
    silently behaving like `STABLE` under division-by-zero avoidance."""
    if total <= 1:
        return 1.0
    return index / (total - 1)


def assign_profile(seed: int, student_id: uuid.UUID) -> SyntheticProfile:
    """Weighted draw against `SYNTHETIC_PROFILE_PROPORTIONS`.

    Keys are iterated in sorted order (not the mapping's declared order) so
    the cumulative-boundary assignment is legible and independent of
    `calibration.py`'s internal declaration order (Design Notes)."""
    proportions = SYNTHETIC_PROFILE_PROPORTIONS.value
    fraction = _fraction(seed, "profile", str(student_id))

    cumulative = 0.0
    sorted_keys = sorted(proportions)
    for key in sorted_keys:
        cumulative += proportions[key]
        if fraction < cumulative:
            return SyntheticProfile(key)

    # Floating-point safety net: cumulative may land a hair under 1.0 due to
    # summation error, and `fraction` can get arbitrarily close to 1.0.
    return SyntheticProfile(sorted_keys[-1])


def attendance_is_present(
    seed: int,
    student_id: uuid.UUID,
    profile: SyntheticProfile,
    day_index: int,
    total_days: int,
) -> bool:
    """Whether `student_id` is present on the school day at `day_index`
    (0-based, out of `total_days`)."""
    baseline = DAILY_ATTENDANCE_RATE_BASELINE.value
    if profile in _ATTENDANCE_DECLINING_PROFILES:
        floor = DAILY_ATTENDANCE_RATE_AT_RISK_FLOOR.value
        progress = _progress(day_index, total_days)
        probability = baseline + (floor - baseline) * progress
    else:
        probability = baseline

    fraction = _fraction(seed, "attendance", str(student_id), str(day_index))
    return fraction < probability


def grade_value(
    seed: int,
    student_id: uuid.UUID,
    period_id_label: str,
    subject: str,
    profile: SyntheticProfile,
    period_index: int,
    total_periods: int,
) -> Decimal:
    """The grade `student_id` receives in `subject` for the period at
    `period_index` (0-based, out of `total_periods`).

    Draws a per-(student, subject) habitual quantile plus a small
    per-período variation (spec-ui-4) — "the same quantile `STABLE` uses
    against `GRADE_DISTRIBUTION`" (spec) — then, for
    declining profiles, shifts it linearly toward 0 by the period's
    progress fraction (Assumption 2) before mapping it into
    `GRADE_DISTRIBUTION`'s bands."""
    # spec-ui-4: each student has a habitual level per subject, with a small
    # variation between períodos. Drawing a fresh quantile every período made
    # a STABLE student's average jump by several points between bimestres,
    # which read as a "queda de notas" for a student who had not changed.
    base = _fraction(seed, "grade_level", str(student_id), subject)
    noise = (_fraction(seed, "grade_quantile", str(student_id), subject, period_id_label) - 0.5) * (
        2 * _GRADE_PERIOD_VARIATION
    )
    quantile = min(max(base + noise, 0.0), 0.999999)
    if profile in _GRADE_DECLINING_PROFILES:
        progress = _progress(period_index, total_periods)
        quantile = quantile * (1 - progress)

    bands = GRADE_DISTRIBUTION.value
    cumulative = 0.0
    chosen = bands[-1]
    band_start = cumulative
    for band in bands:
        next_cumulative = cumulative + band.share
        if quantile < next_cumulative or band is bands[-1]:
            chosen = band
            band_start = cumulative
            break
        cumulative = next_cumulative

    fraction_within_band = (quantile - band_start) / chosen.share if chosen.share > 0 else 0.0
    span = float(chosen.max_value) - float(chosen.min_value)
    raw_value = float(chosen.min_value) + fraction_within_band * span

    quantized = Decimal(str(raw_value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    # Clamp: a value exactly at a band boundary plus rounding could in
    # principle round a hair outside [GRADE_SCALE_MIN, GRADE_SCALE_MAX].
    return min(max(quantized, GRADE_SCALE_MIN.value), GRADE_SCALE_MAX.value)


def assignment_submission_status(
    seed: int,
    student_id: uuid.UUID,
    assignment_id_label: str,
    profile: SyntheticProfile,
    period_index: int,
    total_periods: int,
) -> AssignmentSubmissionStatus:
    """The submission status `student_id` produces for the assignment
    addressed by `assignment_id_label`, in the period at `period_index`."""
    baseline = ASSIGNMENT_NON_DELIVERY_RATE_BASELINE.value
    if profile in _ASSIGNMENT_DECLINING_PROFILES:
        ceiling = ASSIGNMENT_NON_DELIVERY_RATE_AT_RISK_CEILING.value
        progress = _progress(period_index, total_periods)
        non_delivery = baseline + (ceiling - baseline) * progress
    else:
        non_delivery = baseline

    partial = ASSIGNMENT_PARTIAL_DELIVERY_RATE_BASELINE.value
    fraction = _fraction(seed, "assignment_submission", str(student_id), assignment_id_label)

    if fraction < non_delivery:
        return AssignmentSubmissionStatus.NOT_DELIVERED
    if fraction < non_delivery + partial:
        return AssignmentSubmissionStatus.PARTIAL
    return AssignmentSubmissionStatus.DELIVERED
