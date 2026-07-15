# Responses API execution

## Contents

1. Request defaults
2. Preflight
3. Initial run
4. Selection modes
5. Follow-up reasoning
6. Failure and retention rules
7. Artifacts and local verification

## Request defaults

Use GPT-5.6 Pro as an execution mode, not as a separate model slug:

```json
{
  "model": "gpt-5.6-sol",
  "reasoning": {
    "mode": "pro",
    "effort": "high"
  },
  "text": {
    "verbosity": "high"
  }
}
```

Defaults:

- model: `gpt-5.6-sol`
- reasoning mode: `pro`
- baseline effort: `high`
- verbosity: `high`
- background: enabled for long Pro runs
- store: enabled only when the user has no retention objection and stateful follow-up is useful
- no automatic retry after a terminal failure

Preserve `high` for the first migration baseline, then compare `medium` on representative tasks. Use `xhigh` or `max` only when evaluation shows a material quality gain.

## Preflight

Before constructing the OpenAI client:

1. Read the prepared manifest.
2. Confirm the user selected `responses_api`.
3. State that selected repository text will be uploaded to OpenAI.
4. Resolve whether `store=true` is allowed.
5. Let the helper load the specified `.env` file.
6. If `OPENAI_API_KEY` is missing from the environment and `.env`, stop and ask the user to set it.

Do not print, inspect, or expose the API key.

## Initial run

Run:

```bash
python <skill-dir>/scripts/run_gpt_pro_analysis.py \
  --manifest .codex-analysis/context/manifest.json \
  --goal "<user goal>" \
  --env-file .env \
  --mode auto \
  --reasoning-mode pro \
  --reasoning-effort high
```

If persistent response storage is not allowed, add `--no-store`. Background requests with `store=false` still require temporary response storage for asynchronous polling, so surface that behavior when the user's policy prohibits even temporary retention.

For a standard-mode comparison run, use `--reasoning-mode standard`. Do not call a standard run “Pro.”

## Selection modes

### Direct

Direct mode attaches:

- repository map
- selection audit
- lossless prepared context shards

The helper must stop if every required shard cannot fit. It must not fall back to a subset of raw files while presenting the run as full context.

### Full retrieval

`file_search_full` uploads every selected raw file to a vector store. Continue only after every uploaded file reports `completed` ingestion.

Seed the model with the repository map. Require retrieval of concrete entrypoints, callers or wiring, configuration, and relevant tests before major claims.

### Focused retrieval

`focused_file_search` is appropriate when the repository is operationally too large or the user explicitly named a narrow subsystem. The focused set must still include workflow entrypoints, wiring, configs, nearby docs, tests, and goal-related legacy markers.

Do not describe a focused result as a repository-wide audit.

## Follow-up reasoning

Reuse `previous_response_id` only when continuing the same prepared context or a clearly related design question.

Reasoning context choices:

- `auto`: model default
- `current_turn`: earlier reasoning is stale or the objective changed
- `all_turns`: the goal, assumptions, and priorities remain stable

Example:

```bash
python <skill-dir>/scripts/run_gpt_pro_analysis.py \
  --manifest .codex-analysis/context/manifest.json \
  --goal "Turn the accepted findings into a staged redesign" \
  --previous-response-id <response_id> \
  --reasoning-context all_turns \
  --mode auto
```

Do not use `all_turns` merely because a previous response id exists.

## Failure and retention rules

Treat the run as successful only when:

- response status is `completed`
- `output_text` is non-empty
- promised context selection was complete
- vector-store ingestion was complete when retrieval was used

For any other terminal outcome:

1. Save `response.json` when a response exists.
2. Save `run_meta.json` with `terminal_failure=true` and a failure reason.
3. Remove any stale `analysis_report.md`.
4. Exit non-zero.
5. Do not retry or switch transports automatically.

Do not serialize raw response JSON into `analysis_report.md` as a success fallback.

## Artifacts and local verification

Successful runs write under `.codex-analysis/gpt-pro/` or beside an archived manifest:

- `analysis_report.md`
- `response.json`
- `run_meta.json`
- token and upload metadata where applicable

Read the report, then inspect the cited local paths. Confirm high-severity claims, negative claims, and proposed ownership changes before using them in a plan or implementation.
