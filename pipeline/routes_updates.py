"""Updates router (UX-8): read-only status for the one-click update surface.
See updates.py for the egress disclosure and guardrails."""

from fastapi import APIRouter

import updates

router = APIRouter()


@router.get("/updates/status")
def update_status():
    return updates.status()
