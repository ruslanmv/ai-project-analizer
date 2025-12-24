"""
FastAPI web application for browser-based code analysis.

Provides REST API endpoints for:
- File upload
- Analysis job management
- Real-time progress streaming (SSE)
- Results retrieval
"""

from __future__ import annotations

import asyncio
import shutil
import tempfile
import uuid
from pathlib import Path
from typing import Any

from fastapi import BackgroundTasks, FastAPI, File, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from ..core.config import settings
from ..core.exceptions import AnalyzerError
from ..core.logging import get_logger
from ..services.workflow import analyze_codebase

# ═══════════════════════════════════════════════════════════════════════════
# Application Setup
# ═══════════════════════════════════════════════════════════════════════════
logger = get_logger(__name__)

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Enterprise-grade AI-powered codebase analysis",
    docs_url="/docs",
    redoc_url="/redoc",
)

# Determine paths
BASE_DIR = Path(__file__).parent.parent.parent.parent
STATIC_DIR = BASE_DIR / "static"
TEMPLATES_DIR = BASE_DIR / "templates"

# Mount static files and templates if they exist
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

if TEMPLATES_DIR.exists():
    templates = Jinja2Templates(directory=TEMPLATES_DIR)
else:
    templates = None

# ═══════════════════════════════════════════════════════════════════════════
# In-Memory Job Store (Use Redis in production)
# ═══════════════════════════════════════════════════════════════════════════
jobs: dict[str, dict[str, Any]] = {}
event_queues: dict[str, asyncio.Queue[str]] = {}


# ═══════════════════════════════════════════════════════════════════════════
# Request/Response Models
# ═══════════════════════════════════════════════════════════════════════════
class AnalyzeResponse(BaseModel):
    """Response after initiating analysis."""

    job_id: str
    status: str = "started"
    message: str = "Analysis started"


class JobStatusResponse(BaseModel):
    """Job status response."""

    job_id: str
    status: str
    artifacts: dict[str, Any] | None = None


# ═══════════════════════════════════════════════════════════════════════════
# Background Task
# ═══════════════════════════════════════════════════════════════════════════
async def _analyze_job(job_id: str, zip_path: Path) -> None:
    """
    Background task to run analysis.

    Args:
        job_id: Unique job identifier
        zip_path: Path to uploaded ZIP file
    """
    queue = event_queues[job_id]

    try:
        logger.info("analysis_started", job_id=job_id, path=str(zip_path))
        queue.put_nowait("event:ANALYSIS_STARTED")

        # Run synchronous analysis in thread pool
        loop = asyncio.get_event_loop()
        results = await loop.run_in_executor(
            None,
            analyze_codebase,
            zip_path,
            settings.beeai_model,
        )

        # Store results
        jobs[job_id]["artifacts"] = results.to_dict()
        jobs[job_id]["status"] = "completed"

        queue.put_nowait("event:ANALYSIS_COMPLETED")
        logger.info("analysis_completed", job_id=job_id)

    except AnalyzerError as e:
        error_msg = f"Analysis failed: {e.message}"
        queue.put_nowait(f"error:{error_msg}")
        jobs[job_id]["artifacts"] = {"error": error_msg}
        jobs[job_id]["status"] = "failed"
        logger.error("analysis_failed", job_id=job_id, error=str(e), **e.context)

    except Exception as e:
        error_msg = f"Unexpected error: {e}"
        queue.put_nowait(f"error:{error_msg}")
        jobs[job_id]["artifacts"] = {"error": error_msg}
        jobs[job_id]["status"] = "failed"
        logger.exception("analysis_unexpected_error", job_id=job_id)

    finally:
        queue.put_nowait("close")
        # Cleanup temp file
        if zip_path.exists():
            try:
                shutil.rmtree(zip_path.parent, ignore_errors=True)
            except Exception as e:
                logger.warning("cleanup_failed", error=str(e))


