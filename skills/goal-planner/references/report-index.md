# Execution Report Index

Read this reference when a target repository already contains `docs/report-index/catalog.jsonl`, or when its execution-report collection has crossed an activation threshold.

## Ownership and activation

- Treat Markdown files under `docs/failed-reports/` and `docs/passed-reports/` as the only source of truth.
- Keep `docs/researches/` outside this catalog. Research has a separate advisory evidence lifecycle and must not be represented as a failed or passed execution report.
- Treat `docs/report-index/catalog.jsonl` as committed, deterministic derived data. Never edit or merge its entries by hand; regenerate it from the reports.
- Activate the committed catalog when either report directory already uses it, when the combined report count reaches 100, when header metadata exceeds 200 KiB, or when repeated raw report searches take more than one second. Below those thresholds, keep using filename/header scans plus raw full-text search without adding index artifacts.
- When activating it, copy [../scripts/report_index.py](../scripts/report_index.py) to `docs/report-index/report_index.py` unless the repository has a compatible project-specific tool. Keep its generator version with the copied script.
- Regenerate the catalog in the same change as any indexed report create, update, resolution, or supersession.

## Derived record contract

Each JSONL entry represents exactly one report and contains:

- `source_path`, `source_hash`, `kind`, status, recorded time, title, and a stable path-based ID.
- Routing fields for problem signature, exact sanitized identifiers, related code paths, environment and versions, affected/excluded scope, search terms, and approaches.
- A rich structured capsule extracted from the report's designated fields and tables. Failure capsules retain trigger, expected/observed behavior, impact, evidence conclusion, cause and confidence, failed attempts and reasons, resolution or next step, and reuse boundaries. Passed capsules retain qualification, prerequisites, sequence, decisive choices, avoided approaches, completion evidence, and reuse/invalidation boundaries.
- Lifecycle and cross-kind links.

Do not generate new prose for the catalog. Every content value must come from the sanitized source report. Exact error strings, paths, symbols, APIs, test names, versions, uncertainty, failed approaches, and exclusion conditions must not be shortened merely to meet a size target. Avoid copying raw evidence that the source report intentionally keeps behind an access-controlled reference.

The catalog begins with a schema/generator metadata record. Schema changes rebuild the derived catalog; they do not require rewriting legacy reports.

## Commands

Run the repository copy when present:

```bash
python3 docs/report-index/report_index.py sync --root .
python3 docs/report-index/report_index.py query --root . "<error, path, environment, or approach>"
python3 docs/report-index/report_index.py check --root .
```

During skill development, run the bundled script against an explicit target root instead.

- `sync` parses both report sets and atomically regenerates stable path-sorted JSONL.
- `query` validates the catalog, combines structured matches with every raw Markdown report, resolves superseded results to current successors, and emits bounded JSON candidates. It does not expose every stored capsule.
- `check` verifies schema and generator metadata, report-to-entry parity, hashes, deterministic derived content, lifecycle links, and resolved-failure cross-links. A nonzero exit means the catalog must not be trusted.

If the catalog is absent, malformed, stale, or lifecycle-invalid, `query` reports the reason and falls back to current raw reports. The fallback is required for backward compatibility and must never hide old reports.

## Ranking and reading budget

Rank matches in this order:

1. Exact error or problem signature.
2. Exact path, module, symbol, API, or test.
3. Environment or version.
4. Approach, failed approach, or exclusion condition.
5. Lifecycle validity; retain superseded matches but show their current successors.
6. Recency only as a tie-breaker.

Return at most 15 candidate projections by default. Each projection contains the score, match reasons, no more than three bounded source snippets, and successor paths. Across selected source reports and `docs/researches/` material, read at most five items in full per retrieval occasion. Expand only for an unresolved mandatory criterion or material risk, and record why first.

## Legacy and scale behavior

- Index old reports without new routing fields as sparse entries and continue searching their full text. Do not bulk-rewrite them merely to populate the catalog.
- Fill new fields when an old report is substantively updated.
- Keep the catalog deletable and fully rebuildable from reports.
- Do not add semantic rollups, recursive summaries, shards, or a SQLite/full-text cache preemptively. Add a local rebuildable cache only after measured raw-search latency justifies it. Add lossless shards only after a single catalog becomes a measured bottleneck. Never replace or recursively summarize leaf reports.
