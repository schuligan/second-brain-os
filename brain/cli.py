"""`brain` command-line entrypoint.

Subcommands:
  brain index            Rebuild the embedding index.
  brain capture <text>   Classify a raw thought and (with approval) file it.
  brain search <query>   Ranked embeddings search across the vault.
  brain link             Suggest [[wikilinks]] between related notes (--apply to write).
  brain daily            Synthesize today's daily note (--write to save).
"""

from __future__ import annotations

import argparse
import sys

from rich.console import Console
from rich.markup import escape
from rich.panel import Panel
from rich.table import Table

from .agent import capture_classify, capture_file, synthesize_daily
from .config import MOCK_BANNER, load_config
from .index import BrainIndex
from .llm import get_llm
from .vault import write_note

console = Console()


def _banner(config) -> None:
    if config.is_mock:
        console.print(f"[yellow]{MOCK_BANNER}[/yellow]")
    else:
        console.print(f"[green]LLM mode — model {config.model_id}[/green]")


def _confirm(prompt: str, assume_yes: bool) -> bool:
    """Approval gate. --yes skips the prompt; non-interactive defaults to no."""
    if assume_yes:
        return True
    if not sys.stdin.isatty():
        console.print("[dim]Non-interactive shell; pass --yes to approve writes.[/dim]")
        return False
    answer = console.input(f"{prompt} [y/N] ").strip().lower()
    return answer in ("y", "yes")


def cmd_index(args, config) -> int:
    index = BrainIndex.build(config.vault)
    index.save(config.index_path)
    console.print(
        f"[green]Indexed {len(index.notes)} notes[/green] -> {config.index_path}"
    )
    return 0


def cmd_capture(args, config) -> int:
    text = " ".join(args.text).strip()
    if not text:
        console.print("[red]Nothing to capture.[/red]")
        return 1

    index = BrainIndex.load(config.vault, config.index_path)
    llm = get_llm(config)
    plan = capture_classify(text, index, llm)
    c = plan.classification

    console.print(
        Panel(
            f"[bold]{escape(c.title)}[/bold]\n\n"
            f"folder:  [cyan]{c.folder}/[/cyan]\n"
            f"tags:    {escape(', '.join(c.tags))}\n"
            f"related: {escape(', '.join(c.related_slugs) or '(none)')}\n"
            f"why:     [dim]{escape(c.reasoning)}[/dim]",
            title="Proposed filing",
            border_style="cyan",
        )
    )
    console.print(Panel(escape(plan.body), title="Note body", border_style="dim"))

    if not _confirm("File this note?", args.yes):
        console.print("[yellow]Skipped — nothing written.[/yellow]")
        return 0

    path = capture_file(plan, config)
    console.print(f"[green]Filed[/green] -> {path.relative_to(config.vault.parent)}")
    return 0


def cmd_search(args, config) -> int:
    query = " ".join(args.query).strip()
    index = BrainIndex.load(config.vault, config.index_path)
    hits = index.search(query, top_k=args.top_k)
    if not hits:
        console.print(f"[yellow]No matches for[/yellow] {query!r}")
        return 0

    table = Table(title=f"Search: {query!r}")
    table.add_column("score", justify="right", style="cyan")
    table.add_column("note", style="bold")
    table.add_column("snippet")
    for hit in hits:
        table.add_row(f"{hit.score:.3f}", escape(hit.path), escape(hit.snippet))
    console.print(table)
    return 0


