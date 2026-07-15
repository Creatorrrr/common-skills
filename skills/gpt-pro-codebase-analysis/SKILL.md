---
name: gpt-pro-codebase-analysis
description: Prepare and run a deep, evidence-based second-opinion analysis of a large repository through GPT-5.6 Sol Pro on the OpenAI Responses API or through a manual ChatGPT Web handoff. Use for architecture review, refactoring strategy, test-gap analysis, performance, workflow validity, missing implementation, migration risk, or deprecated and unused logic when a dedicated packaging and analysis pass is valuable.
---

# GPT Pro codebase analysis

Prepare a reproducible repository context, run exactly one user-selected external analysis path, and bring the report back into local evidence-based work.

## Non-negotiable rules

1. Follow the user's stated goal, scope, constraints, and output preference.
2. Require an explicit choice of `responses_api` or `chatgpt_web_assisted` before any external analysis or upload.
3. Never switch modes automatically after failure.
4. Read applicable `AGENTS.md` files before packaging.
5. Exclude Git-ignored and sensitive files exactly when possible.
6. Treat `full` as lossless. Stop instead of silently sending a partial direct context or partial retrieval store.
7. Ground every material conclusion in concrete repository files and distinguish confirmed facts, inference, and missing context.
8. Warn before upload when repository contents may be sensitive. Make retention behavior explicit for Responses API runs.
9. Treat external analysis as a second opinion. Verify important findings locally before planning or editing.

## Resolve bundled helpers

Resolve `scripts/...` relative to this `SKILL.md` first. Use an explicit absolute helper path when running from another repository.

If this checkout is unavailable, look for the installed or linked skill under locations such as:

- `~/.codex/common-skills/skills/gpt-pro-codebase-analysis/`
- `~/.claude/common-skills/skills/gpt-pro-codebase-analysis/`
- another global skill install pointing at this skill

Treat helpers as project-local only when the target repository intentionally vendored the skill.

## Workflow

### 1. Establish the request contract

Extract:

- primary objective
- explicit scope paths or subsystem names
- hard constraints and approval boundaries
- desired report style
- whether follow-up analysis is expected
- data-retention constraints

If scope is not explicit, infer a likely surface from the goal. Do not ask for details that can be discovered safely from the repository.

### 2. Confirm the external mode

Before packaging for an external run, ask the user to choose exactly one:

```text
Choose the analysis execution mode:
- responses_api: run GPT-5.6 Sol through the OpenAI Responses API
- chatgpt_web_assisted: prepare a manual ChatGPT Web upload and prompt

I will not switch modes automatically after a failure. Repository files will be
uploaded externally, so mention any retention restriction before the run.
```

Do not run either external path until the choice is explicit. Preparing local context is allowed only when it does not contradict the user's instruction to wait before any work.

### 3. Prepare repository context

Prefer Git enumeration:

```bash
git rev-parse --show-toplevel
git ls-files -co --exclude-standard
```

Run:

```bash
python <skill-dir>/scripts/prepare_analysis_context.py \
  --root . \
  --goal "<user goal>" \
  --mode auto
```

Add explicit scope when the user named paths:

```bash
python <skill-dir>/scripts/prepare_analysis_context.py \
  --root . \
  --goal "<user goal>" \
  --scope src/target tests/target docs/target.md \
  --mode auto
```

The active artifacts live under `.codex-analysis/context/`. A new prepare run archives the prior active run under `.codex-analysis/history/<run_id>/`.

### 4. Audit the prepared selection

Read and summarize `manifest.json` before any upload. Check:

- `mode_recommendation`
- selected and skipped file counts
- estimated tokens and bytes
- warnings
- explicit-scope matches and skips
- archive validation
- whether full or focused context is lossless

Stop if an explicit scope was skipped unexpectedly, an archive is incomplete, or the chosen execution path cannot carry the complete promised selection.

### 5. Run only the selected path

- For `responses_api`, read [references/responses-api.md](references/responses-api.md) completely before execution.
- For `chatgpt_web_assisted`, read [references/chatgpt-web-handoff.md](references/chatgpt-web-handoff.md) completely before preparing the handoff.
- For analysis goals, evidence rules, and report acceptance, read [references/analysis-method.md](references/analysis-method.md).

### 6. Accept or reject the result

Accept a report only when it:

- directly addresses the user's goal
- states inspected and uninspected coverage
- cites real paths and stable line or symbol references
- separates confirmed facts from uncertainty
- supports negative claims such as dead, unused, missing, or duplicate logic with caller, wiring, configuration, and test checks
- ranks findings by consequence
- proposes specific validation and next actions

Reject or narrow a report that is generic, overclaims repository-wide coverage, fabricates line numbers, or treats missing retrieval evidence as proof of absence.

## Packaging policy

Default to the complete text set when practical. Include source, tests, architecture docs, build and toolchain config, infrastructure, CI, runbooks, migrations, and applicable agent instructions.

Skip by default:

- binaries and media
- generated bundles and minified assets
- vendored dependencies
- caches and coverage outputs
- bulky snapshots and fixtures
- lockfiles unless dependency analysis is requested
- real secret-bearing files such as `.env`, `.npmrc`, private keys, and certificates

Explicit scope overrides low-signal skips for readable, non-sensitive text. Sensitive exclusions remain hard exclusions unless the user supplies a sanitized artifact and explicitly scopes it.

Use the manifest recommendation unless the user explicitly chose `full` or `focused`. Never silently change an explicit selection.

## Output contract

The helper prompts require:

1. Verdict
2. Scope and coverage
3. Prioritized findings
4. Unknowns and missing context
5. Recommended actions

Each finding must include severity, confidence, claim, evidence, impact, recommendation, and validation.

## Local follow-through

After a successful external analysis:

1. Save the response and run metadata.
2. Verify the highest-impact findings against current local code.
3. Reuse the report as input to planning, design, or implementation only within the user's requested scope.
4. Summarize the result in the user's language.
5. Do not edit code merely because the external report recommended it; implementation still requires user authorization or an implementation request already in scope.
