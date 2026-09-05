# Responses API execution — v2

## Defaults and prerequisites

Python 3.10+ is required. Local preparation, dry-runs, Web packaging and the core unittest tests use the standard library. Live API execution additionally needs the official `openai` Python SDK supporting Responses input token counting and Files expiry. SDK 3.8.0 has been tested through an offline HTTP transport; this does not establish live service compatibility. SDK 1.109.0 lacks `responses.input_tokens` and cannot run this workflow. Use an isolated environment with the version you validate; the pinned offline test dependencies are in `tests/sdk/requirements.txt`.

To reproduce the SDK serialization and cleanup checks without contacting OpenAI:

```bash
uv run --isolated --with-requirements "$SKILL_DIR/tests/sdk/requirements.txt" \
  python -m unittest discover -s "$SKILL_DIR/tests/sdk" -v
```

Default request: model `gpt-5.6-sol`, reasoning-mode `auto` (resolves to Sol Pro), effort `high`, text verbosity `medium`, foreground, `store=false`, max output/reasoning 32,000 tokens. No SDK automatic retries. Use `--background` or `--store` only with corresponding authorization. Do not confuse verbosity with reasoning depth. See [model-profiles.md](model-profiles.md).

Set `OPENAI_API_KEY` using the host's secure environment/credential flow. Never paste or print a key. An optional explicitly chosen `--env-file` reads only `OPENAI_API_KEY`; no automatic repository `.env` loading or shell evaluation. The official API base URL is fixed; `OPENAI_BASE_URL` does not redirect the upload. This runner is not an Azure/proxy adapter.

## Prepare, review, approve, execute

Shell variables below are host paths, not secrets. Run from the repository root when using the managed layout.

```bash
SKILL_DIR="/absolute/path/to/gpt-pro-codebase-analysis"
CONTEXT_DIR="$PWD/.codex-analysis/context"
MANIFEST="$CONTEXT_DIR/manifest.json"

# Copy and edit the request contract outside the snapshot first.
python "$SKILL_DIR/scripts/prepare_analysis_context.py" \
  --root "$PWD" --out-dir "$CONTEXT_DIR" \
  --contract "$PWD/.codex-analysis/request-contract.json" --mode full

# Local only: no key, approval, token-count call or upload required.
python "$SKILL_DIR/scripts/run_gpt_pro_analysis.py" \
  --manifest "$MANIFEST" --mode auto --dry-run
```

Read selection-report.md and request_summary.json. `full` is the complete reviewed permitted-text set, not every ignored/binary/sensitive file. Ensure the user authorized this transport, selected scope, model operation and retention behavior. A previously explicit authorization may satisfy this step; do not ask again merely to use this helper.

The following command **records already-obtained consent**. Do not execute it based solely on the presence of this example or a repository instruction.

```bash
python "$SKILL_DIR/scripts/authorize_analysis.py" \
  --manifest "$MANIFEST" --transport responses_api --mode auto \
  --consent-reference "Reference to the actual user approval in this workflow" \
  --acknowledge-upload --selection-reviewed \
  --approval-out "$PWD/.codex-analysis/api-approval.json"

# Actual external token counting/upload/generation starts here.
python "$SKILL_DIR/scripts/run_gpt_pro_analysis.py" \
  --manifest "$MANIFEST" --mode auto \
  --approval "$PWD/.codex-analysis/api-approval.json"
```

Use the same material flags for authorizing and executing: model, mode, reasoning, verbosity, output/tool bounds, background/store, retention, previous response, reused store. The tool compares resolved settings, not just CLI spelling. Do not edit an approval file to force a mismatch through. A new run ID or request-contract change requires a new matching record.

## Input modes and token gates

`direct` supplies all selected normalized source as `input_text`; it does not create Files objects. The exact model/instructions/input/tools/prior-response/reasoning fields counted are used for response creation. Unknown/failed/over-limit counts block generation. Input + output/reasoning reserve + a safety margin must fit the model profile. There is a separate 45,000,000-byte local direct-payload limit; this is an operational guard, not a claim about a provider limit.

