# GPT-6 Astra: host compatibility notes

Read only for an explicitly selected Astra host or an API migration review. This skill remains `goal-planner`; installing it does not change the caller's model, role allocation, effort, tools, budget, or authorization. The portable Core contains the behavioral changes. Do not paste this entire file into every handoff.

## Verified target

Reviewed 2026-09-22 against the official **Using GPT-6 Astra** section of [Model guidance](https://developers.openai.com/api/docs/guides/latest-model?model=gpt-6-astra) and the [model page](https://developers.openai.com/api/docs/models/gpt-6-astra). Access details and the corrected prior review are in [MODEL_GUIDE_REVIEW.md](../MODEL_GUIDE_REVIEW.md). Old GPT-5.6 material is historical, not a fallback Astra configuration.

## API checks, only when API work is requested

| Item | Astra requirement or compatibility note |
|---|---|
| Model | Use `gpt-6-astra` only when the caller selected migration to it. |
| Reasoning | Supported: `low`, `medium`, `high`, `xhigh`, `max`; `none`/`minimal` are not supported. Migrate those settings to a tested `low` baseline; preserve other effective settings initially. |
| Tools | Astra tool calls require Responses; plain Chat Completions support does not imply tool-call support. |
| Parameters | Remove `temperature`, `top_p`, `top_logprobs`; also Chat Completions `logprobs` or Responses `include` entry `message.output_text.logprobs`. |
| Effort changes | `configuration_update` is documented for standard single-agent requests. Check current compatibility before use; do not assume it works in every host or multi-agent mode. |
| Cache migration | For migration from GPT-5.5 or earlier, the guide replaces `prompt_cache_retention` with `prompt_cache_options.ttl: "30m"`. Do not automatically rewrite existing working settings otherwise. |
| EU data residency | Astra's `fast` and `priority` service tiers are unavailable there. |

These are compatibility notes, not implemented settings or a claim that every combination was exercised. Recheck the live official documentation before an actual API migration. No model calls, keys, or paid services are added by this release.

## Optional runtime features

The guide introduces async tool calls (the application executes work and returns the matching `call_id`) and mid-turn steering over WebSockets. This skill supplies neither implementation.

For a host that actually supports pending work, the plan should associate task identity, source/goal version, owner, and reservation with the work it started. Distinguish pending, finished, invalidated, and cancellation-confirmed states. Keep valid completed work after a requirement change; inspect stale results before any adoption. Without the runtime feature, use ordinary sequential work and visible state. Never claim an unsupported cancellation, automatic resumption, or later delivery.

## Small migration evaluation

Use the existing role/tool/permission configuration and representative tasks. Evaluate the prompt changes before changing model effort or concurrency, then alter one factor at a time. Measure fulfilled criteria, missing evidence, unnecessary pauses, redundant tests, valid independent delegation, and requirement-update errors. Record cost/latency/tokens only when actually measured. Scenarios in [behavioral-astra.json](../tests/behavioral-astra.json) are unexecuted definitions, not evidence of model improvement.
