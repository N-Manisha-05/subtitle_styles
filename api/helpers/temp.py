import os
import shutil
import tempfile
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Optional
from fastapi import UploadFile, HTTPException

# All API output videos are saved here
OUTPUTS_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "outputs")
)
os.makedirs(OUTPUTS_DIR, exist_ok=True)


def make_output_path(prefix: str, ext: str = "mp4") -> str:
    """
    Return a unique path inside outputs/ using a timestamp.
    e.g. outputs/subtitle_reveal_20260302_133000.mp4
    """
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{prefix}_{ts}.{ext}"
    return os.path.join(OUTPUTS_DIR, filename)


async def save_upload(upload: UploadFile, dest_dir: str, filename: str = None) -> str:
    """Save an uploaded file to dest_dir and return the full path."""
    name = filename or upload.filename
    dest = os.path.join(dest_dir, name)
    with open(dest, "wb") as f:
        content = await upload.read()
        f.write(content)
    return dest


def download_url(url: str, dest_dir: str, fallback_name: str = "file") -> str:
    """Download a file from a URL into dest_dir and return the local path."""
    filename = Path(url.split("?")[0]).name or fallback_name
    dest = os.path.join(dest_dir, filename)
    try:
        urllib.request.urlretrieve(url, dest)
    except Exception as e:
        raise RuntimeError(f"Failed to download from URL '{url}': {e}")
    return dest


async def resolve_file(
    upload: Optional[UploadFile],
    url: Optional[str],
    dest_dir: str,
    saved_name: str,
    field_label: str,
) -> str:
    """
    Resolve a file from either an upload or a URL.
    Raises HTTPException if neither is provided.
    Upload takes priority over URL if both are given.
    """
    if upload is not None and upload.filename:
        return await save_upload(upload, dest_dir, saved_name)
    elif url:
        return download_url(url, dest_dir, saved_name)
    else:
        raise HTTPException(
            status_code=400,
            detail=f"Provide either '{field_label}' (file upload) or '{field_label}_url' (URL).",
        )


def make_temp_dir() -> str:
    """Create a fresh temporary directory and return its path."""
    return tempfile.mkdtemp(prefix="subtitle_api_")


def cleanup(directory: str):
    """Remove a temporary directory and all its contents (inputs only)."""
    try:
        shutil.rmtree(directory, ignore_errors=True)
    except Exception:
        pass
