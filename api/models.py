"""
Pydantic models for the unified /process endpoint.

All sections (srt, image_overlays, video_overlay) are optional.
Omit any section you don't need.  The base video is always required.
"""
from typing import List, Optional
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Screen Resolution
# ---------------------------------------------------------------------------

class ScreenResolution(BaseModel):
    """Output video resolution. Omit to keep source resolution."""

    width: int = Field(1920, gt=0, description="Output width in pixels (e.g. 1920)")
    height: int = Field(1080, gt=0, description="Output height in pixels (e.g. 1080)")


# ---------------------------------------------------------------------------
# SRT / Subtitle section
# ---------------------------------------------------------------------------

class SRTSection(BaseModel):
    """
    Subtitle-burning section.

    Supply the SRT file via one of:
      - `url`      — publicly accessible URL to an .srt file
      - `srt_file` — upload field in the multipart request

    The `style` / `animation_style` fields are interchangeable — use whichever
    is clearer for your client.
    """

    url: Optional[str] = Field(None, description="Public URL to an .srt subtitle file")
    style: str = Field(
        "basic",
        description=(
            "Animation / render style: "
            "elevate | append | highlight | slide | "
            "oneword | basic | twoword | colorword | reveal"
        ),
    )
    font_name: str = Field("Noto Sans Telugu", description="Font family for subtitle text")
    font_size: int = Field(70, gt=0, description="Font size in points")


# ---------------------------------------------------------------------------
# Image overlay item (one entry in the image_overlays array)
# ---------------------------------------------------------------------------

POSITION_CHOICES = "top-left | top-right | bottom-left | bottom-right | center | fullscreen | custom"


class ImageOverlayItem(BaseModel):
    """
    A single image overlay entry.

    Supply the image via ONE of:
      - `url`   — publicly accessible URL (.png / .jpg)
      - `index` — zero-based index into the `image_files` upload list

    All other fields are optional and fall back to sensible defaults.
    """

    url: Optional[str] = Field(
        None,
        description="Public URL to the overlay image (.png / .jpg)",
    )
    index: Optional[int] = Field(
        None,
        ge=0,
        description=(
            "Zero-based index into the `image_files` upload list. "
            "Use this when you uploaded the image file instead of providing a URL."
        ),
    )
    position: str = Field(
        "top-right",
        description=f"Named position preset: {POSITION_CHOICES}",
    )
    x: int = Field(10, description="X offset in pixels (only used when position='custom')")
    y: int = Field(10, description="Y offset in pixels (only used when position='custom')")
    width: int = Field(200, gt=0, description="Scaled width of the image in pixels")
    start_time: float = Field(0.0, ge=0, description="Show image from this second")
    end_time: Optional[float] = Field(
        None, description="Hide image after this second (omit = until end of video)"
    )


# ---------------------------------------------------------------------------
# Video overlay section
# ---------------------------------------------------------------------------

class VideoOverlaySection(BaseModel):
    """
    Video-on-video overlay section.

    Supply the overlay clip via one of:
      - `url`          — publicly accessible URL to an .mp4 file
      - `overlay_file` — upload field in the multipart request
    """

    url: Optional[str] = Field(None, description="Public URL to the overlay video (.mp4)")
    position: str = Field(
        "top-right",
        description=f"Named position preset: {POSITION_CHOICES}",
    )
    x: int = Field(10, description="X offset in pixels (only used when position='custom')")
    y: int = Field(10, description="Y offset in pixels (only used when position='custom')")
    overlay_width: int = Field(400, gt=0, description="Scaled width of the overlay video in pixels")
    start_time: float = Field(0.0, ge=0, description="Show overlay from this second")
    end_time: Optional[float] = Field(
        None, description="Hide overlay after this second (omit = until end of video)"
    )


# ---------------------------------------------------------------------------
# Audio section (kept for the dedicated /audio router; not used by /process)
# ---------------------------------------------------------------------------

class AudioSection(BaseModel):
    """
    Audio replace / mix section (used by the dedicated /audio endpoint).
    """

    url: Optional[str] = Field(None, description="Public URL to the audio file (.mp3/.wav/.aac)")
    mode: str = Field(
        "replace",
        description="'replace' = swap original audio | 'mix' = blend both tracks",
    )
    audio_volume: float = Field(1.0, ge=0.0, le=2.0, description="Volume of the added audio (0.0–2.0)")
    video_volume: float = Field(
        1.0, ge=0.0, le=2.0,
        description="Volume of the original video audio when mode='mix' (0.0–2.0)",
    )


# ---------------------------------------------------------------------------
# Top-level request options (sent as a JSON string in the `data` form field)
# ---------------------------------------------------------------------------

class ProcessRequest(BaseModel):
    """
    Structured options for POST /process.

    Send this as a JSON string in the `data` multipart form field.
    Upload files separately via `video`, `srt_file`, `image_files`, and
    `overlay_file` form fields.

    All sections are optional — include only what you need.
    The base video is always required (either uploaded or via `video_url`).

    Minimal example (video only, no options):
        data={}

    Full example:
    {
        "screen_resolution": { "width": 1280, "height": 720 },

        "srt": {
            "url": "https://example.com/subtitles.srt",
            "style": "elevate",
            "font_name": "Noto Sans Telugu",
            "font_size": 70
        },

        "image_overlays": [
            {
                "url": "https://example.com/logo.png",
                "position": "top-right",
                "width": 200,
                "start_time": 0,
                "end_time": 10
            },
            {
                "index": 0,
                "position": "bottom-left",
                "width": 100,
                "start_time": 5
            }
        ],

        "video_overlay": {
            "url": "https://example.com/overlay.mp4",
            "position": "bottom-right",
            "overlay_width": 300
        }
    }
    """

    screen_resolution: Optional[ScreenResolution] = Field(
        None,
        description="Output resolution. Omit to keep source resolution.",
    )
    srt: Optional[SRTSection] = Field(
        None,
        description="Subtitle burning options. Omit to skip subtitle burning.",
    )
    image_overlays: Optional[List[ImageOverlayItem]] = Field(
        None,
        description=(
            "List of image overlays to apply in order. "
            "Each entry specifies the image (by URL or upload index) and its position. "
            "Omit or pass [] to skip all image overlays."
        ),
    )
    video_overlay: Optional[VideoOverlaySection] = Field(
        None,
        description="Video-on-video overlay options. Omit to skip video overlay.",
    )
