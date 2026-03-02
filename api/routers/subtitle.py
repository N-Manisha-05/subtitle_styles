import os
from typing import Optional
from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from fastapi.responses import FileResponse
from starlette.background import BackgroundTask

from api.helpers.temp import make_temp_dir, resolve_file, cleanup, make_output_path
from api.helpers.ffmpeg import burn_subtitles
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

router = APIRouter(prefix="/subtitle", tags=["Subtitle"])


@router.get("/fonts", summary="List available font families")
def list_fonts():
    """Returns the list of font families available for subtitle rendering."""
    return {"fonts": VALID_FONTS}


@router.post(
    "/burn",
    summary="Burn animated subtitles into a video",
    response_description="Processed MP4 video with subtitles burned in",
)
async def burn_subtitle(
    # Video — supply file OR url
    video:     Optional[UploadFile] = File(None, description="Input MP4 video (file upload)"),
    video_url: Optional[str]        = Form(None, description="Input MP4 video (URL)"),
    # SRT — supply file OR url
    srt:     Optional[UploadFile] = File(None, description="SRT subtitle file (file upload)"),
    srt_url: Optional[str]        = Form(None, description="SRT subtitle file (URL)"),
    # Style options
    font_name: str = Form(DEFAULT_FONT, description=FONT_DESCRIPTION),
    font_size: int = Form(70, description="Font size in points"),
    style: str = Form("basic", description=(
        "Animation style: elevate | append | highlight | slide | "
        "oneword | basic | twoword | colorword | reveal"
    )),
):
    if font_name not in VALID_FONTS:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown font '{font_name}'. Valid options: {', '.join(VALID_FONTS)}"
        )
    style_class = STYLE_MAP.get(style.lower())
    if style_class is None:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown style '{style}'. Valid values: {', '.join(STYLE_MAP)}"
        )

    tmp = make_temp_dir()
    try:
        video_path = await resolve_file(video, video_url, tmp, "input.mp4",  "video")
        srt_path   = await resolve_file(srt,   srt_url,   tmp, "subtitles.srt", "srt")
        ass_path   = os.path.join(tmp, "subtitles.ass")
        out_name   = f"subtitle_{style}_{font_name.replace(' ', '_')}"
        out_path   = make_output_path(out_name)

        selected_style = style_class(font_name=font_name, font_size=font_size)
        selected_style.generate_ass(srt_path, ass_path)
        burn_subtitles(video_path, ass_path, out_path)
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
        filename=f"subtitle_{style}_{font_name.replace(' ', '_')}.mp4",
        background=BackgroundTask(cleanup, tmp),
    )
