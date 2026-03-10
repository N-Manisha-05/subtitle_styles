"""
Unified /process endpoint — one request, any combination of sections.

Request format — multipart/form-data
─────────────────────────────────────
  video           UploadFile  (required if video_url omitted)
  video_url       str         (required if video omitted)
  srt_file        UploadFile  (required if srt.url omitted and srt section present)
  image_file_0/1/2 UploadFile (matched to image_overlays[*].index)
  overlay_file    UploadFile  (required if video_overlay.url omitted and section present)
  audio_file      UploadFile  (required if audio.url omitted and audio section present)
  data            str         JSON string with all structured options (see ProcessRequest)

All sections inside `data` are optional.  Omit any section you don't need.
"""

import json
import logging
import os
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger(__name__)

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from starlette.background import BackgroundTask

from api.config import DEFAULT_FONT, VALID_FONTS
from api.helpers.ffmpeg import (
    burn_subtitles,
    get_video_dimensions,
    mix_audio,
    overlay_image,
    overlay_video,
    rescale_video,
)
from api.helpers.temp import (
    cleanup,
    make_output_path,
    make_temp_dir,
    resolve_file,
)
from api.helpers.url_validator import validate_url
from api.models import ProcessRequest
from styles.basic_style import BasicStyle
from styles.color_word_style import ColorWordStyle
from styles.elevate_style import ElevateStyle
from styles.highlight_style import HighlightStyle
from styles.one_word_style import OneWordStyle
from styles.reveal_style import RevealStyle
from styles.slide_style import SlideStyle
from styles.two_word_style import TwoWordStyle
from styles.word_append_style import WordAppendStyle

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
    "top-left":     ("10",      "10"),
    "top-right":    ("W-w-10",  "10"),
    "bottom-left":  ("10",      "H-h-10"),
    "bottom-right": ("W-w-10",  "H-h-10"),
    "center":       ("(W-w)/2", "(H-h)/2"),
}
POSITION_HELP = "top-left | top-right | bottom-left | bottom-right | center | fullscreen | custom"

# Allowed file extensions per upload type
ALLOWED_VIDEO = {".mp4", ".mov", ".avi", ".mkv", ".webm"}
ALLOWED_IMAGE = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
ALLOWED_AUDIO = {".mp3", ".wav", ".aac", ".ogg", ".m4a", ".flac"}
ALLOWED_SRT   = {".srt"}

# Max upload size per file
MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "500"))

