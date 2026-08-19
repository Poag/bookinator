from __future__ import annotations

import html
import shutil
import tempfile
import threading
import traceback
from pathlib import Path

from fastapi import FastAPI, Form, HTTPException, UploadFile
from fastapi.responses import HTMLResponse, PlainTextResponse, RedirectResponse

from . import pipeline
from .config import Config

app = FastAPI(title="Bookinator")

_config = Config.load()

# In-memory per-project job tracking. Stage completion itself is derived
# from files on disk (see pipeline.stage_status), so this only needs to
# track "is something running right now" and the last message/error - it's
# fine for this to reset on container restart.
_jobs_lock = threading.Lock()
_jobs: dict[str, dict] = {}


def _job(name: str) -> dict:
    with _jobs_lock:
        return dict(_jobs.get(name, {"running": False, "log": [], "error": None}))


def _set_job(name: str, **updates) -> None:
    with _jobs_lock:
        job = _jobs.setdefault(name, {"running": False, "log": [], "error": None})
        job.update(updates)


def _append_log(name: str, message: str) -> None:
    with _jobs_lock:
        job = _jobs.setdefault(name, {"running": False, "log": [], "error": None})
        job["log"] = (job["log"] + [message])[-50:]


PAGE_CSS = """
body { font-family: -apple-system, Segoe UI, Helvetica, Arial, sans-serif;
       max-width: 860px; margin: 2rem auto; padding: 0 1rem; color: #1a1a1a; }
h1, h2 { margin-bottom: 0.3rem; }
.stage { display: flex; align-items: center; gap: 0.75rem; padding: 0.6rem 0;
         border-bottom: 1px solid #eee; }
.stage-name { flex: 1; }
.badge { font-size: 0.8rem; padding: 0.15rem 0.5rem; border-radius: 1rem; }
.badge.done { background: #dcf5e0; color: #1e7c34; }
.badge.pending { background: #eee; color: #666; }
.badge.running { background: #fff3cd; color: #8a6d00; }
button { cursor: pointer; padding: 0.35rem 0.8rem; border-radius: 0.4rem;
         border: 1px solid #ccc; background: #f7f7f7; }
button:hover { background: #eee; }
.project-list a { display: block; padding: 0.5rem 0; }
.log { background: #111; color: #ddd; padding: 0.75rem; border-radius: 0.4rem;
       font-family: monospace; font-size: 0.85rem; white-space: pre-wrap;
       max-height: 220px; overflow-y: auto; }
.error { color: #b00020; white-space: pre-wrap; font-family: monospace; font-size: 0.85rem; }
form.inline { display: inline; }
.artifacts a { margin-right: 1rem; }
"""


def render_page(title: str, body: str, refresh: bool = False) -> HTMLResponse:
    meta_refresh = '<meta http-equiv="refresh" content="3">' if refresh else ""
    html_doc = f"""<!doctype html>
<html><head><meta charset="utf-8"><title>{html.escape(title)}</title>
{meta_refresh}<style>{PAGE_CSS}</style></head>
<body>{body}</body></html>"""
    return HTMLResponse(html_doc)


@app.get("/", response_class=HTMLResponse)
def index() -> HTMLResponse:
    projects = pipeline.list_projects(_config)
    items = "".join(f'<a href="/projects/{html.escape(p)}">{html.escape(p)}</a>' for p in projects)
    if not items:
        items = "<p><em>No projects yet.</em></p>"
    body = f"""
    <h1>Bookinator</h1>
    <p>Podcast &rarr; fantasy novel pipeline.</p>
    <h2>Projects</h2>
    <div class="project-list">{items}</div>
    <h2>New project</h2>
    <form action="/projects" method="post" enctype="multipart/form-data">
      <p><input name="name" placeholder="project-name" required pattern="[A-Za-z0-9_-]+"></p>
      <p><input type="file" name="mp3" accept="audio/mpeg,.mp3" required></p>
      <button type="submit">Create project</button>
    </form>
    """
    return render_page("Bookinator", body)


@app.post("/projects")
def create_project(name: str = Form(...), mp3: UploadFile | None = None) -> RedirectResponse:
    if mp3 is None or not mp3.filename:
        raise HTTPException(400, "An mp3 file is required")
    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tmp:
        shutil.copyfileobj(mp3.file, tmp)
        tmp_path = Path(tmp.name)
    try:
        pipeline.create_project(_config, name, tmp_path, mp3.filename)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    finally:
        tmp_path.unlink(missing_ok=True)
    return RedirectResponse(f"/projects/{name}", status_code=303)


