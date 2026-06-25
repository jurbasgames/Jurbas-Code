# RAG Code Indexing Architecture Implementation Plan

> **For Hermes/Jurbas-Code:** implement this incrementally. Do not send the whole plan as one Jules task. Each phase below is one bounded GitHub issue/PR. Do not add the `jules` label until we explicitly decide to dispatch the task.

**Goal:** Turn Jurbas-Code into a code-aware agent that indexes the repository, retrieves the right context, plans edits with a strong model, applies span-based rewrites safely, and validates speculative candidates.

**Architecture:** Build a local-first indexing and retrieval pipeline: file manifest + content hashes, Python AST chunks, incremental SQLite-backed index, retrieval/reranking, context window builder, span-based edit application, model routing, speculative validation, and eventually streaming/parallel tool execution. The filesystem write path should write full files atomically, but the model should generate only targeted span replacements rather than line-number diffs.

**Tech Stack:** Python stdlib-first for early phases (`ast`, `sqlite3`, `hashlib`, `pathlib`, `tempfile`). Optional later dependencies may include `sqlite-vec`/Qdrant/Chroma for vector search and `tree-sitter` for multi-language parsing, but tests must not require external services.

---

## Non-negotiable guardrails

- No monolithic PRs.
- No auto-merge.
- Do not add the `jules` label until dispatch is explicitly approved.
- Preserve current CLI behavior and existing tests.
- Prefer stdlib/local components before external services.
- Tests must run without live model/API calls.
- Use deterministic fake embeddings/rerankers in tests.
- Avoid line-number diffs for editing; use span IDs, content hashes, and atomic full-file writes.
- Every PR must run:

```bash
python -m py_compile main.py jurbas_code/**/*.py tests/*.py
uv run --extra dev pytest -q
```

Adjust the glob command if the shell does not expand `**`; the intent is to compile all changed Python files.

---

## Target package layout

```text
jurbas_code/
  config.py
  models/
    router.py              # planner/editor/ranker/embedder selection
    clients.py             # provider clients, later
  indexing/
    manifest.py            # file discovery + ignores
    hashing.py             # sha256/mtime/size
    ast_chunks.py          # Python AST chunker
    tree_sitter_chunks.py  # future multi-language chunking
    store.py               # SQLite index schema
    indexer.py             # incremental reindex pipeline
  retrieval/
    embeddings.py          # embedding provider interface + fake provider
    vector_store.py        # vector abstraction / local similarity
    lexical.py             # FTS/BM25 fallback
    reranker.py            # small-model/heuristic reranker
    context_builder.py     # priority-aware context packing
  editing/
    spans.py               # stable span IDs and hash anchors
    planner.py             # frontier planning interface
    apply.py               # span replacement application
    atomic_write.py        # safe full-file writes
    speculative.py         # candidate generation + validation
  tools/
    schemas.py
    handlers.py
    parallel.py            # parallel read-only tool executor
  validation.py
  cli.py
  main.py
```

---

## Context priority policy

The context builder should pack model context in this order:

| Priority | Context source | Rationale |
|---:|---|---|
| 1 | System prompt + active user task | Cannot be dropped |
| 2 | Active/open file or target edit span | Highest local relevance |
| 3 | Neighbor AST symbols in the same file | Maintains structural coherence |
| 4 | Recently modified files | Strong temporal signal |
| 5 | Direct imports/callees/callers | Static dependency signal |
| 6 | Top lexical/vector retrieved chunks | Semantic/codebase search |
| 7 | Reranked chunks | Final relevance quality pass |
| 8 | Repository map/summaries | Useful but lower priority |

Initial scoring can be heuristic:

```text
score =
  +1000 if active/open file
  +500 if target edit file
  +200 if recently modified
  +150 if direct import/dependency
  +100 if same module/package
  + lexical_score
  + vector_similarity
  + reranker_score
```

---

## Span-based edit format

Models should not emit unified diffs or line-number patches for normal edits. They should return structured span replacements:

```json
{
  "edits": [
    {
      "span_id": "main.py::function:write_file::sha256:abc123",
      "replacement_text": "def write_file(...):\n    ...",
      "reason": "Add atomic write with backup"
    }
  ]
}
```

The local edit engine must:

1. resolve the span ID;
2. verify the original content hash still matches;
3. apply replacement in memory;
4. write the complete file atomically;
5. back up or preserve rollback path;
6. run validation.

This gives us full-file writes on disk without forcing the model to regenerate unchanged file content.

---

## Model routing

| Role | Model class | Job |
|---|---|---|
| Planner | frontier | Understand task, plan approach, choose files/spans |
| Editor | medium | Generate span replacements / candidate edits |
| Ranker | small | Score chunks/candidates, cheap reranking |
| Embedder | embedding model/local provider | Generate chunk vectors |

Tests must use fake deterministic providers.

---

## GitHub issue / PR sequence

Created backlog issues, intentionally **without** the `jules` label:

