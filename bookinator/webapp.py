from __future__ import annotations

import html
import shutil
import tempfile
import threading
import traceback
import urllib.parse
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


_JOB_DEFAULTS = {"running": False, "current_stage": None, "log": [], "error": None}


def _job(name: str) -> dict:
    with _jobs_lock:
        return dict(_jobs.get(name, _JOB_DEFAULTS))


def _set_job(name: str, **updates) -> None:
    with _jobs_lock:
        job = _jobs.setdefault(name, dict(_JOB_DEFAULTS))
        job.update(updates)


def _append_log(name: str, message: str) -> None:
    print(f"[{name}] {message}", flush=True)
    with _jobs_lock:
        job = _jobs.setdefault(name, dict(_JOB_DEFAULTS))
        job["log"] = (job["log"] + [message])[-50:]


PAGE_CSS = """
:root {
  --bg: #faf7f1; --bg-elevated: #ffffff; --border: #e7e0d3;
  --text: #241f2e; --text-muted: #6b6478;
  --accent: #5b3fa0; --accent-strong: #46316f;
  --green: #2f7a4f; --green-bg: #e1f2e6;
  --amber: #9c6b00; --amber-bg: #fdf0cf;
  --red: #a4293a; --red-bg: #fbe6e9;
  --shadow: 0 1px 2px rgba(36,31,46,0.06), 0 4px 14px rgba(36,31,46,0.06);
  --radius: 0.85rem;
}
@media (prefers-color-scheme: dark) {
  :root {
    --bg: #171320; --bg-elevated: #221c30; --border: #362c48;
    --text: #ede9f5; --text-muted: #a89cc0;
    --accent: #bda4f5; --accent-strong: #7c5be0;
    --green: #6bcf95; --green-bg: #17301f;
    --amber: #f0c34d; --amber-bg: #3a2f10;
    --red: #ef8394; --red-bg: #3a1820;
    --shadow: 0 1px 2px rgba(0,0,0,0.35), 0 8px 20px rgba(0,0,0,0.4);
  }
}
* { box-sizing: border-box; }
body { margin: 0; background: var(--bg); color: var(--text);
       font-family: -apple-system, "Segoe UI", Helvetica, Arial, sans-serif;
       line-height: 1.5; }
.wrap { max-width: 760px; margin: 0 auto; padding: 0 1.25rem 4rem; }
a { color: var(--accent); }
header.top { padding: 1.75rem 0 1rem; }
header.top a.brand { display: flex; align-items: center; gap: 0.55rem;
       text-decoration: none; color: var(--text); font-weight: 700;
       font-size: 1.5rem; letter-spacing: 0.01em;
       font-family: Georgia, "Iowan Old Style", "Palatino Linotype", serif; }
h1 { font-family: Georgia, "Iowan Old Style", "Palatino Linotype", serif;
     font-size: 1.7rem; margin: 0 0 0.2rem; }
h2 { font-size: 0.85rem; text-transform: uppercase; letter-spacing: 0.08em;
     color: var(--text-muted); margin: 2rem 0 0.75rem; font-weight: 700; }
p.tagline { color: var(--text-muted); margin-top: 0; }
.card { background: var(--bg-elevated); border: 1px solid var(--border);
        border-radius: var(--radius); box-shadow: var(--shadow); }
.project-list { display: flex; flex-direction: column; }
.project-list a.project-row { display: flex; align-items: center;
       justify-content: space-between; padding: 0.9rem 1.1rem;
       text-decoration: none; color: var(--text); }
.project-list a.project-row + a.project-row { border-top: 1px solid var(--border); }
.project-list a.project-row:hover { color: var(--accent); }
.project-row .chev { color: var(--text-muted); }
.empty { color: var(--text-muted); padding: 1.25rem; text-align: center; }
form.new-project { padding: 1.25rem; display: flex; flex-direction: column; gap: 0.8rem; }
label.field { display: flex; flex-direction: column; gap: 0.35rem;
       font-size: 0.82rem; color: var(--text-muted); font-weight: 600; }
input[name="name"], input[type="file"] {
       padding: 0.55rem 0.7rem; border-radius: 0.55rem; border: 1px solid var(--border);
       background: var(--bg); color: var(--text); font-size: 0.95rem; font-family: inherit; }
button { cursor: pointer; padding: 0.55rem 1.1rem; border-radius: 0.6rem;
         border: 1px solid var(--border); background: var(--bg-elevated); color: var(--text);
         font-size: 0.88rem; font-weight: 700; transition: border-color 0.15s, color 0.15s; }
button:hover:not(:disabled) { border-color: var(--accent); color: var(--accent); }
button:disabled { opacity: 0.5; cursor: not-allowed; }
button.primary { background: var(--accent-strong); border-color: var(--accent-strong); color: #fff; }
button.primary:hover:not(:disabled) { filter: brightness(1.15); color: #fff; }
.run-all-row { margin: 1.25rem 0; }
.stages { padding: 0.3rem 1.1rem; }
.stage { display: flex; align-items: center; gap: 0.9rem; padding: 0.85rem 0; }
.stage + .stage { border-top: 1px solid var(--border); }
.stage-marker { width: 1.9rem; height: 1.9rem; border-radius: 999px; flex: none;
       display: flex; align-items: center; justify-content: center;
       font-size: 0.85rem; font-weight: 700; border: 2px solid var(--border); color: var(--text-muted); }
.stage-marker.done { background: var(--green-bg); border-color: var(--green); color: var(--green); }
.stage-marker.running { background: var(--amber-bg); border-color: var(--amber); color: var(--amber);
       animation: pulse 1.4s ease-in-out infinite; }
.stage-marker .dot { width: 0.5rem; height: 0.5rem; border-radius: 50%; background: currentColor; display: block; }
@keyframes pulse { 0%, 100% { box-shadow: 0 0 0 0 rgba(240,195,77,0.45); }
                   50% { box-shadow: 0 0 0 6px rgba(240,195,77,0); } }
.stage-info { flex: 1; min-width: 0; }
.stage-name { font-weight: 600; font-size: 0.95rem; }
.stage-status { font-size: 0.76rem; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.05em; }
.stage-status.done { color: var(--green); }
.stage-status.running { color: var(--amber); }
form.inline { display: inline; }
.log-window { border-radius: var(--radius); overflow: hidden; border: 1px solid var(--border); }
.log-titlebar { background: #2a2438; padding: 0.55rem 0.8rem; display: flex; gap: 0.4rem; }
.log-dot { width: 0.6rem; height: 0.6rem; border-radius: 999px; }
.log-dot.r { background: #e5675f; } .log-dot.y { background: #e5b567; } .log-dot.g { background: #65c467; }
.log { background: #171225; color: #d8d2e8; padding: 0.9rem 1rem;
       font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
       font-size: 0.82rem; white-space: pre-wrap; max-height: 240px; overflow-y: auto; }
.error-box { background: var(--red-bg); border: 1px solid var(--red); color: var(--red);
       padding: 0.9rem 1rem; border-radius: var(--radius); white-space: pre-wrap;
       font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size: 0.82rem; }
.artifacts { display: flex; flex-wrap: wrap; gap: 0.5rem; }
.artifacts a { display: inline-flex; align-items: center; gap: 0.4rem; text-decoration: none;
       padding: 0.4rem 0.8rem; border-radius: 999px; border: 1px solid var(--border);
       color: var(--text); font-size: 0.82rem; background: var(--bg-elevated); }
.artifacts a:hover { border-color: var(--accent); color: var(--accent); }
.empty-inline { color: var(--text-muted); font-size: 0.85rem; }
"""

