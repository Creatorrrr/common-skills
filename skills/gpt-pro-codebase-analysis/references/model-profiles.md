# Model profiles and official reference notes

Documentation review date: **2026-09-05**. These are checked configuration assumptions, not live model benchmarks. Registry: `scripts/model_profiles.py`. Review it again when changing a model or SDK; unknown models fail locally instead of inheriting guessed capabilities.

| Profile | Effective default reasoning | Effort | Context / output maximum |
|---|---|---|---|
| `gpt-5.6-sol` (alias `gpt-5.6`) | `mode=pro`, `effort=high` | standard: none/low/medium/high/xhigh/max; Pro: medium or higher | 1,050,000 / 128,000 |
| `gpt-6-astra` | `effort=high`; no `mode` field emitted | low/medium/high/xhigh/max | 1,050,000 / 128,000 |

The official Astra page does not establish support for GPT-5.6's Pro mode parameter. This package conservatively rejects explicit Astra `--reasoning-mode pro` and unsupported `none`, rather than asserting the provider can never add Pro. Astra `--reasoning-mode standard` is accepted as a neutral caller choice but omitted from the API payload; prefer `auto` for clarity. Astra non-auto reasoning.context is also unverified and rejected. Sol supports auto/current_turn/all_turns in this registry.

Default Sol/high is retained to separate implementation changes from model migration. This is not a claim that Sol is superior or cheaper for this workload. Compare the same frozen input and request contract across models, then evaluate effort/depth independently. Measure actual evidence correctness, missing important findings, unsupported claims, scope compliance, cost, latency and approval friction. No quantitative gain is claimed by v2.

## Official sources

- Latest-model migration and skill/instruction guidance: https://developers.openai.com/api/docs/guides/latest-model
- Astra capabilities: https://developers.openai.com/api/docs/models/gpt-6-astra
- Sol capabilities: https://developers.openai.com/api/docs/models/gpt-5.6-sol
- Reasoning modes/context: https://developers.openai.com/api/docs/guides/reasoning
- Token counting: https://developers.openai.com/api/docs/guides/token-counting
- Token count API schema, including prior response: https://developers.openai.com/api/reference/resources/responses/subresources/input_tokens/methods/count
- Supported file-search inputs: https://developers.openai.com/api/docs/guides/tools-file-search
- Files creation/expiry: https://developers.openai.com/api/reference/resources/files/methods/create
- Vector store creation/expiry: https://developers.openai.com/api/reference/resources/vector_stores/methods/create
- Data controls and distinct retention mechanisms: https://developers.openai.com/api/docs/guides/your-data
- Untrusted data and prompt injection: https://developers.openai.com/api/docs/guides/agent-builder-safety

## Migration interpretation

The latest-model guide favors explicit instruction priority, fewer unnecessary pauses, controlled output style and task-appropriate verification. This package implements those points by reusing actual existing approvals, separating local work from external transfer, rendering a shared user contract, distinguishing untrusted archive instructions, and leaving substantive verification pending after a completed response. It does not remove consequential-action permissions or pretend code-level assertions solve all prompt injection.
