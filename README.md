# Bookinator

Podcast mp3 &rarr; fantasy novel pipeline. Transcribes an episode, splits it
into chapters, and rewrites it as fantasy prose - preserving the real plot
points, running jokes, and funny moments, just told through fantasy
characters and a fantasy world instead of "two people talking on a podcast."

Runs as a self-contained Docker image with a web UI. Every LLM call in the
pipeline goes through OpenRouter, so a single `OPENROUTER_API_KEY` is all
that's needed. Each pipeline stage writes its output to disk as an
inspectable JSON/Markdown artifact before the next stage runs, so it's
resumable and any stage can be re-run on its own (handy since transcription
and writing cost money - you shouldn't have to re-transcribe just to tweak
a prose prompt).

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

Every LLM stage goes through OpenRouter, using two configurable model slugs
(see `config.example.toml`): `transcription_model` - an audio-capable
multimodal model for stage 2 (e.g. a Gemini model, which accepts audio
input directly) - and `writing_model` - a text model used for every other
stage (chapter segmentation, extraction, the story bible, prose writing,
and the continuity pass), defaulting to `anthropic/claude-sonnet-5` for its
long-form writing quality but swappable to any OpenRouter text model.

Stages 1-2 operate on a single mp3 at a time; stages 3-8 work over one
project's transcript. The initial version targets one mp3 -> one book;
looping stages 3-8 over several transcripts sharing one story bible (to
build a season -> one book) is a natural extension but isn't wired up yet.

## Running it (Docker)

```bash
cp .env.example .env
# edit .env and set OPENROUTER_API_KEY

docker compose up --build
```

Open http://localhost:8000. Create a project by uploading an mp3, then run
each stage from the dashboard (or "Run all remaining stages"). Uploaded
audio and every generated artifact are persisted under `./projects/`, which
is bind-mounted into the container.

No `config.toml` is required - the image installs ffmpeg on `PATH` and uses
sensible defaults for everything else. See `config.example.toml` if you
want to override the chunk length, model names, etc.: copy it to
`config.toml` in this directory before building the image.

## Running it without Docker

```bash
pip install -e .
cp .env.example .env   # and fill in OPENROUTER_API_KEY
cp config.example.toml config.toml  # optional; edit ffmpeg_path etc.

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

## Project layout on disk

```
projects/<project-name>/
├── raw/                 # source mp3
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

## Verification workflow

Run the pipeline on one short episode (~15-20 min) first to check cost and
quality before a full-length one. After each stage, open its artifact from
the dashboard ("Artifacts" links, or read the JSON/Markdown directly under
`projects/<name>/`) to confirm it looks right before paying for the next
stage. Once `manuscript.md` is assembled, read it chapter-by-chapter
against `notes.json` to confirm the jokes/plot points made it into the
prose and that character names stay consistent across chapters.
