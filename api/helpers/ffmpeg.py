import subprocess
import os


def run_ffmpeg(cmd: list[str]):
    """Run an ffmpeg command, raising RuntimeError on failure."""
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"FFmpeg failed:\n{result.stderr}")


def burn_subtitles(video_path: str, ass_path: str, output_path: str):
    """Hard-burn an ASS subtitle file into a video."""
    abs_ass = os.path.abspath(ass_path)
    run_ffmpeg([
        "ffmpeg", "-y",
        "-i", video_path,
        "-vf", f"ass='{abs_ass}'",
        "-c:a", "copy",
        output_path
    ])


def overlay_image(
    video_path: str,
    image_path: str,
    output_path: str,
    x: str = "10",
    y: str = "10",
    width: int = 200,
    start_time: float = 0.0,
    end_time: float = None,
    fullscreen: bool = False,
):
    if end_time is not None:
        enable_expr = f"between(t,{start_time},{end_time})"
    else:
        enable_expr = f"gte(t,{start_time})"

    if fullscreen:
        filter_complex = (
            "[1:v][0:v]scale2ref=w=main_w:h=main_h[img][base];"
            f"[base][img]overlay=0:0:enable='{enable_expr}'"
        )
    else:
        filter_complex = (
        f"[1:v]scale={width}:-1[img];"
        f"[0:v][img]overlay={x}:{y}:enable='{enable_expr}'"
    )

    run_ffmpeg([
        "ffmpeg", "-y",
        "-i", video_path,
        "-i", image_path,
        "-filter_complex", filter_complex,
        "-c:a", "copy",
        output_path
    ])

def overlay_video(
    base_path: str,
    overlay_path: str,
    output_path: str,
    x: str = "10",
    y: str = "10",
    width: int = 400,
    start_time: float = 0.0,
    end_time: float = None,
    fullscreen: bool = False,
):
    """
    Overlay one video on top of a base video.
    Supports fullscreen mode and timed appearance.
    Audio comes from base video only.
    """

    if end_time is not None:
        enable_expr = f"between(t,{start_time},{end_time})"
    else:
        enable_expr = f"gte(t,{start_time})"

    if fullscreen:
        # Match overlay video resolution to base video
        filter_complex = (
            "[1:v][0:v]scale2ref=w=main_w:h=main_h[ovr][base];"
            f"[base][ovr]overlay=0:0:enable='{enable_expr}'"
        )
    else:
        filter_complex = (
            f"[1:v]scale={width}:-1[ovr];"
            f"[0:v][ovr]overlay={x}:{y}:enable='{enable_expr}'"
        )

    run_ffmpeg([
        "ffmpeg", "-y",
        "-i", base_path,
        "-i", overlay_path,
        "-filter_complex", filter_complex,
        "-map", "0:a?",
        output_path
    ])

def mix_audio(
    video_path: str,
    audio_path: str,
    output_path: str,
    mode: str = "replace",
    audio_volume: float = 1.0,
    video_volume: float = 1.0,
):
    """
    Replace or mix an audio track into a video.

    mode='replace' : discard original audio, use provided audio track
    mode='mix'     : blend both audio streams together
    """
    if mode == "replace":
        run_ffmpeg([
            "ffmpeg", "-y",
            "-i", video_path,
            "-i", audio_path,
            "-map", "0:v",
            "-map", "1:a",
            "-c:v", "copy",
            "-shortest",
            output_path
        ])
    else:  # mix
        filter_complex = (
            f"[0:a]volume={video_volume}[a0];"
            f"[1:a]volume={audio_volume}[a1];"
            f"[a0][a1]amix=inputs=2:duration=first[aout]"
        )
        run_ffmpeg([
            "ffmpeg", "-y",
            "-i", video_path,
            "-i", audio_path,
            "-filter_complex", filter_complex,
            "-map", "0:v",
            "-map", "[aout]",
            "-c:v", "copy",
            output_path
        ])
