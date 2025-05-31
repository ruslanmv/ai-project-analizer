"""
app.py  –  Minimal FastAPI wrapper around the BeeAI runtime.

Endpoints
---------
GET  /               -> HTML upload wizard
POST /analyse        -> accepts multipart ZIP, returns {job_id}
GET  /events/{id}    -> Server-Sent Events stream of agent progress
GET  /result/{id}    -> final JSON artefacts
GET  /health         -> {"status": "ok"}
"""

from __future__ import annotations

import asyncio
import shutil
import tempfile
import uuid
from pathlib import Path
from typing import Dict

from fastapi import (
    BackgroundTasks,
    FastAPI,
    File,
    HTTPException,
    Request,
    UploadFile,
)
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from src.workflows import run_workflow

# ---------------------------------------------------------------------------- #
#  In-memory job store (for demo purposes; swap with Redis for prod)
# ---------------------------------------------------------------------------- #
jobs: Dict[str, dict] = {}
event_queues: Dict[str, asyncio.Queue[str]] = {}

# ---------------------------------------------------------------------------- #
#  FastAPI setup
# ---------------------------------------------------------------------------- #
app = FastAPI(title="AI Project-Analyser")

BASE_DIR = Path(__file__).parent
templates = Jinja2Templates(directory=BASE_DIR / "templates")
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")


# ---------------------------------------------------------------------------- #
#  Helper: background analysis coroutine
# ---------------------------------------------------------------------------- #
async def _analyse_job(job_id: str, zip_path: Path) -> None:
    """Runs the BeeAI workflow; pushes progress strings to SSE queue."""
    queue = event_queues[job_id]

    def _on_event(e):  # beeai runtime callback
        queue.put_nowait(f"event:{e['type']}")

    try:
        artefacts = run_workflow(
            zip_path,
            print_events=False,  # we handle events manually
        )
        jobs[job_id]["artefacts"] = artefacts
        queue.put_nowait("event:WORKFLOW_DONE")
    except Exception as exc:  # pragma: no cover
        queue.put_nowait(f"error:{exc}")
        jobs[job_id]["artefacts"] = {"error": str(exc)}
    finally:
        queue.put_nowait("close")
        # cleanup temp upload
        shutil.rmtree(zip_path.parent, ignore_errors=True)


# ---------------------------------------------------------------------------- #
#  Routes
# ---------------------------------------------------------------------------- #
@app.get("/", include_in_schema=False)
async def upload_page(request: Request):
    return templates.TemplateResponse("upload.html", {"request": request})


@app.post("/analyse")
async def analyse_zip(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(..., description="ZIP archive to analyse"),
):
    if not file.filename.lower().endswith(".zip"):
        raise HTTPException(400, "Only .zip files are accepted")

    job_id = uuid.uuid4().hex
    tmp_dir = Path(tempfile.mkdtemp(prefix="ai_upload_"))
    dest = tmp_dir / file.filename
    with dest.open("wb") as out:
        shutil.copyfileobj(file.file, out)

    # create job entry & SSE queue
    event_queues[job_id] = asyncio.Queue()
    jobs[job_id] = {"artefacts": None}

    background_tasks.add_task(_analyse_job, job_id, dest)
    return {"job_id": job_id}


@app.get("/events/{job_id}")
async def sse_events(job_id: str):
    if job_id not in event_queues:
        raise HTTPException(404, "Unknown job")

    queue = event_queues[job_id]

    async def event_generator():
        while True:
            msg = await queue.get()
            if msg == "close":
                break
            yield f"data: {msg}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.get("/result/{job_id}")
async def job_result(job_id: str):
    if job_id not in jobs:
        raise HTTPException(404, "Unknown job")
    return JSONResponse(jobs[job_id]["artefacts"] or {"status": "running"})


@app.get("/health")
async def health():
    return {"status": "ok"}
