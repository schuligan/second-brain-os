# Implementation Plan — second-brain-os

## Goals

1. A Markdown vault that is a real, openable Obsidian-style knowledge base —
   plain `.md` files with YAML frontmatter, organized by a clear taxonomy.
2. An **agentic capture** flow that turns a raw thought into a properly filed,
   tagged, and linked note — with a hard approval gate before any write.
3. **Semantic search** and **auto-linking** driven by embeddings.
4. **Daily-note synthesis** that summarizes recent activity.
5. **Offline-first**: works with zero secrets in a deterministic mock mode;
   upgrades to a real LLM only when a key is present. Tests and demo never need
   network or keys.

Non-goals: a GUI, a sync server, multi-user support, or production-grade
transformer embeddings. Those are roadmap items, not v1.

## Folder taxonomy

| Folder        | Purpose                                              |
|---------------|------------------------------------------------------|
| `inbox/`      | Raw, unprocessed thoughts awaiting filing.           |
| `notes/`      | Evergreen knowledge: recipes, routines, methods.     |
| `daily/`      | Dated daily notes (synthesized or hand-written).     |
| `projects/`   | Active project notes with milestones.                |
| `references/` | Book notes, articles, quotes — things consumed.      |

Every note carries frontmatter: `title`, `tags` (list), `created` (ISO date).
The folder list is the single source of truth in `config.FOLDERS`; the classifier
coerces any unknown folder back to `notes`.

## Capture-agent design

The capture flow is split into two explicit phases so the write is always gated:

1. **`capture_classify(text, index, llm)` — pure, no side effects.**
   - Embeds the raw text and runs a semantic search to find candidate related
     notes (their slugs become link candidates).
   - Calls the LLM backend's `classify()` to get `{title, folder, tags,
     summary, related_slugs}`.
   - Assembles the note body: the original thought plus an auto-generated
     `## Related` section of `[[wikilinks]]` to the candidates the model picked.
   - Returns a `CapturePlan`. **Nothing is written.**

2. **`capture_file(plan, config)` — the only writer.**
   - Builds frontmatter (`created = today`) and writes via the non-destructive
     `write_note`, which picks a non-colliding filename (`-2`, `-3`, ...).

The CLI sits between them with `_confirm()`: it prints the plan, then requires
`--yes` (or interactive `y`) to call `capture_file`. In a non-interactive shell
without `--yes`, it refuses to write. This makes "never silently overwrite" and
"approval-gated writes" structural properties, not conventions.

### Two interchangeable LLM backends

`llm.py` defines an `LLM` Protocol with one method, `classify()`:

- **`MockLLM`** (default, offline): keyword heuristics map text to a folder and
  tags. Whole-word matching (not substring) avoids false positives like "bread"
  triggering the "read" keyword. Fully deterministic.
- **`AnthropicLLM`** (real path): lazily imports `anthropic`, sends a structured
  system prompt, and parses a JSON classification. Activated only when
  `ANTHROPIC_API_KEY` is set and the package is installed.

`get_llm(config)` returns one or the other based solely on key presence, so no
other module branches on mode.

## Linking / embedding approach

- **Embedder** (`embedder.py`): a deterministic "hashing trick" bag-of-words
  vectorizer. Each token is hashed (blake2b) into one of `EMBED_DIM=256` buckets;
  the vector is L2-normalized so cosine similarity is a dot product. Stopwords and
  ≤1-char tokens are dropped. No model download, no network — identical results in
  CI, locally, and offline.
- **Weighting**: `Note.searchable_text` repeats the title and (especially) tags so
  shared tags act as a strong relatedness signal. Without this, short notes barely
  register similarity; with it, genuinely-related notes separate cleanly from
  hash-collision noise.
- **Index** (`index.py`): a `path -> vector` map persisted as JSON under
  `.brain/index.json` (gitignored, rebuildable with `brain index`).
  - `search(query, k)` ranks all notes by cosine to the query, with query-aware
    snippets.
  - `suggest_links()` proposes `[[wikilinks]]` for note pairs above
    `LINK_THRESHOLD=0.12`, skipping links that already exist in the body.

## Daily synthesis

`synthesize_daily(index, lookback_days=7)` collects notes from
`inbox/notes/references` created within the lookback window plus all `projects/`
notes, and renders a dated daily note with `## Recent captures` and
`## Open projects` sections (each item a wikilink). It returns
`(frontmatter, body)` so the CLI can preview before `--write` commits it.

## Trade-offs

- **Hashing embedder vs. transformer**: chosen for zero-dependency determinism and
  offline CI. Cost: weaker semantic nuance. Mitigated by tag weighting; the
  `embed()` function is the single swap point for real embeddings.
- **Keyword mock classifier vs. LLM**: the mock is crude but deterministic and
  testable. The real path exists and shares the same interface; the demo just
  doesn't depend on it.
- **JSON index vs. a vector DB**: a flat JSON file is trivially inspectable and
  rebuildable for a vault of this size. A real vault would want incremental
  indexing (roadmap).
- **Two-phase capture vs. one-shot**: a touch more code, but it makes the approval
  gate and non-destructive-write guarantees impossible to bypass by accident.

## Phased plan

- **Phase 1 — Vault + I/O** (done): taxonomy, frontmatter parse/render,
  non-destructive writes, seeded synthetic notes.
- **Phase 2 — Embeddings + search** (done): hashing embedder, index, ranked
  search with snippets.
- **Phase 3 — Agentic capture** (done): dual LLM backend, two-phase
  classify/file, approval gate, auto-wikilinks.
- **Phase 4 — Linking + daily** (done): `suggest_links`, `--apply`, daily
  synthesis.
- **Phase 5 — CLI + tests** (done): `brain` entrypoint, 25 pytest tests, ruff
  clean, all mock-mode/no-network.
- **Phase 6 — Roadmap**: backlinks, incremental indexing, pluggable real
  embeddings, inbox draining, graph export, watch mode.

## Testing strategy

All tests run in mock mode with no network or secrets (see `tests/`):

- `test_embedder.py` — determinism, normalization, relative similarity ordering.
- `test_vault.py` — frontmatter parsing, slugify, non-destructive writes.
- `test_index.py` — search ranking, query-aware snippets, link suggestions,
  index round-trip.
- `test_agent.py` — classify is side-effect-free, file requires explicit commit,
  no overwrite, wikilinks added, daily sections generated.
- `test_cli.py` — end-to-end via `main()`: index/search work, capture without
  `--yes` writes nothing, capture with `--yes` files, daily preview vs. `--write`.
