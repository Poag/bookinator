from __future__ import annotations

from pathlib import Path

from .config import Config
from .llm import call_claude_json
from .models import ChaptersFile, StoryBible

SYSTEM_PROMPT = (
    "You are a continuity editor reviewing a full draft fantasy novel that "
    "was written one chapter at a time. Check for: character/place names "
    "used inconsistently, tone that drifts from the story bible, and "
    "timeline/event contradictions between chapters. Respond with ONLY JSON: "
    '{"issues": [{"chapter_index": int, "issue": str}], '
    '"fixes": [{"chapter_index": int, "corrected_text": str}]}. '
    'Only include a chapter in "fixes" if it actually needs a text change; '
    'leave chapters that are fine out of "fixes" entirely. corrected_text '
    "must be the full replacement chapter text (Markdown), preserving "
    "everything that was already correct."
)


def run_continuity_pass(
    chapters_file_path: Path, bible_path: Path, drafts_dir: Path, config: Config
) -> dict:
    """Stage 7: one LLM pass over the full draft, applying any fixes found."""
    chapters_file = ChaptersFile.model_validate_json(chapters_file_path.read_text())
    bible = StoryBible.model_validate_json(bible_path.read_text())

    manuscript_parts = []
    for chapter in chapters_file.chapters:
        path = drafts_dir / f"chapter_{chapter.index + 1:02d}.md"
        manuscript_parts.append(f"<!-- chapter_index={chapter.index} -->\n{path.read_text()}")
    manuscript = "\n\n".join(manuscript_parts)

    user = f"STORY BIBLE\n{bible.model_dump_json(indent=2)}\n\nFULL DRAFT\n\n{manuscript}"
    result = call_claude_json(config, SYSTEM_PROMPT, user, max_tokens=16384)

    for fix in result.get("fixes", []):
        idx = fix["chapter_index"]
        path = drafts_dir / f"chapter_{idx + 1:02d}.md"
        path.write_text(fix["corrected_text"])

    report_path = drafts_dir.parent / "continuity_report.md"
    lines = ["# Continuity Report\n"]
    issues = result.get("issues", [])
    for issue in issues:
        lines.append(f"- Chapter {issue['chapter_index'] + 1}: {issue['issue']}")
    if not issues:
        lines.append("No issues found.")
    report_path.write_text("\n".join(lines) + "\n")

    return result
