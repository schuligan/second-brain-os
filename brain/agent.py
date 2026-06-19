"""Agentic workflows: capture (classify -> approve -> file), linking, daily note.

The capture flow is approval-gated: classify() proposes a plan, and only file()
writes to disk. Nothing is written without an explicit commit, and writes never
overwrite an existing file.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

from .config import Config
from .index import BrainIndex
from .llm import LLM
from .models import Classification, Frontmatter, Note
from .vault import write_note

RECENT_LOOKBACK_DAYS = 7


class CapturePlan:
    """A proposed filing, produced by classify(), committed by file()."""

    def __init__(self, raw_text: str, classification: Classification, body: str):
        self.raw_text = raw_text
        self.classification = classification
        self.body = body


def capture_classify(
    raw_text: str, index: BrainIndex, llm: LLM, top_k: int = 5
) -> CapturePlan:
    """Classify a raw thought into a filing plan. Does NOT write anything."""
    candidate_hits = index.search(raw_text, top_k=top_k)
    candidate_slugs = [Path(h.path).stem for h in candidate_hits]
    classification = llm.classify(raw_text, candidate_slugs).normalized()

    # Build the note body: the thought plus auto-suggested wikilinks.
    links = [
        f"[[{slug}]]"
        for slug in classification.related_slugs
        if slug in candidate_slugs
    ]
    body = raw_text.strip()
    if links:
        body += "\n\n## Related\n" + "\n".join(f"- {link}" for link in links)
    return CapturePlan(raw_text=raw_text, classification=classification, body=body)


def capture_file(plan: CapturePlan, config: Config) -> Path:
    """Commit a CapturePlan to disk. Approval-gated: callers gate before calling."""
    frontmatter = Frontmatter(
        title=plan.classification.title,
        tags=plan.classification.tags,
        created=Frontmatter.today(),
    )
    return write_note(
        config.vault, plan.classification.folder, frontmatter, plan.body
    )


def _is_recent(note: Note, lookback_days: int) -> bool:
    """True if the note's created date is within the lookback window."""
    try:
        created = date.fromisoformat(note.frontmatter.created)
    except ValueError:
        return False
    return (date.today() - created).days <= lookback_days


def synthesize_daily(
    index: BrainIndex, lookback_days: int = RECENT_LOOKBACK_DAYS
) -> tuple[Frontmatter, str]:
    """Generate today's daily note: recent captures + open project notes.

    Returns (frontmatter, body) so the caller can preview before writing.
    """
    recent = [
        n
        for n in index.notes
        if n.folder in ("inbox", "notes", "references") and _is_recent(n, lookback_days)
    ]
    projects = [n for n in index.notes if n.folder == "projects"]

    today = date.today().isoformat()
    lines = [f"# Daily Note — {today}", ""]

    lines.append("## Recent captures")
    if recent:
        for note in recent:
            tags = " ".join(f"#{t}" for t in note.frontmatter.tags)
            lines.append(f"- [[{note.slug}]] — {note.frontmatter.title} {tags}".rstrip())
    else:
        lines.append("- _(nothing captured in the last "
                     f"{lookback_days} days)_")

    lines.append("")
    lines.append("## Open projects")
    if projects:
        for note in projects:
            lines.append(f"- [[{note.slug}]] — {note.frontmatter.title}")
    else:
        lines.append("- _(no active project notes)_")

    frontmatter = Frontmatter(
        title=f"Daily Note {today}",
        tags=["daily"],
        created=today,
    )
    return frontmatter, "\n".join(lines)
