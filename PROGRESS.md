# PROGRESS.md — Desktop packaging v1.1 follow-up (D-58/D-59)

> Surgical follow-up to the committed v1. No pipeline/verifier changes; no new installs
> (any new dep = [GATE]). Loopback-only, no telemetry. Suite stays green; baselines
> untouched. Do NOT commit (Planner commits).

## 1. Landing page (site/)
- [x] **1a** `site/demo.png` (copied from docs/) replaces the mockup — real app screenshot in the framed window. _site/index.html, styles.css_
- [x] **1b** non-clickable "Demo video — COMING SOON" slot (16:9-ish, dashed/hatched, oxblood play, `pointer-events:none`, a `<figure>` not an `<a>`); `EMBED GOES HERE` comment for the owner's video. Sits to the RIGHT of the screenshot (where owner pointed).
- [x] **1c** hero eyebrow "For solo attorneys" → "For attorneys & law offices"; only "solo" ref in site. Privacy/"100% local" claims untouched.
- [x] **1d** `test_site.py` guards updated (real image, video slot non-clickable + EMBED marker, audience copy general — asserts no "solo attorney"); browser-verified layout. 9 tests green.

## 2. Launcher hardening (desktop/launcher.py)
- [x] **2a** child started with `start_new_session=True`; `install_cleanup(proc)` registers atexit + SIGTERM/SIGINT/SIGHUP handlers → `stop_server`; `stop_server` reaps the whole process group (TERM→KILL). Closes the D-59 orphan-on-hard-kill yellow. (SIGKILL uncatchable → free_port self-heals next launch.)
- [x] **2b** test: a launcher driver is SIGTERM'd → its grandchild uvicorn is reaped + the port freed (would orphan without the handler). 4 launcher tests green.

## FINAL — done; pipeline/verifier/api untouched
- [x] **Suite 260/260 OK** (+3). Only `site/*`, `desktop/launcher.py`, the 2 tests, PROGRESS changed; no pipeline/verifier/api/routes logic touched.
- [x] **Baselines byte-identical**: `13b242de / 0df0525c / 51e13b31`. **No new installs** (no PyInstaller/py2app/signing). Loopback-only, no telemetry preserved.
- Not committed (Planner commits).

### Local commands
```bash
# Landing page (real demo + video slot)
cd ~/projects/legal-doc-intelligence/site && python3 -m http.server 4173   # → http://127.0.0.1:4173
# Re-test the launcher hardening (headless)
cd ~/projects/legal-doc-intelligence && pipeline/.venv/bin/python -m unittest pipeline.tests.test_launcher -v
# Run the launcher for real (opens the window; Ctrl-C now cleanly reaps the server — no orphan)
pipeline/.venv/bin/python desktop/launcher.py
```
