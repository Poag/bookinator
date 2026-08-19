FROM python:3.11-slim

# ffmpeg package on Debian provides both ffmpeg and ffprobe on PATH.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml ./
COPY bookinator ./bookinator
RUN pip install --no-cache-dir .

# Projects (uploaded audio + generated artifacts) live here; mount a volume
# at this path to persist them across container restarts. /app/config holds
# config.toml - mount the whole directory so dropping a file in there just
# works with no per-file compose changes.
RUN mkdir -p /app/projects /app/config
VOLUME ["/app/projects", "/app/config"]

EXPOSE 8000

CMD ["uvicorn", "bookinator.webapp:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