def cmd_link(args, config) -> int:
    index = BrainIndex.load(config.vault, config.index_path)
    suggestions = index.suggest_links()
    if not suggestions:
        console.print("[green]No new links to suggest — everything connected.[/green]")
        return 0

    table = Table(title="Suggested wikilinks")
    table.add_column("score", justify="right", style="cyan")
    table.add_column("source")
    table.add_column("link")
    for s in suggestions:
        table.add_row(f"{s.score:.3f}", escape(s.source_path), escape(f"[[{s.target_slug}]]"))
    console.print(table)

    if not args.apply:
        console.print("[dim]Run with --apply to append these links (--yes to skip prompt).[/dim]")
        return 0
    if not _confirm(f"Append {len(suggestions)} links?", args.yes):
        console.print("[yellow]Skipped — nothing written.[/yellow]")
        return 0

    written = _apply_links(index, suggestions, config)
    console.print(f"[green]Updated {written} notes with wikilinks.[/green]")
    return 0


def _apply_links(index: BrainIndex, suggestions, config) -> int:
    """Append a ## Related section (or extend it) to each source note."""
    from collections import defaultdict

    by_source: dict[str, list[str]] = defaultdict(list)
    for s in suggestions:
        by_source[s.source_path].append(s.target_slug)

    for source_path, slugs in by_source.items():
        note = index.get(source_path)
        if note is None:
            continue
        new_links = [f"- [[{slug}]]" for slug in slugs if f"[[{slug}]]" not in note.body]
        if not new_links:
            continue
        body = note.body
        if "## Related" not in body:
            body += "\n\n## Related\n"
        body += "\n" + "\n".join(new_links)
        (config.vault / source_path).write_text(
            _reserialize(note, body), encoding="utf-8"
        )
    return len(by_source)


def _reserialize(note, body: str) -> str:
    from .vault import render_note

    return render_note(note.frontmatter, body)


def cmd_daily(args, config) -> int:
    index = BrainIndex.load(config.vault, config.index_path)
    frontmatter, body = synthesize_daily(index)
    console.print(Panel(escape(body), title=escape(frontmatter.title), border_style="cyan"))

    if not args.write:
        console.print("[dim]Run with --write to save into daily/ (--yes to skip prompt).[/dim]")
        return 0
    if not _confirm("Write daily note?", args.yes):
        console.print("[yellow]Skipped — nothing written.[/yellow]")
        return 0

    path = write_note(config.vault, "daily", frontmatter, body)
    console.print(f"[green]Wrote[/green] -> {path.relative_to(config.vault.parent)}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="brain",
        description="A Markdown second brain with agentic capture.",
    )
    parser.add_argument(
        "--vault",
        default=None,
        help="Path to the vault (default: ./vault or $BRAIN_VAULT)",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_index = sub.add_parser("index", help="Rebuild the embedding index")
    p_index.set_defaults(func=cmd_index)

    p_capture = sub.add_parser("capture", help="Capture and file a raw thought")
    p_capture.add_argument("text", nargs="+", help="The raw thought to capture")
    p_capture.add_argument("--yes", action="store_true", help="Approve the write without prompting")
    p_capture.set_defaults(func=cmd_capture)

    p_search = sub.add_parser("search", help="Search the vault by meaning")
    p_search.add_argument("query", nargs="+", help="Search query")
    p_search.add_argument("--top-k", type=int, default=5, help="Number of results")
    p_search.set_defaults(func=cmd_search)

    p_link = sub.add_parser("link", help="Suggest (and optionally apply) wikilinks")
    p_link.add_argument("--apply", action="store_true", help="Write the suggested links")
    p_link.add_argument("--yes", action="store_true", help="Approve the write without prompting")
    p_link.set_defaults(func=cmd_link)

    p_daily = sub.add_parser("daily", help="Synthesize today's daily note")
    p_daily.add_argument("--write", action="store_true", help="Save the note into daily/")
    p_daily.add_argument("--yes", action="store_true", help="Approve the write without prompting")
    p_daily.set_defaults(func=cmd_daily)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    config = load_config(args.vault)

    if not config.vault.is_dir():
        console.print(f"[red]Vault not found:[/red] {config.vault}")
        console.print("[dim]Run from the repo root, or pass --vault PATH.[/dim]")
        return 1

    _banner(config)
    return args.func(args, config)


if __name__ == "__main__":
    raise SystemExit(main())
