import os
from typing import Optional
from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from fastapi.responses import FileResponse
from starlette.background import BackgroundTask

from api.helpers.temp import make_temp_dir, resolve_file, cleanup, make_output_path
from api.helpers.ffmpeg import mix_audio

router = APIRouter(prefix="/audio", tags=["Audio"])


@router.post(
    "/mix",
    summary="Replace or mix an audio track into a video",
    response_description="Processed MP4 video with new audio",
)
async def audio_mix(
    # Video — supply file OR url
    video:     Optional[UploadFile] = File(None, description="Input MP4 video (file upload)"),
    video_url: Optional[str]        = Form(None, description="Input MP4 video (URL)"),
    # Audio — supply file OR url
    audio:     Optional[UploadFile] = File(None, description="Audio file .mp3/.wav/.aac (file upload)"),
    audio_url: Optional[str]        = Form(None, description="Audio file .mp3/.wav/.aac (URL)"),
    # Options
    mode: str = Form(
        "replace",
        description="'replace' = swap original audio | 'mix' = blend both tracks",
    ),
    audio_volume: float = Form(1.0, description="Volume of added audio (0.0 – 2.0)"),
    video_volume: float = Form(1.0, description="Volume of original video audio when mixing (0.0 – 2.0)"),
):
    if mode not in ("replace", "mix"):
        raise HTTPException(status_code=400, detail="mode must be 'replace' or 'mix'")

    tmp = make_temp_dir()
    try:
        video_path = await resolve_file(video, video_url, tmp, "input.mp4",    "video")
        audio_path = await resolve_file(audio, audio_url, tmp, "input_audio",  "audio")
        out_path   = make_output_path(f"audio_{mode}")

        mix_audio(
            video_path=video_path,
            audio_path=audio_path,
            output_path=out_path,
            mode=mode,
            audio_volume=audio_volume,
            video_volume=video_volume,
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
        filename=f"audio_{mode}.mp4",
        background=BackgroundTask(cleanup, tmp),
    )
