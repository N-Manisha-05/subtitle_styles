# Subtitle Styles API — Implementation Notes

> **Purpose:** This document is a living memory document. Every significant code change is recorded here so future work can resume without re-reading the entire codebase.

---

## Project Structure

```
Subtitles_styles/
├── api/
│   ├── main.py              ← FastAPI app, lifespan, cleanup task
│   ├── models.py            ← Pydantic models (ProcessRequest, SRTSection, etc.)
│   ├── config.py            ← VALID_FONTS, DEFAULT_FONT constants
│   ├── helpers/
│   │   ├── ffmpeg.py        ← ALL FFmpeg/ffprobe calls (async)
│   │   ├── temp.py          ← Temp dir lifecycle (create, save, download, cleanup)
│   │   └── url_validator.py ← SSRF protection for user-supplied URLs
│   └── routers/
│       ├── process.py       ← Main unified endpoint POST /process
│       ├── subtitle.py      ← POST /subtitle (subtitles only)
│       ├── image.py         ← POST /image (image overlay only)
│       ├── audio.py         ← POST /audio (audio only)
│       ├── video.py         ← POST /video (video overlay only)
│       └── composite.py     ← POST /composite/burn (legacy, subtitles + image)
├── styles/
│   ├── base_style.py        ← Abstract base: generate_ass(srt, ass, width, height)
│   ├── elevate_style.py     ├─ Style implementations (all inherit BaseStyle)
│   ├── slide_style.py       │
│   ├── highlight_style.py   │
│   ├── one_word_style.py    │
│   ├── two_word_style.py    │
│   ├── word_append_style.py │
│   ├── color_word_style.py  │
│   ├── reveal_style.py      │
│   └── basic_style.py       └─
└── utils/
    ├── ass_formatter.py     ← get_ass_header(font, size, width, height)
    └── srt_parser.py        ← parse .srt → list of subtitle entries
```

---

## /process Pipeline Order

```
1. Resize           (rescale_video)
2. Detect dims      (ffprobe — only if no screen_resolution given)
3. Generate ASS     (style_cls.generate_ass with actual canvas dims)
4. Image overlays   (overlay_image × N, loop)
5. Video overlay    (overlay_video)
6. Audio            (mix_audio — replace or mix)
7. Burn subtitles   ← ALWAYS LAST so text appears on top
```

---

## Key Design Decisions

| Decision | Reason |
|---|---|
| Subtitles burned last | Ensures text is always on top of all image/video overlays |
| image_file_0/1/2 (named slots) | `List[UploadFile]` causes 422 in Swagger when field is empty |
| `await` for all FFmpeg calls | `asyncio.create_subprocess_exec` — doesn't block the event loop |
| ffprobe for actual dimensions | When no `screen_resolution` given, ASS canvas must match real video size |
| `openapi_extra` for image slots | Removed — caused \all other Swagger fields to disappear |

---

## Change Log

### Session 1 (API Redesign)
- Created unified `/process` endpoint replacing per-feature endpoints
- Added JSON `data` field in form-data to send structured options alongside files
- Removed `image_files` from declared params (→ 422 fix), used `request.form()` extraction

### Session 2 (Debugging & Fixes)
- Added `import logging` + `basicConfig` to `main.py` — logs now appear in uvicorn terminal
- Added `[PROCESS]` and `[FFMPEG]` logging throughout pipeline
- Fixed subtitle rendering order — subtitles now burned **last**
- Replaced `List[UploadFile] image_files` with named slots `image_file_0`, `image_file_1`, `image_file_2` to permanently fix Swagger 422 error
- Removed `burn_subtitles_with_image` from `ffmpeg.py` (redundant)
- Fixed `composite.py` to use `overlay_image` + `burn_subtitles` two-step

### Session 3 (Audio + Resolution)
- Added `AudioSection` model to `models.py`
- Added `audio_file` upload param and `mix_audio` step to `/process`
- Fixed hardcoded `PlayResX/Y: 1920/1080` in `ass_formatter.py` → now accepts `width`/`height` params
- Updated `base_style.generate_ass()` signature to accept `width`/`height`
- Updated `process.py` to pass actual output dimensions to `generate_ass()`

### Session 4 (Security & Reliability Fixes)
- **`api/helpers/ffmpeg.py`** — Full async rewrite:
  - `subprocess.run` → `asyncio.create_subprocess_exec` (non-blocking)
  - Added `timeout` param (default `FFMPEG_TIMEOUT` env var, 600s)
  - Added `get_video_dimensions()` via `ffprobe` (returns actual `width, height`)
  - Added `_escape_ass_path()` — escapes colons/backslashes in ASS filter path
- **`api/helpers/url_validator.py`** — New file, SSRF protection:
  - Blocks private IPs (RFC-1918), loopback, link-local, non-http/https schemes
  - Resolves hostnames via DNS and checks resulting IPs too
- **`api/main.py`**:
  - Added `asynccontextmanager lifespan` — starts output cleanup background task on startup
  - Cleanup runs every hour, deletes files older than `OUTPUT_TTL_HOURS` (default 24h)
  - `OUTPUT_TTL_HOURS` and `MAX_UPLOAD_MB` configurable via environment variables
- **`api/routers/process.py`**:
  - All FFmpeg calls now `await`ed
  - Added `_check_extension()` — validates file extensions per upload type
  - Added `_check_size()` — rejects files over `MAX_UPLOAD_MB` limit
  - Added `validate_url()` calls on all user-supplied URLs
  - ffprobe used to detect actual video dimensions when `screen_resolution` not given
  - Removed `Request` import (no longer needed after removing `request.form()`)

---

## Environment Variables

| Variable | Default | Purpose |
|---|---|---|
| `FFMPEG_TIMEOUT` | `600` | Max seconds per FFmpeg command before killing |
| `OUTPUT_TTL_HOURS` | `24` | Hours before output files are auto-deleted |
| `MAX_UPLOAD_MB` | `500` | Max upload size per file (MB) |

---

## Known Remaining Issues

| Issue | Status |
|---|---|
| No authentication / API key | Not implemented — architectural decision |
| Rate limiting | Not implemented — add `slowapi` if needed |
| `composite.py` endpoint redundancy | Still exists — kept for backward compat |
| `image_file_0/1/2` — max 3 uploads | Hardcoded — increase slots in process.py if needed |
| Fonts must be installed system-wide | No graceful error — FFmpeg silently falls back |
