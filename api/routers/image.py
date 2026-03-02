import os
from typing import Optional
from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from fastapi.responses import FileResponse
from starlette.background import BackgroundTask

from api.helpers.temp import make_temp_dir, resolve_file, cleanup, make_output_path
from api.helpers.ffmpeg import overlay_image

router = APIRouter(prefix="/image", tags=["Image"])

# Named position presets → FFmpeg overlay x:y expressions
# W/H = video width/height,  w/h = scaled image width/height
POSITION_PRESETS = {
    "top-left":     ("10",          "10"),
    "top-right":    ("W-w-10",      "10"),
    "bottom-left":  ("10",          "H-h-10"),
    "bottom-right": ("W-w-10",      "H-h-10"),
    "center":       ("(W-w)/2",     "(H-h)/2"),
    "fullscreen":   None,
}
DEFAULT_POSITION = "top-right"


@router.post(
    "/overlay",
    summary="Overlay an image onto a video",
    response_description="Processed MP4 video with image overlaid",
)
async def image_overlay(
    # Video — supply file OR url
    video:     Optional[UploadFile] = File(None, description="Input MP4 video (file upload)"),
    video_url: Optional[str]        = Form(None, description="Input MP4 video (URL)"),
    # Image — supply file OR url
    image:     Optional[UploadFile] = File(None, description="Overlay image .png/.jpg (file upload)"),
    image_url: Optional[str]        = Form(None, description="Overlay image .png/.jpg (URL)"),
    # Position / timing
    position: str = Form(
        DEFAULT_POSITION,
        description=(
            "Named preset: top-left | top-right (default) | "
            "bottom-left | bottom-right | center | fullscreen | custom"
        ),
    ),
    x: int = Form(10,  description="X offset in pixels (only when position='custom')"),
    y: int = Form(10,  description="Y offset in pixels (only when position='custom')"),
    width: int    = Form(200,  description="Scaled width of the image in pixels"),
    start_time: float = Form(0.0,  description="Start showing image at this second"),
    end_time: float   = Form(None, description="Stop showing image at this second (omit = until end)"),
):
    # Resolve position
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
                )
            )
        overlay_x, overlay_y = preset

    tmp = make_temp_dir()
    try:
        video_path = await resolve_file(video, video_url, tmp, "input.mp4",   "video")
        image_path = await resolve_file(image, image_url, tmp, "overlay_img", "image")
        out_path   = make_output_path(f"image_{position}")

        overlay_image(
            video_path=video_path,
            image_path=image_path,
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
        filename="image_overlay.mp4",
        background=BackgroundTask(cleanup, tmp),
    )
