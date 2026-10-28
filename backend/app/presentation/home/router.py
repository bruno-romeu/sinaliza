"""`GET /home`, `GET /home/search` — behind `get_current_user`, same as every
other product route (spec-3-3 Boundaries & Constraints).

`GET /home` only ever reads already-committed `TrajectoryChange` rows
(`GetHomeService` -> `list_recent`, paginated by `changes_page`/
`changes_page_size`) — it never recomputes
trajectory; that stays request-scoped to `GET /students/{id}/trajectory`.
Its `in_progress_follow_ups` list is paginated via `follow_ups_page`/
`follow_ups_page_size` (open-case volume is operator-driven and otherwise
grows unbounded over a real deployment's lifetime).

`GET /home/search?q=` matches `q` against student name or classroom name
(case-insensitive), paginated via `page`/`page_size`; an empty/no-match query
is a normal 200 with an empty `results` array, never an error.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.application.home.get_home import (
    DEFAULT_CHANGES_PAGE_SIZE,
    DEFAULT_FOLLOW_UPS_PAGE_SIZE,
    GetHomeService,
)
from app.application.home.search_students import DEFAULT_PAGE_SIZE, SearchStudentsService
from app.composition import get_get_home_service, get_search_students_service
from app.presentation.auth.dependencies import get_current_user
from app.presentation.schemas.home import (
    HomeOut,
    InProgressFollowUpOut,
    RecentChangeOut,
    StudentSearchOut,
    StudentSearchResultOut,
)

router = APIRouter(dependencies=[Depends(get_current_user)])


@router.get("/home", response_model=HomeOut)
def get_home(
    follow_ups_page: int = Query(default=1, ge=1),
    follow_ups_page_size: int = Query(default=DEFAULT_FOLLOW_UPS_PAGE_SIZE, ge=1, le=100),
    changes_page: int = Query(default=1, ge=1),
    changes_page_size: int = Query(default=DEFAULT_CHANGES_PAGE_SIZE, ge=1, le=100),
    service: GetHomeService = Depends(get_get_home_service),
) -> HomeOut:
    result = service.execute(
        follow_ups_page, follow_ups_page_size, changes_page, changes_page_size
    )
    return HomeOut(
        recent_changes=[
            RecentChangeOut(
                student_id=recent.trajectory_change.student_id,
                student_name=recent.student_name,
                type=recent.trajectory_change.type.value,
                description=recent.trajectory_change.description,
                detected_at=recent.trajectory_change.detected_at,
            )
            for recent in result.recent_changes.items
        ],
        recent_changes_total=result.recent_changes.total,
        recent_changes_page=result.recent_changes.page,
        recent_changes_page_size=result.recent_changes.page_size,
        in_progress_follow_ups=[
            InProgressFollowUpOut(
                id=active.follow_up.id,
                student_id=active.follow_up.student_id,
                student_name=active.student_name,
                status=active.follow_up.status.value,
            )
            for active in result.active_follow_ups.items
        ],
        in_progress_follow_ups_total=result.active_follow_ups.total,
        in_progress_follow_ups_page=result.active_follow_ups.page,
        in_progress_follow_ups_page_size=result.active_follow_ups.page_size,
    )


@router.get("/home/search", response_model=StudentSearchOut)
def search_students(
    q: str = Query(default=""),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=DEFAULT_PAGE_SIZE, ge=1, le=100),
    service: SearchStudentsService = Depends(get_search_students_service),
) -> StudentSearchOut:
    page_result = service.execute(q, page, page_size)
    return StudentSearchOut(
        results=[
            StudentSearchResultOut(id=item.id, name=item.name, classroom_name=item.classroom_name)
            for item in page_result.results
        ],
        count=len(page_result.results),
        total=page_result.total,
        page=page_result.page,
        page_size=page_result.page_size,
    )
