import os
from typing import Optional
from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from fastapi.responses import FileResponse
from starlette.background import BackgroundTask

from api.helpers.temp import make_temp_dir, resolve_file, cleanup, make_output_path
from api.helpers.ffmpeg import overlay_image, burn_subtitles
from api.config import VALID_FONTS, DEFAULT_FONT, FONT_DESCRIPTION

from styles.elevate_style import ElevateStyle
from styles.word_append_style import WordAppendStyle
from styles.highlight_style import HighlightStyle
from styles.slide_style import SlideStyle
from styles.one_word_style import OneWordStyle
from styles.basic_style import BasicStyle
from styles.two_word_style import TwoWordStyle
from styles.color_word_style import ColorWordStyle
from styles.reveal_style import RevealStyle

STYLE_MAP = {
    "elevate":   ElevateStyle,
    "append":    WordAppendStyle,
    "highlight": HighlightStyle,
    "slide":     SlideStyle,
    "oneword":   OneWordStyle,
    "basic":     BasicStyle,
    "twoword":   TwoWordStyle,
    "colorword": ColorWordStyle,
    "reveal":    RevealStyle,
}

POSITION_PRESETS = {
    "top-left":     ("10",       "10"),
    "top-right":    ("W-w-10",   "10"),
    "bottom-left":  ("10",       "H-h-10"),
    "bottom-right": ("W-w-10",   "H-h-10"),
    "center":       ("(W-w)/2",  "(H-h)/2"),
    "fullscreen":   None,
}

router = APIRouter(prefix="/composite", tags=["Composite"])


@router.post(
    "/burn",
    summary="Burn subtitles + overlay an image in a single pass",
    response_description="Processed MP4 with both subtitles and image applied",
)
async def composite_burn(
    # ── Video ────────────────────────────────────────────────
    video:     Optional[UploadFile] = File(None, description="Input MP4 video (file upload)"),
    video_url: Optional[str]        = Form(None, description="Input MP4 video (URL)"),
    # ── Subtitles ────────────────────────────────────────────
    srt:     Optional[UploadFile] = File(None, description="SRT subtitle file (file upload)"),
    srt_url: Optional[str]        = Form(None, description="SRT subtitle file (URL)"),
    font_name: str = Form(DEFAULT_FONT, description=FONT_DESCRIPTION),
    font_size: int = Form(70, description="Subtitle font size in points"),
    style: str = Form("basic", description=(
        "Animation style: elevate | append | highlight | slide | "
        "oneword | basic | twoword | colorword | reveal"
    )),
    # ── Image ────────────────────────────────────────────────
    image:     Optional[UploadFile] = File(None, description="Overlay image .png/.jpg (file upload)"),
    image_url: Optional[str]        = Form(None, description="Overlay image .png/.jpg (URL)"),
    position: str = Form(
        "top-right",
        description=(
            "Image position: top-left | top-right (default) | "
            "bottom-left | bottom-right | center | fullscreen | custom"
        ),
    ),
    x: int = Form(10,  description="X offset in pixels (only when position='custom')"),
    y: int = Form(10,  description="Y offset in pixels (only when position='custom')"),
    img_width: int = Form(200, description="Scaled width of the overlay image in pixels"),
    img_start: float = Form(0.0,  description="Show image from this second"),
    img_end: float   = Form(None, description="Hide image after this second (omit = until end)"),
):
    # Validate font
    if font_name not in VALID_FONTS:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown font '{font_name}'. Valid options: {', '.join(VALID_FONTS)}"
        )
    # Validate style
    style_class = STYLE_MAP.get(style.lower())
    if style_class is None:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown style '{style}'. Valid values: {', '.join(STYLE_MAP)}"
        )

    # Resolve image position
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
                detail=f"Unknown position '{position}'. Valid: {', '.join(POSITION_PRESETS)} or 'custom'."
            )
        overlay_x, overlay_y = preset

    tmp = make_temp_dir()
    try:
        video_path = await resolve_file(video, video_url, tmp, "input.mp4",      "video")
        srt_path   = await resolve_file(srt,   srt_url,   tmp, "subtitles.srt",  "srt")
        image_path = await resolve_file(image, image_url, tmp, "overlay_img",    "image")
        ass_path   = os.path.join(tmp, "subtitles.ass")
        out_name   = f"composite_{style}_{font_name.replace(' ', '_')}"
        out_path   = make_output_path(out_name)

        # Generate ASS from SRT
        selected_style = style_class(font_name=font_name, font_size=font_size)
        selected_style.generate_ass(srt_path, ass_path)

        # Step 1: overlay image onto video
        img_out = os.path.join(tmp, "after_image.mp4")
        overlay_image(
            video_path=video_path,
            image_path=image_path,
            output_path=img_out,
            x=overlay_x, y=overlay_y, width=img_width,
            start_time=img_start, end_time=img_end,
            fullscreen=use_fullscreen,
        )

        # Step 2: burn subtitles on top (last so text appears above image)
        burn_subtitles(
            video_path=img_out,
            ass_path=ass_path,
            output_path=out_path,
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
        filename=f"composite_{style}.mp4",
        background=BackgroundTask(cleanup, tmp),
    )
