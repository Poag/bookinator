from __future__ import annotations

from pathlib import Path

from .models import ChaptersFile


def assemble_manuscript(chapters_file_path: Path, drafts_dir: Path, project: str, out_path: Path) -> Path:
    """Stage 8: assemble all chapter drafts into one manuscript.md with a TOC."""
    chapters_file = ChaptersFile.model_validate_json(chapters_file_path.read_text())

    toc_lines = [f"# {project}\n", "## Table of Contents\n"]
    body_parts = []
    for chapter in chapters_file.chapters:
        draft_path = drafts_dir / f"chapter_{chapter.index + 1:02d}.md"
        text = draft_path.read_text().strip()
        toc_lines.append(f"{chapter.index + 1}. {chapter.title}")
        body_parts.append(text)

    manuscript = "\n".join(toc_lines) + "\n\n---\n\n" + "\n\n---\n\n".join(body_parts) + "\n"
    out_path.write_text(manuscript)
    return out_path
