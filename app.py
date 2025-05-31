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
import logging
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
#  Configure logging for this module
# ---------------------------------------------------------------------------- #
LOG = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(module)s.%(funcName)s:%(lineno)d | ★ %(message)s",
    datefmt="%H:%M:%S",
    force=True,
)

# ---------------------------------------------------------------------------- #
#  In-memory job store (for demo purposes; swap with Redis for prod)
# ---------------------------------------------------------------------------- #
jobs: Dict[str, dict] = {}
event_queues: Dict[str, asyncio.Queue[str]] = {}

# ---------------------------------------------------------------------------- #
#  FastAPI setup
# ---------------------------------------------------------------------------- #
app = FastAPI(title="AI Project-Analyser")
LOG.info("FastAPI app initialized")

BASE_DIR = Path(__file__).parent
templates = Jinja2Templates(directory=BASE_DIR / "templates")
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
LOG.info("Mounted static files and templates")


# ---------------------------------------------------------------------------- #
#  Helper: background analysis coroutine
# ---------------------------------------------------------------------------- #
async def _analyse_job(job_id: str, zip_path: Path) -> None:
    """Runs the BeeAI workflow; pushes progress strings to SSE queue."""
    LOG.info("[_analyse_job] Started background job %r with zip_path=%r", job_id, zip_path)
    queue = event_queues[job_id]

    def _on_event(e):  # beeai runtime callback
        LOG.debug("[_analyse_job] Received agent event: %r", e)
        queue.put_nowait(f"event:{e['type']}")

    try:
        LOG.info("[_analyse_job] Invoking run_workflow() for job %r", job_id)
        # NOTE: run_workflow currently does not accept an event callback, so we rely on print_events=False
        artefacts = run_workflow(
            zip_path,
            print_events=False,  # we handle events manually
        )
        LOG.info("[_analyse_job] run_workflow() completed for job %r", job_id)
        jobs[job_id]["artefacts"] = artefacts
        LOG.info("[_analyse_job] Stored artefacts for job %r", job_id)
        queue.put_nowait("event:WORKFLOW_DONE")
        LOG.debug("[_analyse_job] Emitted WORKFLOW_DONE for job %r", job_id)
    except Exception as exc:  # pragma: no cover
        LOG.exception("[_analyse_job] Exception in run_workflow for job %r: %s", job_id, exc)
        queue.put_nowait(f"error:{exc}")
        jobs[job_id]["artefacts"] = {"error": str(exc)}
        LOG.info("[_analyse_job] Stored error artefact for job %r", job_id)
    finally:
        LOG.info("[_analyse_job] Cleaning up temporary directory %r for job %r", zip_path.parent, job_id)
        queue.put_nowait("close")
        shutil.rmtree(zip_path.parent, ignore_errors=True)
        LOG.info("[_analyse_job] Temp directory removed for job %r", job_id)


# ---------------------------------------------------------------------------- #
#  Routes
# ---------------------------------------------------------------------------- #
@app.get("/", include_in_schema=False)
async def upload_page(request: Request):
    LOG.info("[upload_page] GET / - rendering upload page")
    return templates.TemplateResponse("upload.html", {"request": request})


@app.post("/analyse")
async def analyse_zip(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(..., description="ZIP archive to analyse"),
):
    LOG.info("[analyse_zip] POST /analyse called with filename=%r", file.filename)

    if not file.filename.lower().endswith(".zip"):
        LOG.warning("[analyse_zip] Uploaded file is not a .zip: %r", file.filename)
        raise HTTPException(400, "Only .zip files are accepted")

    job_id = uuid.uuid4().hex
    LOG.info("[analyse_zip] Generated job_id=%r", job_id)

    tmp_dir = Path(tempfile.mkdtemp(prefix="ai_upload_"))
    LOG.debug("[analyse_zip] Created temporary upload directory %r for job %r", tmp_dir, job_id)
    dest = tmp_dir / file.filename
    LOG.info("[analyse_zip] Saving uploaded file to %r", dest)
    with dest.open("wb") as out:
        shutil.copyfileobj(file.file, out)
    LOG.info("[analyse_zip] File saved for job %r", job_id)

    # create job entry & SSE queue
    event_queues[job_id] = asyncio.Queue()
    jobs[job_id] = {"artefacts": None}
    LOG.debug("[analyse_zip] Initialized job store and event queue for job %r", job_id)

    background_tasks.add_task(_analyse_job, job_id, dest)
    LOG.info("[analyse_zip] Background task scheduled for job %r", job_id)
    return {"job_id": job_id}


@app.get("/events/{job_id}")
async def sse_events(job_id: str):
    LOG.info("[sse_events] GET /events/%r called", job_id)
    if job_id not in event_queues:
        LOG.warning("[sse_events] Unknown job_id=%r", job_id)
        raise HTTPException(404, "Unknown job")

    queue = event_queues[job_id]
    LOG.debug("[sse_events] Retrieved event queue for job %r", job_id)

    async def event_generator():
        LOG.info("[sse_events] Starting SSE event generator for job %r", job_id)
        while True:
            msg = await queue.get()
            LOG.debug("[sse_events] Got message from queue for job %r: %r", job_id, msg)
            if msg == "close":
                LOG.info("[sse_events] Received close signal for job %r, ending stream", job_id)
                break
            yield f"data: {msg}\n\n"
        LOG.info("[sse_events] SSE event generator finished for job %r", job_id)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.get("/result/{job_id}")
async def job_result(job_id: str):
    LOG.info("[job_result] GET /result/%r called", job_id)
    if job_id not in jobs:
        LOG.warning("[job_result] Unknown job_id=%r", job_id)
        raise HTTPException(404, "Unknown job")

    artefacts = jobs[job_id]["artefacts"]
    if artefacts is None:
        LOG.info("[job_result] Job %r still running; returning status running", job_id)
        return JSONResponse({"status": "running"})
    else:
        LOG.info("[job_result] Job %r completed; returning artefacts", job_id)
        return JSONResponse(artefacts)


@app.get("/health")
async def health():
    LOG.info("[health] GET /health called")
    return {"status": "ok"}


if __name__ == "__main__":
    import os
    import uvicorn

    # Read host and port from environment (fallback to defaults)
    host = os.getenv("APP_HOST", "0.0.0.0")
    port = int(os.getenv("APP_PORT", "8000"))
    LOG.info("[__main__] Starting uvicorn on %s:%d", host, port)

    uvicorn.run("app:app", host=host, port=port, log_level="info")
