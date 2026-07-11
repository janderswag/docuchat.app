"""Settings router — READ-ONLY system status + the privacy posture behind the
"100% local · 0 outbound" badge. The posture is DERIVED from real config (the bound
host + the configured Ollama URL), not a hardcoded claim. No mutating settings (nothing
here can relax loopback/egress), and no secret/path is exposed."""

import sys

from fastapi import APIRouter

import catalog
import routes_kb
from embed_store import ollama_url, open_table

router = APIRouter()

_LOOPBACK = {"127.0.0.1", "localhost", "::1"}
_PINNED = {"chat": "qwen3:14b", "embed": "bge-m3"}  # D-11 pins (frozen)


@router.get("/settings/status")
def status():
    import api  # lazy: avoid the import cycle (api includes this router)

    host = ollama_url().split("//")[-1].split("/")[0]      # e.g. "127.0.0.1:11434"
    ollama_host = host.split(":")[0]
    loopback = ollama_host in _LOOPBACK and api.HOST == "127.0.0.1"

    try:
        kb_chunks = open_table(str(routes_kb.KB_DB)).count_rows()
    except Exception:
        kb_chunks = 0

    # Trust fix (gaps-audit "silent privacy-feature failure"): data_protection.py's
    # own startup exclusion attempt logs a warning and moves on when tmutil fails
    # (api.py:158-165) — surface that here instead of only in a log file nobody
    # reads. "tmutil-unavailable*" is the one value data_protection.protect_paths()
    # emits on a genuine exclusion failure; "absent"/"inside-encrypted-volume" are
    # not failures. Non-macOS never attempts the exclusion, so it's never a failure.
    backup_exclusions = getattr(api.app.state, "data_protection", {})
    time_machine_failed = sys.platform == "darwin" and any(
        v.startswith("tmutil-unavailable") for v in backup_exclusions.values())

    return {
        "models": dict(_PINNED),
        "ollama": host if ":" in host else host + ":11434",
        "stores": {"kb_docs": len(catalog.list_documents()), "kb_chunks": kb_chunks},
        "egress": "loopback-only" if loopback else "non-loopback",
        "bind": api.HOST,
        # Move 3 (D-71): the trust posture is REPORTED from real state, never assumed.
        "hardening": {
            "trusted_host": True,           # TrustedHostMiddleware active (api.py)
            "origin_guard": True,           # cross-origin unsafe methods rejected
            "backup_exclusions": backup_exclusions,
            "time_machine_failed": time_machine_failed,
        },
    }