| # | Issue | Purpose |
|---:|---|---|
| [#47](https://github.com/jurbasgames/Jurbas-Code/issues/47) | [RAG Pipeline] Epic: AST indexing, retrieval, span edits, and model routing | Epic tracker |
| [#48](https://github.com/jurbasgames/Jurbas-Code/issues/48) | [RAG Pipeline] 01 — package/config foundation | Package/config foundation |
| [#49](https://github.com/jurbasgames/Jurbas-Code/issues/49) | [RAG Pipeline] 02 — file manifest and hash tracking | File manifest + hash tracking |
| [#50](https://github.com/jurbasgames/Jurbas-Code/issues/50) | [RAG Pipeline] 03 — SQLite index store | SQLite metadata store |
| [#51](https://github.com/jurbasgames/Jurbas-Code/issues/51) | [RAG Pipeline] 04 — Python AST chunker | Python AST chunks/spans |
| [#52](https://github.com/jurbasgames/Jurbas-Code/issues/52) | [RAG Pipeline] 05 — incremental indexer | Incremental reindex pipeline |
| [#53](https://github.com/jurbasgames/Jurbas-Code/issues/53) | [RAG Pipeline] 06 — embedding provider interface | Embedding abstraction/fakes |
| [#54](https://github.com/jurbasgames/Jurbas-Code/issues/54) | [RAG Pipeline] 07 — lexical/vector retrieval MVP | Retrieval MVP |
| [#55](https://github.com/jurbasgames/Jurbas-Code/issues/55) | [RAG Pipeline] 08 — reranker interface | Reranker abstraction |
| [#56](https://github.com/jurbasgames/Jurbas-Code/issues/56) | [RAG Pipeline] 09 — priority-aware context builder | Context packing/priorities |
| [#57](https://github.com/jurbasgames/Jurbas-Code/issues/57) | [RAG Pipeline] 10 — span-based edit application and atomic full-file writes | Safe span edits |
| [#58](https://github.com/jurbasgames/Jurbas-Code/issues/58) | [RAG Pipeline] 11 — model router for planner/editor/ranker/embedder roles | Multi-model routing |
| [#59](https://github.com/jurbasgames/Jurbas-Code/issues/59) | [RAG Pipeline] 12 — speculative edits and validation loop | Candidate validation |
| [#60](https://github.com/jurbasgames/Jurbas-Code/issues/60) | [RAG Pipeline] 13 — streaming and parallel read-only tool calls | Streaming/parallel tools |
| [#61](https://github.com/jurbasgames/Jurbas-Code/issues/61) | [TUI] Build a decent terminal UI for Jurbas-Code | TUI/event UI |

### 0. Epic: RAG/code-indexing architecture tracker

Tracks the whole effort, links all sub-issues, and keeps the non-goals explicit.

### 1. Package/config foundation

Create package skeleton and typed config without changing current runtime behavior.

### 2. File manifest + hash tracking

Discover indexable files, ignore generated/vendor paths, track sha256/mtime/size, and classify new/changed/unchanged/deleted files.

### 3. SQLite index store

Persist files/chunks/metadata in a local SQLite DB. No vector search yet.

### 4. Python AST chunker

Use Python `ast` and byte offsets to chunk modules, classes, and functions into stable spans.

### 5. Incremental indexer

Combine manifest, hash tracking, AST chunking, and SQLite persistence. Reindex only changed files.

### 6. Embedding provider interface

Add provider abstraction and fake deterministic embeddings for tests. No live API calls in tests.

### 7. Lexical/vector retrieval MVP

Return relevant chunks from lexical/FTS and local vector similarity. Keep vector backend replaceable.

### 8. Reranker interface

Add small-model/heuristic reranker interface and deterministic local test implementation.

### 9. Priority-aware context builder

Pack active file, recent files, static neighbors, and retrieved/reranked chunks into a token budget with reasons.

### 10. Span-based edit application + atomic full-file writes

Implement stable spans, replacement application, hash guards, backups, and atomic writes.

### 11. Model router

Separate planner/editor/ranker/embedder model roles with config-driven selection.

### 12. Speculative edits + validation loop

Generate candidates in temp dirs, run validation, and select the safest passing edit.

### 13. Streaming and parallel tool calls

Allow independent read-only tools/retrieval/indexing to run concurrently while keeping mutating actions serialized.

### 14. Decent TUI

Build a terminal UI that shows conversation, streaming, tool calls, indexing state, selected context, pending edits, validation output, and confirmation prompts.

---

## MVP cut

The first useful MVP is not the full system. It is:

```text
file manifest + hash tracking
+ Python AST chunks
+ SQLite incremental index
+ priority-aware context builder
+ span-based edit application
```

Embeddings, vector DB, reranking, speculative edits, and parallel streaming should come after the incremental index and span edit engine are stable.

---

## TUI design note

The TUI should be built after the agent loop is extracted enough to expose events. It should consume structured events instead of scraping prints:

```text
AssistantToken
ToolCallStarted
ToolCallFinished
IndexingStarted
IndexingFinished
ContextSelected
EditCandidateGenerated
ValidationStarted
ValidationFinished
UserConfirmationRequired
```

Initial TUI can use `rich` or `textual`, but avoid forcing the dependency into core runtime until the CLI/event boundary is clear.