_FAVICON_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">'
    '<text y=".9em" font-size="90">\U0001f4d6</text></svg>'
)
FAVICON_HREF = "data:image/svg+xml," + urllib.parse.quote(_FAVICON_SVG)


def render_page(title: str, body: str, refresh: bool = False) -> HTMLResponse:
    meta_refresh = '<meta http-equiv="refresh" content="3">' if refresh else ""
    html_doc = f"""<!doctype html>
<html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)}</title>
<link rel="icon" href="{FAVICON_HREF}">
{meta_refresh}<style>{PAGE_CSS}</style></head>
<body><div class="wrap">
<header class="top"><a class="brand" href="/">\U0001f4d6 Bookinator</a></header>
{body}
</div></body></html>"""
    return HTMLResponse(html_doc)


@app.get("/", response_class=HTMLResponse)
def index() -> HTMLResponse:
    projects = pipeline.list_projects(_config)
    if projects:
        rows = "".join(
            f'<a class="project-row" href="/projects/{html.escape(p)}">'
            f'<span>{html.escape(p)}</span><span class="chev">&rarr;</span></a>'
            for p in projects
        )
        projects_html = f'<div class="card project-list">{rows}</div>'
    else:
        projects_html = '<div class="card empty">No projects yet - create one below.</div>'

    body = f"""
    <p class="tagline">Podcast &rarr; fantasy novel pipeline.</p>
    <h2>Projects</h2>
    {projects_html}
    <h2>New project</h2>
    <form class="card new-project" action="/projects" method="post" enctype="multipart/form-data">
      <label class="field">Project name
        <input name="name" placeholder="uprooted-1-1" required pattern="[A-Za-z0-9_-]+">
      </label>
      <label class="field">Source mp3
        <input type="file" name="mp3" accept="audio/mpeg,.mp3" required>
      </label>
      <button type="submit" class="primary">Create project</button>
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
                _set_job(name, current_stage=stage)
                _append_log(name, f"Running: {pipeline.STAGE_LABELS[stage]}...")
                message = pipeline.run_stage(_config, name, stage)
                _append_log(name, f"Done: {message}")
        except Exception as exc:  # noqa: BLE001
            _append_log(name, f"Error: {exc}")
            _set_job(name, error=f"{exc}\n\n{traceback.format_exc()}")
        finally:
            _set_job(name, running=False, current_stage=None)

    threading.Thread(target=target, daemon=True).start()


@app.get("/projects/{name}", response_class=HTMLResponse)
def project_dashboard(name: str) -> HTMLResponse:
    paths = pipeline.ProjectPaths.for_project(_config, name)
    if not paths.base.exists():
        raise HTTPException(404, "Project not found")

    status = pipeline.stage_status(paths)
    job = _job(name)

    stage_rows = []
    for i, stage in enumerate(pipeline.STAGES, start=1):
        done = status[stage]
        is_running = job["running"] and job.get("current_stage") == stage
        state = "running" if is_running else ("done" if done else "pending")
        state_text = "running" if is_running else ("done" if done else "not started")
        marker = "&check;" if state == "done" else ('<span class="dot"></span>' if state == "running" else str(i))
        disabled = "disabled" if job["running"] else ""
        stage_rows.append(f"""
        <div class="stage">
          <div class="stage-marker {state}">{marker}</div>
          <div class="stage-info">
            <div class="stage-name">{html.escape(pipeline.STAGE_LABELS[stage])}</div>
            <div class="stage-status {state}">{state_text}</div>
          </div>
          <form class="inline" action="/projects/{html.escape(name)}/run/{stage}" method="post">
            <button {disabled}>{'Re-run' if done else 'Run'}</button>
          </form>
        </div>""")

    log_html = "\n".join(html.escape(line) for line in job["log"]) or "(no output yet)"
    error_html = (
        f'<h2>Error</h2><div class="error-box">{html.escape(job["error"])}</div>'
        if job["error"] else ""
    )

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
        f'<a href="/projects/{html.escape(name)}/file/{rel}" target="_blank">'
        f'\U0001f4c4 {html.escape(label)}</a>'
        for label, rel in artifacts
    ) or '<span class="empty-inline">No artifacts yet.</span>'

    disabled_all = "disabled" if job["running"] else ""
    body = f"""
    <p><a href="/">&larr; All projects</a></p>
    <h1>{html.escape(name)}</h1>
    <div class="run-all-row">
      <form action="/projects/{html.escape(name)}/run-all" method="post">
        <button class="primary" {disabled_all}>Run all remaining stages</button>
      </form>
    </div>
    <div class="card stages">
      {"".join(stage_rows)}
    </div>
    <h2>Log</h2>
    <div class="log-window">
      <div class="log-titlebar">
        <span class="log-dot r"></span><span class="log-dot y"></span><span class="log-dot g"></span>
      </div>
      <div class="log">{log_html}</div>
    </div>
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
