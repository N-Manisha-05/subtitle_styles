"""
FFmpeg helper functions — all async so they don't block the event loop.

Every function that wraps an ffmpeg/ffprobe call is `async def` and must
be called with `await` from the router.
"""

import asyncio
import json
import logging
import os

logger = logging.getLogger(__name__)

# Maximum seconds to wait for any single FFmpeg/ffprobe command.
FFMPEG_TIMEOUT = int(os.getenv("FFMPEG_TIMEOUT", "600"))


async def run_ffmpeg(cmd: list[str], timeout: int = FFMPEG_TIMEOUT) -> None:
    """Run an FFmpeg command asynchronously.

    - Does NOT block the event loop (uses asyncio subprocess).
    - Raises RuntimeError with stderr on non-zero exit.
    - Raises asyncio.TimeoutError (caught by router as 500) if command hangs.
    """
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        proc.kill()
        await proc.communicate()
        raise RuntimeError(f"FFmpeg timed out after {timeout}s")

    stderr_text = stderr.decode(errors="replace")
    if proc.returncode != 0:
        logger.error("[FFMPEG] Failed: %s", stderr_text[-300:])
        raise RuntimeError(f"FFmpeg failed (exit {proc.returncode}):\n{stderr_text}")

    logger.debug("[FFMPEG] OK: %s", cmd[0])


async def get_video_dimensions(video_path: str) -> tuple[int, int]:
    """Return (width, height) of a video file using ffprobe.

    Used to detect actual video dimensions when the caller has not explicitly
    specified a target resolution — ensures the ASS subtitle canvas matches
    the real video size.
    """
    cmd = [
        "ffprobe", "-v", "quiet",
        "-print_format", "json",
        "-show_streams",
        video_path,
    ]
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=30)
    except asyncio.TimeoutError:
        proc.kill()
        await proc.communicate()
        raise RuntimeError("ffprobe timed out while reading video dimensions.")

    try:
        data = json.loads(stdout.decode())
    except json.JSONDecodeError:
        raise RuntimeError("ffprobe returned invalid JSON — cannot determine video dimensions.")

    for stream in data.get("streams", []):
        if stream.get("codec_type") == "video":
            return int(stream["width"]), int(stream["height"])

    raise RuntimeError(f"ffprobe could not find a video stream in: {video_path}")


def _escape_ass_path(path: str) -> str:
    """Escape an ASS file path for use inside an FFmpeg filter string.

    FFmpeg's `ass=` filter uses a colon as option separator, so colons in
    the path (common on Windows or after drive letters) must be escaped.
    Backslashes must also be normalised to forward slashes first.
    """
    return os.path.abspath(path).replace("\\", "/").replace(":", "\\:")


async def rescale_video(input_path: str, output_path: str, width: int, height: int) -> None:
    """Rescale a video to exact width×height pixels.

    - Uses force_original_aspect_ratio=decrease and padding to handle aspect mismatches
      while ensuring final dimensions are exactly width×height.
    - setsar=1 resets the sample aspect ratio to 1:1.
    """
    # Ensure dimensions are even (libx264 requirement)
    w = (width // 2) * 2
    h = (height // 2) * 2

    await run_ffmpeg([
        "ffmpeg", "-y",
        "-i", input_path,
        "-vf", f"scale={w}:{h},setsar=1",
        "-c:a", "copy",
        output_path,
    ])


async def burn_subtitles(video_path: str, ass_path: str, output_path: str) -> None:
    """Hard-burn an ASS subtitle file into a video."""
    escaped = _escape_ass_path(ass_path)
    # The 'ass' filter path must be wrapped in single quotes, 
    # and the whole filter string itself is often wrapped in double quotes.
    await run_ffmpeg([
        "ffmpeg", "-y",
        "-i", video_path,
        "-vf", f"ass='{escaped}'",
        "-c:a", "copy",
        output_path,
    ])


async def overlay_image(
    video_path: str,
    image_path: str,
    output_path: str,
    x: str = "10",
    y: str = "10",
    width: int = 200,
    start_time: float = 0.0,
    end_time: float | None = None,
    fullscreen: bool = False,
    target_width: int | None = None,
    target_height: int | None = None,
) -> None:

    if end_time is not None:
        enable_expr = f"between(t,{start_time},{end_time})"
    else:
        enable_expr = f"gte(t,{start_time})"

    if fullscreen:
        # Ensure dimensions are even
        tw = (target_width // 2) * 2
        th = (target_height // 2) * 2
        filter_complex = (
            "[1:v]format=rgba[img];"
            f"[img]scale={tw}:{th}[img_s];"
            f"[0:v][img_s]overlay=0:0:enable='{enable_expr}':format=auto"
        )
    else:
        # Ensure overlay width is even
        overlay_width = (int(target_width * 0.15) // 2) * 2

        filter_complex = (
            "[1:v]format=rgba[img];"
            f"[img]scale={overlay_width}:-2[img_s];"
            f"[0:v][img_s]overlay={x}:{y}:enable='{enable_expr}':format=auto"
        )

    logger.info("[FFMPEG] Overlay image filter: %s", filter_complex)

    await run_ffmpeg([
        "ffmpeg", "-y",
        "-i", video_path,
        "-loop", "1", "-i", image_path,
        "-filter_complex", filter_complex,
        "-c:a", "copy",
        "-pix_fmt", "yuv420p",
        "-shortest",
        output_path,
    ])



async def overlay_video(
    base_path: str,
    overlay_path: str,
    output_path: str,
    x: str = "10",
    y: str = "10",
    width: int = 400,
    start_time: float = 0.0,
    end_time: float | None = None,
    fullscreen: bool = False,
) -> None:
    """Overlay one video on top of a base video. Audio comes from base only."""
    if end_time is not None:
        enable_expr = f"between(t,{start_time},{end_time})"
    else:
        enable_expr = f"gte(t,{start_time})"

    if fullscreen:
        filter_complex = (
            "[1:v][0:v]scale2ref=w=main_w:h=main_h[ovr][base];"
            f"[base][ovr]overlay=0:0:enable='{enable_expr}':format=auto"
        )
    else:
        filter_complex = (
            f"[1:v]scale='trunc({width}/2)*2':-2[ovr];"
            f"[0:v][ovr]overlay={x}:{y}:enable='{enable_expr}':format=auto"
        )

    await run_ffmpeg([
        "ffmpeg", "-y",
        "-i", base_path,
        "-i", overlay_path,
        "-filter_complex", filter_complex,
        "-map", "0:a?",
        output_path,
    ])


async def mix_audio(
    video_path: str,
    audio_path: str,
    output_path: str,
    mode: str = "replace",
    audio_volume: float = 1.0,
    video_volume: float = 1.0,
) -> None:
    """Replace or mix an audio track into a video.

    mode='replace' : discard original audio, use provided audio track
    mode='mix'     : blend both audio streams together
    """
    if mode == "replace":
        await run_ffmpeg([
            "ffmpeg", "-y",
            "-i", video_path,
            "-i", audio_path,
            "-map", "0:v",
            "-map", "1:a",
            "-c:v", "copy",
            "-shortest",
            output_path,
        ])
    else:  # mix
        filter_complex = (
            f"[0:a]volume={video_volume}[a0];"
            f"[1:a]volume={audio_volume}[a1];"
            f"[a0][a1]amix=inputs=2:duration=first[aout]"
        )
        await run_ffmpeg([
            "ffmpeg", "-y",
            "-i", video_path,
            "-i", audio_path,
            "-filter_complex", filter_complex,
            "-map", "0:v",
            "-map", "[aout]",
            "-c:v", "copy",
            output_path,
        ])
