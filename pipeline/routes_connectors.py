"""Connectors router (UX-6) — watched folders, the local-first import surface.

GET lists watched folders with live status (exists / missing). POSTs add/remove.
All verbs are POST/GET (no PUT/PATCH/DELETE — the structural lock in test_api
stays intact). No network egress: a "connector" here is a directory on disk.
"""

from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

import catalog
import watchers

router = APIRouter()


class NewFolder(BaseModel):
    matter: str
    path: str


class RemoveFolder(BaseModel):
    id: int


@router.get("/connectors/folders")
def list_folders():
    """Folders with LIVE status: exists on disk, matter still real, and the
    heartbeat (last scan + files added since app start) — the row must read as
    alive or say why it is not (council 2026-07-11 Move 4)."""
    import time as _time
    out = []
    for wf in catalog.list_watch_folders():
        stats = watchers.folder_stats(wf["id"]) or {}
        last = stats.get("last_scan")
        out.append({**wf,
                    "exists": Path(wf["path"]).is_dir(),
                    "matter_exists": bool(catalog.get_matter(wf["matter_slug"])),
                    "checked_s_ago": (round(_time.time() - last)
                                      if last else None),
                    "files_added": stats.get("files_added", 0)})
    return {"folders": out, "poll_seconds": watchers.POLL_SECONDS}


@router.post("/connectors/folders")
def add_folder(body: NewFolder):
    # Unfiled is a legal target (same lazy-create convention as connector
    # imports): a shared scanner tray should feed the confirm-then-file tray,
    # not a matter (Sam's contamination note).
    if body.matter == "unfiled" and not catalog.get_matter("unfiled"):
        try:
            catalog.create_matter("Unfiled")
        except ValueError:
            pass    # concurrent lazy-create raced us; the matter now exists
    if not catalog.get_matter(body.matter):
        raise HTTPException(status_code=400, detail=f"unknown matter: {body.matter!r}")
    try:
        folder = watchers.validate_folder(body.path)
        row = catalog.add_watch_folder(body.matter, folder)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return row


@router.post("/connectors/folders/remove")
def remove_folder(body: RemoveFolder):
    catalog.remove_watch_folder(body.id)
    return {"ok": True}
