from fastapi import FastAPI
from api.routers import subtitle, image, audio, video

app = FastAPI(
    title="Subtitle & Media Toolkit API",
    description=(
        "REST API to burn animated subtitles, overlay images/videos, "
        "and mix/replace audio into videos using FFmpeg."
    ),
    version="1.0.0",
)

app.include_router(subtitle.router)
app.include_router(image.router)
app.include_router(audio.router)
app.include_router(video.router)


@app.get("/", tags=["Health"])
def health():
    return {"status": "ok", "message": "Subtitle Toolkit API is running"}