# ═══════════════════════════════════════════════════════════════════════════
# API Routes
# ═══════════════════════════════════════════════════════════════════════════
@app.get("/")
async def root(request: Request) -> Any:
    """Serve upload page."""
    if templates:
        return templates.TemplateResponse("upload.html", {"request": request})
    return {"message": "AI Project Analyzer API", "version": settings.app_version}


@app.get("/health")
async def health() -> dict[str, str]:
    """
    Health check endpoint.

    Returns:
        Health status
    """
    return {"status": "ok", "version": settings.app_version}


@app.post("/analyse", response_model=AnalyzeResponse)
async def analyze_zip(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(..., description="ZIP archive to analyze"),
) -> AnalyzeResponse:
    """
    Upload ZIP file and start analysis.

    Args:
        background_tasks: FastAPI background tasks
        file: Uploaded ZIP file

    Returns:
        Job ID and status

    Raises:
        HTTPException: If file is invalid
    """
    # Validate file extension
    if not file.filename or not file.filename.lower().endswith(".zip"):
        raise HTTPException(
            status_code=400,
            detail="Only .zip files are accepted",
        )

    # Create temporary directory
    job_id = uuid.uuid4().hex
    tmp_dir = Path(tempfile.mkdtemp(prefix=f"ai_analyzer_{job_id}_"))
    dest_path = tmp_dir / file.filename

    logger.info(
        "upload_received",
        job_id=job_id,
        filename=file.filename,
    )

    try:
        # Save uploaded file
        with dest_path.open("wb") as out:
            shutil.copyfileobj(file.file, out)

        # Create job entry and event queue
        event_queues[job_id] = asyncio.Queue()
        jobs[job_id] = {
            "status": "pending",
            "artifacts": None,
            "filename": file.filename,
        }

        # Schedule background analysis
        background_tasks.add_task(_analyze_job, job_id, dest_path)

        return AnalyzeResponse(
            job_id=job_id,
            message=f"Analysis started for {file.filename}",
        )

    except Exception as e:
        logger.exception("upload_failed", job_id=job_id)
        # Cleanup on error
        shutil.rmtree(tmp_dir, ignore_errors=True)
        raise HTTPException(
            status_code=500,
            detail=f"Upload failed: {e}",
        ) from e


@app.get("/events/{job_id}")
async def sse_events(job_id: str) -> StreamingResponse:
    """
    Server-Sent Events stream for job progress.

    Args:
        job_id: Job identifier

    Returns:
        SSE stream

    Raises:
        HTTPException: If job not found
    """
    if job_id not in event_queues:
        raise HTTPException(status_code=404, detail="Job not found")

    queue = event_queues[job_id]

    async def event_generator() -> Any:
        """Generate SSE events."""
        while True:
            msg = await queue.get()
            if msg == "close":
                break
            yield f"data: {msg}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
    )


@app.get("/result/{job_id}")
async def get_result(job_id: str) -> JSONResponse:
    """
    Get analysis results.

    Args:
        job_id: Job identifier

    Returns:
        Analysis results or status

    Raises:
        HTTPException: If job not found
    """
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")

    job_data = jobs[job_id]
    return JSONResponse(
        {
            "job_id": job_id,
            "status": job_data["status"],
            "artifacts": job_data.get("artifacts"),
        }
    )


@app.get("/jobs")
async def list_jobs() -> dict[str, Any]:
    """
    List all jobs.

    Returns:
        Dictionary of all jobs
    """
    return {
        "total": len(jobs),
        "jobs": [
            {
                "job_id": job_id,
                "status": job_data["status"],
                "filename": job_data.get("filename"),
            }
            for job_id, job_data in jobs.items()
        ],
    }


# ═══════════════════════════════════════════════════════════════════════════
# Startup/Shutdown Events
# ═══════════════════════════════════════════════════════════════════════════
@app.on_event("startup")
async def startup_event() -> None:
    """Application startup."""
    logger.info(
        "application_started",
        environment=settings.environment,
        model=settings.beeai_model,
    )


@app.on_event("shutdown")
async def shutdown_event() -> None:
    """Application shutdown."""
    logger.info("application_shutdown")
