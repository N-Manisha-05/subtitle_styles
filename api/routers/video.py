import os
from typing import Optional
from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from fastapi.responses import FileResponse
from starlette.background import BackgroundTask

from api.helpers.temp import make_temp_dir, resolve_file, cleanup, make_output_path
from api.helpers.ffmpeg import overlay_video

router = APIRouter(prefix="/video", tags=["Video"])

# Named position presets — same as image overlay
POSITION_PRESETS = {
    "top-left":     ("10",       "10"),
    "top-right":    ("W-w-10",   "10"),
    "bottom-left":  ("10",       "H-h-10"),
    "bottom-right": ("W-w-10",   "H-h-10"),
    "center":       ("(W-w)/2",  "(H-h)/2"),
    "fullscreen":   None,  
}
DEFAULT_POSITION = "top-right"


@router.post(
    "/overlay",
    summary="Overlay one video on top of another",
    response_description="Processed MP4 with overlay video composited in",
)
async def video_overlay(
    # Base video — file OR url
    video:     Optional[UploadFile] = File(None, description="Base MP4 video (file upload)"),
    video_url: Optional[str]        = Form(None, description="Base MP4 video (URL)"),
    # Overlay video — file OR url
    overlay:     Optional[UploadFile] = File(None, description="Overlay MP4 video (file upload)"),
    overlay_url: Optional[str]        = Form(None, description="Overlay MP4 video (URL)"),
    # Layout
    position: str = Form(
        DEFAULT_POSITION,
        description=(
            "Named preset: top-left | top-right (default) | "
            "bottom-left | bottom-right | center | custom"
        ),
    ),
    x: int = Form(10,  description="X offset in pixels (only when position='custom')"),
    y: int = Form(10,  description="Y offset in pixels (only when position='custom')"),
    width: int = Form(400, description="Scaled width of the overlay video in pixels"),
    # Timing
    start_time: float = Form(0.0,  description="Show overlay from this second"),
    end_time: float   = Form(None, description="Hide overlay after this second (omit = until end)"),
):
    # Resolve position preset
    use_fullscreen = position.lower() == "fullscreen"

    if use_fullscreen:
        overlay_x, overlay_y = "0", "0"
    elif position == "custom":
        overlay_x, overlay_y = str(x), str(y)
    else:
        preset = POSITION_PRESETS.get(position.lower())
        if preset is None:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Unknown position '{position}'. "
                    f"Valid values: {', '.join(POSITION_PRESETS)} or 'custom'."
                ),
            )
        overlay_x, overlay_y = preset

    tmp = make_temp_dir()
    try:
        base_path    = await resolve_file(video,   video_url,   tmp, "base.mp4",    "video")
        overlay_path = await resolve_file(overlay, overlay_url, tmp, "overlay.mp4", "overlay")
        out_path     = make_output_path(f"video_{position}")

        overlay_video(
            base_path=base_path,
            overlay_path=overlay_path,
            output_path=out_path,
            x=overlay_x, y=overlay_y, width=width,
            start_time=start_time,
            end_time=end_time,
            fullscreen=use_fullscreen,
        )
    except HTTPException:
        cleanup(tmp)
        raise
    except RuntimeError as e:
        cleanup(tmp)
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        cleanup(tmp)
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")

    return FileResponse(
        out_path,
        media_type="video/mp4",
        filename="video_overlay.mp4",
        background=BackgroundTask(cleanup, tmp),
    )