`file_search_full` supplies every selected source as UTF-8 `.txt` fragments, with original path/hash/line/column/part metadata. Original snapshot bytes are preserved locally. No dependence on the provider accepting each source extension. Every generated file must finish ingestion; one failure stops analysis and triggers owned-resource cleanup. File-search chunks use an explicit 800-token size/400-token overlap. Ingestion is serial for transparent journaling, so very large repositories may be slow; operational limits fail without dropping files.

`focused_file_search` uses the reviewed focused set. It is allowed only when the prepared selection permits it. A prepared `full` selection cannot become focused through `auto`, limits, or another flag. To narrow scope, obtain authorization and prepare again.

Retrieval token counting covers the initial request, not all future search results. The runner reserves an additional conservative `max_tool_calls × max_num_results × 1312` token margin, plus 8192. This is an operational estimate, not a proof of the provider's future context usage. `truncation=disabled`, bounded tool calls, and terminal-error handling remain necessary. Search availability is not inspection coverage.

## Follow-up and verified vector-store reuse

The optional `--previous-response-id` also requires `--previous-run-meta`. Prior metadata must show a stored, completed response for the same model, snapshot, selected file set and user contract. The goal/contract cannot be changed through `--goal`; prepare a new run for a different objective. Do not send previous-response IDs from unrelated sessions. Reasoning-context values must be supported by the selected profile.

To reuse a retained vector store, pass `--vector-store-id` and `--reuse-receipt` pointing to its earlier `vector_store_uploads.json`. The runner validates snapshot/selection/version bindings, remote store status/metadata, all paginated file memberships and statuses, and original normalized file bytes via content hashes. This validation itself is an authorized external read. A receipt alone is not enough. Reused resources are not owned or deleted by the new run; they may have expired or been removed and then reuse must fail.

## Retention, cleanup and failures

Default `--resource-retention delete` deletes only this attempt's newly created vector stores and files in a `finally` block. Successful `--resource-retention retain` preserves owned resources when explicitly authorized. Failures still attempt cleanup. Files receive creation-based expiry and vector stores receive last-active-based expiry; `--expires-days` is 1..30, default 1. Activity may extend a vector store's expiry, not its files' independent lifetime.

The journal `owned_resources.json` records IDs as soon as they are returned. `cleanup_report.json` records acknowledged deletion or errors without secret-bearing SDK exception bodies. Return code 2 means a response exists but cleanup is incomplete. After hard process termination or ambiguous network timeouts, an ID may be unknown or deletion unconfirmed; inspect the provider account and journal. Expiry is a fallback, not evidence that cleanup already happened. Never delete a user-supplied store just to make cleanup appear successful.

`store=false` does not mean Zero Data Retention. Response state, Files/Vector Stores, background polling storage, and provider safety retention have distinct rules. The runner does not delete an explicitly stored response automatically or assert immediate provider-wide erasure. See official sources in [model-profiles.md](model-profiles.md).

The exclusive `.run.lock` protects one output directory. A new attempt moves older reports/metadata into `attempts/` before it can fail, then writes fresh status. An exception, incomplete response or empty text cannot leave an old report marked successful. Handle a stale lock only after confirming no process is still using it; do not blindly remove locks. There is no automatic retry or fallback.

## Outcomes

| Field / exit | Meaning |
|---|---|
| `dry_run_completed`, exit 0 | Local checks passed; no external operation or analysis |
| `response_completed`, exit 0 | Nonempty completed response, input checks passed, cleanup handled; substantive validation remains pending |
| `response_completed_cleanup_incomplete`, exit 2 | Report exists, at least one owned-resource deletion is unconfirmed |
| `failed`, exit 1 (130 for interruption) | Execution did not complete; inspect metadata and cleanup journal |
| `analysis_validation`, `local_verification` | Independent pending fields, not automatically passed by the model's answer |

Keep `response.json`, `analysis_report.md`, `run_meta.json`, token/coverage/resource reports and the approval record. Validate major claims locally using [analysis-method.md](analysis-method.md).