router = APIRouter(prefix="/process", tags=["Process"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _resolve_pos(position: str, x: int, y: int):
    """Return (x_expr, y_expr, is_fullscreen)."""
    pos = position.lower()
    if pos == "fullscreen":
        return "0", "0", True
    if pos == "custom":
        return str(x), str(y), False
    preset = POSITION_PRESETS.get(pos)
    if preset is None:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown position '{position}'. Valid: {POSITION_HELP}",
        )
    return preset[0], preset[1], False


def _has_file(f: Optional[UploadFile]) -> bool:
    return f is not None and bool(f.filename)


def _check_extension(upload: UploadFile, allowed: set[str], label: str) -> None:
    """Raise 400 if the uploaded file's extension is not in `allowed`."""
    ext = Path(upload.filename).suffix.lower()
    if ext not in allowed:
        raise HTTPException(
            status_code=400,
            detail=(
                f"{label}: file type '{ext}' is not allowed. "
                f"Accepted: {', '.join(sorted(allowed))}"
            ),
        )


def _check_size(upload: UploadFile, label: str, max_mb: int = MAX_UPLOAD_MB) -> None:
    """Raise 413 if the upload content-length header exceeds max_mb.

    Note: content-length is not always present; when absent, no check is done
    (the actual data still flows through, this is best-effort early rejection).
    """
    size = getattr(upload, "size", None)
    if size is not None and size > max_mb * 1024 * 1024:
        raise HTTPException(
            status_code=413,
            detail=f"{label}: file size exceeds the {max_mb} MB limit.",
        )


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------

@router.post(
    "",
    summary="Process a video — combine any of: subtitles, image overlays, video overlay, audio",
    response_description="Processed MP4 output",
    description="""
Send a **multipart/form-data** request with these fields:

| Field | Type | Description |
|---|---|---|
| `video` | file | Base video file *(one of video / video_url required)* |
| `video_url` | string | Public URL of the base video |
| `srt_file` | file | SRT subtitle file *(required when srt section present and no srt.url)* |
| `image_file_0` | file | First overlay image *(matched by index 0 in image_overlays list)* |
| `image_file_1` | file | Second overlay image *(matched by index 1 in image_overlays list)* |
| `image_file_2` | file | Third overlay image *(matched by index 2 in image_overlays list)* |
| `overlay_file` | file | Overlay video file *(required when video_overlay section present and no url)* |
| `audio_file` | file | Audio track (.mp3/.wav/.aac) *(required when audio section present and no audio.url)* |
| `data` | JSON string | All structured options — see **ProcessRequest** model below |

""",
)
async def process_video(
    # ── Base video ────────────────────────────────────────────────────────
    video: Optional[UploadFile] = File(
        None,
        description="[BASE VIDEO] Upload the base .mp4 / .mov file",
    ),
    video_url: Optional[str] = Form(
        None,
        description="[BASE VIDEO] Public URL of the base video file",
    ),

    # ── SRT subtitle file ─────────────────────────────────────────────────
    srt_file: Optional[UploadFile] = File(
        None,
        description=(
            "[SRT] Upload the .srt subtitle file. "
            "Required when the `srt` section is present in `data` and no `srt.url` is given."
        ),
    ),

    # ── Image overlay file slots (index 0–2 ─ reference via image_overlays[].index) ──
    image_file_0: Optional[UploadFile] = File(
        None,
        description='[IMAGE 0] First overlay image (.png/.jpg). Reference in data with "index": 0',
    ),
    image_file_1: Optional[UploadFile] = File(
        None,
        description='[IMAGE 1] Second overlay image (.png/.jpg). Reference in data with "index": 1',
    ),
    image_file_2: Optional[UploadFile] = File(
        None,
        description='[IMAGE 2] Third overlay image (.png/.jpg). Reference in data with "index": 2',
    ),

    # ── Video overlay file ────────────────────────────────────────────────
    overlay_file: Optional[UploadFile] = File(
        None,
        description=(
            "[VIDEO OVERLAY] Upload the overlay video (.mp4). "
            "Required when the `video_overlay` section is present in `data` and no `video_overlay.url` is given."
        ),
    ),

    # ── Audio file ────────────────────────────────────────────────────────
    audio_file: Optional[UploadFile] = File(
        None,
        description="[AUDIO] Upload the audio track (.mp3 / .wav / .aac).",
    ),

    # ── Structured JSON options ───────────────────────────────────────────
    data: str = Form(
        "{}",
        description=(
            "JSON string containing all structured options. "
            "All keys are optional. "
            "Keys: screen_resolution, srt, image_overlays, video_overlay, audio. "
            "Pass `{}` or omit to apply no processing beyond returning the base video."
        ),
    ),
):
    # ── File type validation ──────────────────────────────────────────────
    if _has_file(video):        _check_extension(video,        ALLOWED_VIDEO, "video")
    if _has_file(srt_file):     _check_extension(srt_file,     ALLOWED_SRT,   "srt_file")
    if _has_file(image_file_0): _check_extension(image_file_0, ALLOWED_IMAGE, "image_file_0")
    if _has_file(image_file_1): _check_extension(image_file_1, ALLOWED_IMAGE, "image_file_1")
    if _has_file(image_file_2): _check_extension(image_file_2, ALLOWED_IMAGE, "image_file_2")
    if _has_file(overlay_file): _check_extension(overlay_file, ALLOWED_VIDEO, "overlay_file")
    if _has_file(audio_file):   _check_extension(audio_file,   ALLOWED_AUDIO, "audio_file")

    # ── File size validation ──────────────────────────────────────────────
    if _has_file(video):        _check_size(video,        "video")
    if _has_file(overlay_file): _check_size(overlay_file, "overlay_file")
    if _has_file(audio_file):   _check_size(audio_file,   "audio_file")

    # ── Collect image upload slots into a list (None slots are skipped) ───
    image_files: List[UploadFile] = [
        f for f in [image_file_0, image_file_1, image_file_2]
        if _has_file(f)
    ]

    # ── Parse options JSON ────────────────────────────────────────────────
    try:
        opts = ProcessRequest.model_validate(json.loads(data))
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON in `data` field: {e}")
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Invalid options in `data`: {e}")

    # ── SSRF validation on all user-supplied URLs ─────────────────────────
    if video_url:
        validate_url(video_url, "video_url")
    if opts.srt and opts.srt.url:
        validate_url(opts.srt.url, "srt.url")
    if opts.image_overlays:
        for i, item in enumerate(opts.image_overlays):
            if item.url:
                validate_url(item.url, f"image_overlays[{i}].url")
    if opts.video_overlay and opts.video_overlay.url:
        validate_url(opts.video_overlay.url, "video_overlay.url")
    if opts.audio and opts.audio.url:
        validate_url(opts.audio.url, "audio.url")

    # ── Require base video ────────────────────────────────────────────────
    if not _has_file(video) and not video_url:
        raise HTTPException(
            status_code=400,
            detail="Base video is required. Provide 'video' (file upload) or 'video_url' (URL).",
        )

    tmp = make_temp_dir()
    logger.info("[PROCESS] Request received | tmp=%s", tmp)
    logger.info("[PROCESS] Parsed options: %s", opts.model_dump(exclude_none=True))
    try:
        logger.info("[PROCESS] Resolving base video...")
        current = await resolve_file(video, video_url, tmp, "base.mp4", "video")
        logger.info("[PROCESS] Base video saved -> %s", current)

        # ── SCREEN RESOLUTION ─────────────────────────────────────────────
        if opts.screen_resolution is not None:
            logger.info("[PROCESS] Resizing to %dx%d...",
                        opts.screen_resolution.width, opts.screen_resolution.height)
            scaled = os.path.join(tmp, "scaled.mp4")
            await rescale_video(current, scaled,
                                opts.screen_resolution.width,
                                opts.screen_resolution.height)
            current = scaled
            logger.info("[PROCESS] Resize done -> %s", current)
        else:
            logger.info("[PROCESS] No resize requested, keeping source resolution.")

        # ── Determine actual output canvas size via ffprobe ───────────────
        # If screen_resolution was given, use it; otherwise probe the file.
        if opts.screen_resolution is not None:
            out_w = opts.screen_resolution.width
            out_h = opts.screen_resolution.height
        else:
            logger.info("[PROCESS] Probing video dimensions with ffprobe...")
            out_w, out_h = await get_video_dimensions(current)

        logger.info("[PROCESS] Output canvas size: %dx%d", out_w, out_h)

        # ── SRT — resolve & validate early, burn LAST ─────────────────────
        srt_path = None
        ass_path = None
        if opts.srt is not None:
            srt_section = opts.srt
            logger.info("[PROCESS] SRT section detected | style=%s font=%s size=%s",
                        srt_section.style, srt_section.font_name, srt_section.font_size)

            srt_has_upload = _has_file(srt_file)
            logger.info("[PROCESS] SRT source: %s",
                        "uploaded file" if srt_has_upload else f"URL={srt_section.url}")
            srt_path = await resolve_file(
                srt_file if srt_has_upload else None,
                srt_section.url,
                tmp,
                "subtitles.srt",
                "srt_file / srt.url",
            )
            logger.info("[PROCESS] SRT file saved -> %s", srt_path)

            if srt_section.font_name not in VALID_FONTS:
                raise HTTPException(
                    status_code=400,
                    detail=f"Unknown font '{srt_section.font_name}'. Valid: {', '.join(VALID_FONTS)}",
                )

            style_cls = STYLE_MAP.get(srt_section.style.lower())
            if style_cls is None:
                raise HTTPException(
                    status_code=400,
                    detail=f"Unknown style '{srt_section.style}'. Valid: {', '.join(STYLE_MAP)}",
                )

            ass_path = os.path.join(tmp, "subtitles.ass")
            logger.info("[PROCESS] Generating ASS file with style class: %s (canvas %dx%d)",
                        style_cls.__name__, out_w, out_h)
            style_cls(
                font_name=srt_section.font_name,
                font_size=srt_section.font_size,
            ).generate_ass(srt_path, ass_path, width=out_w, height=out_h)
            logger.info("[PROCESS] ASS file generated -> %s", ass_path)
        else:
            logger.info("[PROCESS] No SRT section in request, skipping subtitles.")

        # ── IMAGE OVERLAYS (applied before subtitles so text is on top) ───
        if opts.image_overlays:
            logger.info("[PROCESS] Applying %d image overlay(s)...", len(opts.image_overlays))
            for idx, item in enumerate(opts.image_overlays):
                logger.info("[PROCESS] Image overlay [%d] | source=%s position=%s width=%s",
                            idx,
                            f"index:{item.index}" if item.index is not None else f"url:{item.url}",
                            item.position, item.width)
                if item.index is not None:
                    if item.index >= len(image_files):
                        raise HTTPException(
                            status_code=400,
                            detail=(
                                f"image_overlays[{idx}].index={item.index} is out of range. "
                                f"Only {len(image_files)} file(s) were uploaded."
                            ),
                        )
                    uploaded = image_files[item.index]
                    img_path = await resolve_file(
                        uploaded, None, tmp, f"overlay_img_{idx}", "image_files"
                    )
                elif item.url:
                    img_path = await resolve_file(
                        None, item.url, tmp, f"overlay_img_{idx}", "image_overlays.url"
                    )
                else:
                    raise HTTPException(
                        status_code=400,
                        detail=(
                            f"image_overlays[{idx}] must provide either 'url' or 'index'. "
                            "Neither was given."
                        ),
                    )
                logger.info("[PROCESS] Image overlay [%d] file saved -> %s", idx, img_path)

                ox, oy, fullscreen = _resolve_pos(item.position, item.x, item.y)
                img_out = os.path.join(tmp, f"after_image_{idx}.mp4")
                await overlay_image(
                    video_path=current,
                    image_path=img_path,
                    output_path=img_out,
                    x=ox, y=oy, width=item.width,
                    start_time=item.start_time,
                    end_time=item.end_time,
                    fullscreen=fullscreen,
                )
                current = img_out
                logger.info("[PROCESS] Image overlay [%d] applied -> %s", idx, current)
        else:
            logger.info("[PROCESS] No image overlays requested.")

        # ── VIDEO OVERLAY (applied before subtitles so text is on top) ────
        if opts.video_overlay is not None:
            vo = opts.video_overlay
            logger.info("[PROCESS] Applying video overlay | source=%s position=%s",
                        vo.url or "uploaded file", vo.position)
            ovr_path = await resolve_file(
                overlay_file if _has_file(overlay_file) else None,
                vo.url,
                tmp,
                "overlay.mp4",
                "overlay_file / video_overlay.url",
            )
            logger.info("[PROCESS] Video overlay file saved -> %s", ovr_path)
            ox, oy, fullscreen = _resolve_pos(vo.position, vo.x, vo.y)

            ovr_out = os.path.join(tmp, "after_overlay.mp4")
            await overlay_video(
                base_path=current,
                overlay_path=ovr_path,
                output_path=ovr_out,
                x=ox, y=oy, width=vo.overlay_width,
                start_time=vo.start_time,
                end_time=vo.end_time,
                fullscreen=fullscreen,
            )
            current = ovr_out
            logger.info("[PROCESS] Video overlay applied -> %s", current)
        else:
            logger.info("[PROCESS] No video overlay requested.")

        # ── AUDIO ─────────────────────────────────────────────────────────
        if opts.audio is not None:
            au = opts.audio
            audio_has_upload = _has_file(audio_file)
            logger.info("[PROCESS] Audio section detected | mode=%s source=%s",
                        au.mode, "uploaded file" if audio_has_upload else f"URL={au.url}")
            aud_path = await resolve_file(
                audio_file if audio_has_upload else None,
                au.url,
                tmp,
                "audio_track",
                "audio_file / audio.url",
            )
            logger.info("[PROCESS] Audio file saved -> %s", aud_path)
            aud_out = os.path.join(tmp, "after_audio.mp4")
            await mix_audio(
                video_path=current,
                audio_path=aud_path,
                output_path=aud_out,
                mode=au.mode,
                audio_volume=au.audio_volume,
                video_volume=au.video_volume,
            )
            current = aud_out
            logger.info("[PROCESS] Audio applied -> %s", current)
        else:
            logger.info("[PROCESS] No audio section requested.")

        # ── SRT BURN — done LAST so subtitles appear on top of everything ──
        if ass_path is not None:
            srt_out = os.path.join(tmp, "after_srt.mp4")
            logger.info("[PROCESS] Burning subtitles into video (final layer)...")
            await burn_subtitles(current, ass_path, srt_out)
            current = srt_out
            logger.info("[PROCESS] Subtitles burned -> %s", current)

        # ── Final output ──────────────────────────────────────────────────
        out_path = make_output_path("process")
        os.rename(current, out_path)
        logger.info("[PROCESS] Done! Output saved -> %s", out_path)

    except HTTPException:
        cleanup(tmp)
        raise
    except RuntimeError as e:
        cleanup(tmp)
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        cleanup(tmp)
        raise HTTPException(status_code=500, detail=f"Unexpected error: {e}")

    return FileResponse(
        out_path,
        media_type="video/mp4",
        filename="processed_output.mp4",
        background=BackgroundTask(cleanup, tmp),
    )
