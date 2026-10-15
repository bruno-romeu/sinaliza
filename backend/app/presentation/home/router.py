"""`GET /home`, `GET /home/search` — behind `get_current_user`, same as every
other product route (spec-3-3 Boundaries & Constraints).

`GET /home` only ever reads already-committed `TrajectoryChange` rows
(`GetHomeService` -> `list_recent`, capped at 20) — it never recomputes
trajectory; that stays request-scoped to `GET /students/{id}/trajectory`.

`GET /home/search?q=` matches `q` against student name or classroom name
(case-insensitive); an empty/no-match query is a normal 200 with an empty
`results` array, never an error.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.application.home.get_home import GetHomeService
from app.application.home.search_students import SearchStudentsService
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
def get_home(service: GetHomeService = Depends(get_get_home_service)) -> HomeOut:
    result = service.execute()
    return HomeOut(
        recent_changes=[
            RecentChangeOut(
                student_id=recent.trajectory_change.student_id,
                student_name=recent.student_name,
                type=recent.trajectory_change.type.value,
                description=recent.trajectory_change.description,
                detected_at=recent.trajectory_change.detected_at,
            )
            for recent in result.recent_changes
        ],
        in_progress_follow_ups=[
            InProgressFollowUpOut(
                id=active.follow_up.id,
                student_id=active.follow_up.student_id,
                student_name=active.student_name,
                status=active.follow_up.status.value,
            )
            for active in result.active_follow_ups
        ],
    )


@router.get("/home/search", response_model=StudentSearchOut)
def search_students(
    q: str = Query(default=""),
    service: SearchStudentsService = Depends(get_search_students_service),
) -> StudentSearchOut:
    results = service.execute(q)
    return StudentSearchOut(
        results=[
            StudentSearchResultOut(id=result.id, name=result.name, classroom_name=result.classroom_name)
            for result in results
        ],
        count=len(results),
    )
