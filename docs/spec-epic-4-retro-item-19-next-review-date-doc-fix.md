---
title: 'Correct stale next_review_date claim in epic-4-context.md'
type: 'chore'
created: '2026-10-15'
status: 'done'
baseline_commit: '9166d036243ed10fcde40a83fdd7664996978357'
route: 'oneshot'
route_source: 'auto'
review: ''
review_source: ''
lenses_ran: []
review_loop_iteration: 0
context: []
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** `docs/epic-4-context.md:45` claims `FollowUp.next_review_date` "is read only by a live query inside `GET /home` (`WHERE next_review_date <= as_of()`)". This is false: a repo-wide search finds `next_review_date` is always written as `None`/`NULL` (`open_follow_up.py:57`, `domain/follow_up.py:10`) and never appears in any query filter anywhere in `backend/`. The field is unused end to end across all 5 Epic 4 stories.

**Approach:** Correct the claim to state the field is persisted but unused by any query today, matching the already-accurate adjacent sentences in `domain/follow_up.py:10` and `infrastructure/db/models.py:269` ("no UI/query reads it in this story").

</frozen-after-approval>

## Implementation Notes

Oneshot: a single doc-line correction, no code change.

## Verification

**Manual checks (if no CLI):**
- `docs/epic-4-context.md:45` no longer claims a live query reads `next_review_date`.