def _run_in_background(name: str, stages: list[str]) -> None:
    def target() -> None:
        _set_job(name, running=True, error=None)
        try:
            for stage in stages:
                _append_log(name, f"Running: {pipeline.STAGE_LABELS[stage]}...")
                message = pipeline.run_stage(_config, name, stage)
                _append_log(name, f"Done: {message}")
        except Exception as exc:  # noqa: BLE001
            _set_job(name, error=f"{exc}\n\n{traceback.format_exc()}")
        finally:
            _set_job(name, running=False)

    threading.Thread(target=target, daemon=True).start()


@app.get("/projects/{name}", response_class=HTMLResponse)
def project_dashboard(name: str) -> HTMLResponse:
    paths = pipeline.ProjectPaths.for_project(_config, name)
    if not paths.base.exists():
        raise HTTPException(404, "Project not found")

    status = pipeline.stage_status(paths)
    job = _job(name)

    stage_rows = []
    for stage in pipeline.STAGES:
        done = status[stage]
        badge = "running" if job["running"] else ("done" if done else "pending")
        badge_text = "running" if job["running"] else ("done" if done else "not started")
        disabled = "disabled" if job["running"] else ""
        stage_rows.append(f"""
        <div class="stage">
          <span class="stage-name">{html.escape(pipeline.STAGE_LABELS[stage])}</span>
          <span class="badge {badge}">{badge_text}</span>
          <form class="inline" action="/projects/{html.escape(name)}/run/{stage}" method="post">
            <button {disabled}>{'Re-run' if done else 'Run'}</button>
          </form>
        </div>""")

    log_html = "\n".join(html.escape(line) for line in job["log"]) or "(no output yet)"
    error_html = f'<h2>Error</h2><div class="error">{html.escape(job["error"])}</div>' if job["error"] else ""

    artifacts = []
    if (paths.transcript / "transcript.json").exists():
        artifacts.append(("transcript.json", "transcript/transcript.json"))
    if (paths.chapters / "chapters.json").exists():
        artifacts.append(("chapters.json", "chapters/chapters.json"))
    if (paths.chapters / "notes.json").exists():
        artifacts.append(("notes.json", "chapters/notes.json"))
    if paths.bible.exists():
        artifacts.append(("bible.json", "bible.json"))
    if paths.drafts.exists():
        for draft in sorted(paths.drafts.glob("chapter_*.md")):
            artifacts.append((draft.name, f"drafts/{draft.name}"))
    if paths.manuscript.exists():
        artifacts.append(("manuscript.md", "manuscript.md"))
    artifacts_html = "".join(
        f'<a href="/projects/{html.escape(name)}/file/{rel}" target="_blank">{html.escape(label)}</a>'
        for label, rel in artifacts
    ) or "(none yet)"

    disabled_all = "disabled" if job["running"] else ""
    body = f"""
    <p><a href="/">&larr; All projects</a></p>
    <h1>{html.escape(name)}</h1>
    <form action="/projects/{html.escape(name)}/run-all" method="post">
      <button {disabled_all}>Run all remaining stages</button>
    </form>
    {"".join(stage_rows)}
    <h2>Log</h2>
    <div class="log">{log_html}</div>
    {error_html}
    <h2>Artifacts</h2>
    <div class="artifacts">{artifacts_html}</div>
    """
    return render_page(f"Bookinator - {name}", body, refresh=job["running"])


@app.post("/projects/{name}/run/{stage}")
def run_stage(name: str, stage: str) -> RedirectResponse:
    paths = pipeline.ProjectPaths.for_project(_config, name)
    if not paths.base.exists():
        raise HTTPException(404, "Project not found")
    if stage not in pipeline.STAGES:
        raise HTTPException(404, "Unknown stage")
    if _job(name)["running"]:
        raise HTTPException(409, "A stage is already running for this project")
    _run_in_background(name, [stage])
    return RedirectResponse(f"/projects/{name}", status_code=303)


@app.post("/projects/{name}/run-all")
def run_all(name: str) -> RedirectResponse:
    paths = pipeline.ProjectPaths.for_project(_config, name)
    if not paths.base.exists():
        raise HTTPException(404, "Project not found")
    if _job(name)["running"]:
        raise HTTPException(409, "A stage is already running for this project")
    status = pipeline.stage_status(paths)
    remaining = [s for s in pipeline.STAGES if not status[s]]
    _run_in_background(name, remaining or pipeline.STAGES)
    return RedirectResponse(f"/projects/{name}", status_code=303)


@app.get("/projects/{name}/file/{rel_path:path}", response_class=PlainTextResponse)
def view_file(name: str, rel_path: str) -> PlainTextResponse:
    paths = pipeline.ProjectPaths.for_project(_config, name)
    target = (paths.base / rel_path).resolve()
    if not str(target).startswith(str(paths.base.resolve())) or not target.is_file():
        raise HTTPException(404, "File not found")
    return PlainTextResponse(target.read_text())


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
