# Bookinator

Podcast mp3 &rarr; fantasy novel pipeline. Transcribes an episode, splits it
into chapters, and rewrites it as fantasy prose - preserving the real plot
points, running jokes, and funny moments, just told through fantasy
characters and a fantasy world instead of "two people talking on a podcast."

Runs as a self-contained Docker image with a web UI. By default every LLM
call in the pipeline goes through OpenRouter, so a single
`OPENROUTER_API_KEY` is all that's needed - but transcription and/or prose
writing can each be switched to run fully locally instead (see
[Running fully local](#running-fully-local-ollama--local-transcription)
below). Each pipeline stage writes its output to disk as an inspectable
JSON/Markdown artifact before the next stage runs, so it's resumable and
any stage can be re-run on its own (handy since cloud transcription/writing
cost money - you shouldn't have to re-transcribe just to tweak a prose
prompt).

## Pipeline

```
mp3 -> [1] chunk & normalize (ffmpeg)
     -> [2] transcribe chunks (OpenRouter, audio-capable model) -> transcript + timestamps
     -> [3] segment into chapters (LLM)                          -> chapters.json
     -> [4] extract plot points / jokes / quotes per chapter (LLM) -> notes.json
     -> [5] build story bible (fantasy world, character mapping)   -> bible.json
     -> [6] write each chapter as fantasy prose (OpenRouter, text model) -> chapter_NN.md
     -> [7] continuity pass over the full draft                    -> fixes applied
     -> [8] assemble manuscript.md + table of contents
```

Every LLM-calling stage - transcription plus each of chapterize/extract/
bible/write/continuity - has its own provider+model, defaulting to
`config.toml` (see `config.example.toml`): transcription is
`"openrouter"` (an audio-capable multimodal model, e.g. Gemini) or
`"local"` (`faster-whisper`, runs in-process); the rest are `"openrouter"`
(default - `anthropic/claude-sonnet-5`) or `"ollama"` (a self-hosted
server). Each project can independently override any of these six from
its dashboard's **Routing settings** page - e.g. run transcription and
extraction on OpenRouter but writing and the story bible on a local Ollama
model, for this project only. Fields left blank inherit the global
`config.toml` default, so most projects need no overrides at all.

Stages 1-2 operate on a single mp3 at a time; stages 3-8 work over one
project's transcript. The initial version targets one mp3 -> one book;
looping stages 3-8 over several transcripts sharing one story bible (to
build a season -> one book) is a natural extension but isn't wired up yet.

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
so to override the chunk length, model names, providers, etc., just copy
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
bookinator chapterize my-episode
bookinator extract my-episode
bookinator bible my-episode
bookinator write my-episode
bookinator continuity my-episode
bookinator assemble my-episode
bookinator status my-episode

# or everything at once
bookinator all my-episode path/to/episode.mp3
```

`ffmpeg`/`ffprobe` must be on `PATH`, or set `audio.ffmpeg_path` /
`audio.ffprobe_path` in `config.toml` (e.g. to
`C:\Tools\FFMpeg\ffmpeg.exe` on a Windows box that already has it
installed).

## Running fully local (Ollama + local transcription)

Both LLM roles can run without any cloud API. Bookinator doesn't bundle
Ollama - point it at one you already have running.

**Writing via Ollama:**

```bash
ollama pull llama3.1:70b   # or any other text model you want to write with
```

```toml
[writing]
provider = "ollama"
ollama_model = "llama3.1:70b"

[ollama]
base_url = "http://localhost:11434"
# In Docker: base_url = "http://host.docker.internal:11434"
# (docker-compose.yml already adds the extra_hosts entry that makes this
# resolve on Linux, not just Docker Desktop)
```

Model quality matters here more than in most Ollama use cases - the writing
stages are asked to hit specific plot points/jokes and return structured
JSON, so a smaller/weaker model may drift off-task or produce invalid JSON
more often than Claude does. A large instruction-tuned model (30B+) is a
safer starting point; a GPU is strongly recommended for that size on
anything but a short episode - CPU-only inference on a 70B model will be
very slow.

**Local transcription (no Ollama involved - faster-whisper runs directly
in the Bookinator process):**

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
`speaker: null` (later stages already treat speaker as optional, so this
doesn't break anything downstream, it just means chapters/prose can't
distinguish who said what); and larger models are noticeably slower on
CPU, so start with `small` or `medium` and only go to `large-v3` if you
have a GPU or don't mind the wait.

## Project layout on disk

```
projects/<project-name>/
├── raw/                 # source mp3
├── settings.json        # per-project provider/model overrides (optional)
├── transcript/
│   ├── audio_chunks/    # normalized audio + per-chunk mp3s + chunks.json manifest
│   ├── chunks/          # cached per-chunk transcription JSON (resumability)
│   └── transcript.json  # merged transcript
├── chapters/
│   ├── chapters.json
│   └── notes.json
├── bible.json
├── drafts/
│   └── chapter_01.md, chapter_02.md, ...
├── continuity_report.md
└── manuscript.md
```

## Editing artifacts in the UI

Every artifact link on a project's dashboard (`chapters.json`, `notes.json`,
`bible.json`, chapter drafts, `manuscript.md`) opens a plain-text editor
instead of just a viewer. Saving `chapters.json`, `notes.json`, or
`bible.json` validates the content against its schema first - an invalid
edit is rejected with an inline error and the file on disk is left
untouched; chapter drafts and the manuscript are freeform Markdown, so
anything goes. There's no dependency tracking between stages, so editing
an upstream file (e.g. fixing a plot point in `notes.json`) doesn't
automatically redo downstream work - re-run whichever later stages should
pick up the change.

## Verification workflow

Run the pipeline on one short episode (~15-20 min) first to check cost and
quality before a full-length one. After each stage, open its artifact from
the dashboard ("Artifacts" links, or read the JSON/Markdown directly under
`projects/<name>/`) to confirm it looks right before paying for the next
stage. Once `manuscript.md` is assembled, read it chapter-by-chapter
against `notes.json` to confirm the jokes/plot points made it into the
prose and that character names stay consistent across chapters.
