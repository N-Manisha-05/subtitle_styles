import asyncio
import logging
import os
import time
from contextlib import asynccontextmanager
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

logger = logging.getLogger(__name__)

# How long (hours) to keep finished output files before auto-deleting them.
OUTPUT_TTL_HOURS = int(os.getenv("OUTPUT_TTL_HOURS", "24"))

# Maximum allowed upload file size in MB (enforced in process.py).
MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "500"))


async def _cleanup_old_outputs() -> None:
    """Background task: delete output files older than OUTPUT_TTL_HOURS every hour."""
    outputs_dir = Path("outputs")
    while True:
        await asyncio.sleep(3600)  # run every hour
        if not outputs_dir.exists():
            continue
        cutoff = time.time() - OUTPUT_TTL_HOURS * 3600
        deleted = 0
        for f in outputs_dir.iterdir():
            if f.is_file() and f.stat().st_mtime < cutoff:
                try:
                    f.unlink()
                    deleted += 1
                except OSError:
                    pass
        if deleted:
            logger.info("[CLEANUP] Deleted %d output file(s) older than %dh", deleted, OUTPUT_TTL_HOURS)


@asynccontextmanager
async def lifespan(app):
    """Start background tasks on startup; cancel them on shutdown."""
    task = asyncio.create_task(_cleanup_old_outputs())
    logger.info("[STARTUP] Output cleanup task started (TTL=%dh, interval=1h)", OUTPUT_TTL_HOURS)
    yield
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    logger.info("[SHUTDOWN] Output cleanup task stopped.")


from fastapi import FastAPI
from api.routers import subtitle, image, audio, video, composite, process

app = FastAPI(
    title="Subtitle & Media Toolkit API",
    description=(
        "REST API to burn animated subtitles, overlay images/videos, "
        "and mix/replace audio into videos using FFmpeg."
    ),
    version="2.0.0",
    lifespan=lifespan,
)

app.include_router(subtitle.router)
app.include_router(image.router)
app.include_router(audio.router)
app.include_router(video.router)
app.include_router(composite.router)
app.include_router(process.router)


@app.get("/", tags=["Health"])
def health():
    return {
        "status": "ok",
        "message": "Subtitle Toolkit API is running",
        "version": "2.0.0",
    }
