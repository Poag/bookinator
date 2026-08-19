# Bookinator

Podcast mp3 &rarr; transcript. Uploads an mp3, chunks and normalizes the
audio, and transcribes it - that's the whole scope.

Runs as a self-contained Docker image with a web UI. By default
transcription goes through OpenRouter, so a single `OPENROUTER_API_KEY` is
all that's needed - or it can run fully locally instead (see
[Running fully local](#running-fully-local-transcription) below). Each
stage writes its output to disk as an inspectable JSON artifact before the
next stage runs, so it's resumable and either stage can be re-run on its
own.

## Pipeline

```
mp3 -> [1] chunk & normalize (ffmpeg)
     -> [2] transcribe chunks (OpenRouter or local) -> transcript.json
```

Transcription's provider+model is set in `config.toml` (see
`config.example.toml`, `[transcription]`): `"openrouter"` (default - an
audio-capable multimodal model, e.g. Gemini) or `"local"`
(`faster-whisper`, runs in-process, no network needed after the model is
downloaded once).

## Running it (Docker)

`docker-compose.yml` pulls the prebuilt image from
`ghcr.io/poag/bookinator:main` - published automatically by
`.github/workflows/docker-publish.yml` on every push to `main` - so no
local build or repo checkout is needed beyond `docker-compose.yml` itself.

```bash
cp .env.example .env
# edit .env and set OPENROUTER_API_KEY

docker compose up -d
```

Open http://localhost:8000. Create a project by uploading an mp3, then run
each stage from the dashboard (or "Run all remaining stages"). Uploaded
audio and every generated artifact are persisted under `./projects/`, which
is bind-mounted into the container.

No `config.toml` is required - the image installs ffmpeg on `PATH` and uses
sensible defaults for everything else. `./config/` is already bind-mounted
to `/app/config` in `docker-compose.yml` (same pattern as `./projects/`),
so to override the chunk length, model name, provider, etc., just copy
`config.example.toml` to `config/config.toml` in this directory - no
compose edits or rebuild needed, it's read at startup.

## Running it without Docker

```bash
pip install -e .
cp .env.example .env   # and fill in OPENROUTER_API_KEY
cp config.example.toml config/config.toml  # optional; edit ffmpeg_path etc.

# Web UI
uvicorn bookinator.webapp:app --reload

# or the CLI, stage by stage
bookinator new my-episode path/to/episode.mp3
bookinator chunk my-episode
bookinator transcribe my-episode
bookinator status my-episode

# or both at once
bookinator all my-episode path/to/episode.mp3
```

`ffmpeg`/`ffprobe` must be on `PATH`, or set `audio.ffmpeg_path` /
`audio.ffprobe_path` in `config.toml` (e.g. to
`C:\Tools\FFMpeg\ffmpeg.exe` on a Windows box that already has it
installed).

## Running fully local (transcription)

`faster-whisper` runs directly in the Bookinator process - no external
service needed:

```toml
[transcription]
provider = "local"
local_whisper_model = "small"       # tiny|base|small|medium|large-v3
local_whisper_device = "cpu"        # or "cuda" with a GPU + CUDA installed
local_whisper_compute_type = "int8" # "float16" is typical for GPU
```

The first run downloads the model weights (needs network access once,
cached afterward - the Docker image persists this cache in a volume). Two
things are meaningfully different from the OpenRouter/Gemini path: Whisper
does not do speaker diarization, so every transcript segment has
`speaker: null`; and larger models are noticeably slower on CPU, so start
with `small` or `medium` and only go to `large-v3` if you have a GPU or
don't mind the wait.

## Transcription getting cut off ("length")

If a transcription request ends with `finish_reason: "length"`, the
model's response was cut off by its output-token limit before finishing -
Bookinator now detects this and retries automatically (see
`http_utils.post_chat_completion`) rather than silently keeping the
truncated text, but if it keeps happening on a given project the fix is
lowering `audio.chunk_minutes` in that project's config so each chunk's
transcript needs less output per request.

## Project layout on disk

```
projects/<project-name>/
├── raw/                 # source mp3
└── transcript/
    ├── audio_chunks/    # normalized audio + per-chunk mp3s + chunks.json manifest
    ├── chunks/          # cached per-chunk transcription JSON (resumability)
    └── transcript.json  # merged transcript
```

## Editing the transcript in the UI

The `transcript.json` link on a project's dashboard opens a plain-text
editor. Saving validates the content against its schema first - an
invalid edit is rejected with an inline error and the file on disk is left
untouched.

## Verification workflow

Run against one short episode (~15-20 min) first to check cost and
quality before a full-length one. Open `transcript.json` from the
dashboard afterward to confirm segments, timestamps, and (if using
OpenRouter) speaker labels look right.
