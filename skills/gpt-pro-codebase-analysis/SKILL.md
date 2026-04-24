---
name: gpt-pro-codebase-analysis
description: Use this skill when the user wants a deep second-opinion analysis of a repository, either through the OpenAI Responses API or through a ChatGPT Web handoff. Use it for architecture review, refactoring strategy, test-gap analysis, performance, workflow or use-case validity, missing implementation, or deprecated and unused logic when the repository is too large to inspect comfortably in-session.
---

# GPT Pro codebase analysis

This skill prepares repository context, chooses between a direct API run and a ChatGPT Web handoff, and returns an evidence-based analysis report that can drive follow-up design work.

## Core principles

1. The user's stated goal, scope, and direction override every default in this skill.
2. Explicit mode confirmation is mandatory before any external execution step.
3. Never auto-switch between `responses_api` and `chatgpt_web_assisted`.
4. Prefer the most complete context that is still practical inside the chosen mode.
5. Exclude Git-ignored files exactly when possible.
6. For `responses_api`, treat archives as transport artifacts and analyze text shards or uploaded raw files.
7. For `chatgpt_web_assisted`, browser automation is prohibited by default. Prepare only the upload zip, prompt, and next-step instructions unless the current user request explicitly asks to use `Computer Use` for the handoff.
8. Keep every conclusion grounded in concrete files.
9. Distinguish confirmed findings from inference or uncertainty.
10. If external upload could be sensitive, surface a brief privacy note before proceeding.

## Script location resolution

When this skill tells you to run a bundled helper like `scripts/prepare_analysis_context.py` or `scripts/run_gpt_pro_analysis.py`, do not assume that `scripts/` exists in the active project.

Resolve helper paths in this order:

1. Start from the directory that contains this `SKILL.md`. Treat `scripts/...` as relative to the skill directory first.
2. If the active workspace does not contain the skill files, check the tool's global skill install area or linked checkout, for example `~/.codex/common-skills/skills/gpt-pro-codebase-analysis/`, `~/.claude/common-skills/skills/gpt-pro-codebase-analysis/`, or another global install location that points at this skill.
3. Only treat `scripts/...` as project-local when the user has intentionally vendored this skill into the repository.

When executing a helper, prefer an explicit path derived from the resolved skill directory instead of assuming the current shell is already inside that directory.

## Mandatory mode confirmation

Before any external run, ask the user to choose exactly one execution mode:

- `responses_api`
- `chatgpt_web_assisted`

Use wording like this when needed:

```text
Please choose the analysis execution mode.
- responses_api: run the analysis directly through the OpenAI Responses API
- chatgpt_web_assisted: I will prepare the upload archive and prompt, then the user runs it manually in ChatGPT Web unless the current request explicitly asks me to use Computer Use for the handoff
For ChatGPT Web Pro handoff, use Extended(확장) reasoning unless you explicitly request a different reasoning level. The analysis can take more than 30 minutes.
I will not execute anything before an explicit choice. If one mode fails, I will not automatically switch to the other.
```

Rules:

- Do not assume a default mode when the user has not chosen one.
- Do not continue with the other mode after a failure unless the user explicitly instructs that change.
- Do not silently widen or narrow the scope after a failed external run. Ask or continue only within the already chosen mode and scope.

## Use this skill when

- The user explicitly wants a deeper external analysis pass.
- The repo or subsystem is large enough that Codex would benefit from a dedicated packaging step.
- The user wants a design review before implementation.
- The user wants one or more of these analysis lenses:
  - structural refactoring
  - test inventory, gap analysis, and reinforcement
  - performance and scalability review
  - use-case or workflow validity
  - missing or stubbed implementation detection
  - deprecated, dead, duplicate, or suspiciously unused logic
  - risk review before a migration or rewrite

## Do not use this skill when

- The task is small and can be answered reliably from a few files already in context.
- The user explicitly does not want external analysis.
- The task is pure local editing with no need for a second-opinion architecture pass.

## Required first pass

Before packaging or calling anything external:

1. Read `AGENTS.md` files that apply to the current directory.
2. Read the user's request carefully and extract:
   - primary objective
   - explicit scope paths or subsystem names
   - hard constraints
   - desired output style
3. If the user provided no scope, infer the likely analysis surface from the goal.
4. Prefer exact repo enumeration with Git:

```bash
git rev-parse --show-toplevel
git ls-files -co --exclude-standard
```

Use `git ls-files -co --exclude-standard` as the canonical file list whenever possible. It includes tracked and untracked files while excluding `.gitignore`, `.git/info/exclude`, and global Git ignores.

## Context packaging policy

### 1) Full-first strategy

Default to a full-repository text analysis set, not a hand-picked subset, when the size is reasonable.

The packaging script already implements this behavior:

```bash
python scripts/prepare_analysis_context.py --root . --goal "<user goal>" --mode auto
```

That script writes artifacts under `.codex-analysis/context/` by default.

The layout now keeps a single clean active run under `.codex-analysis/` and archives the previous active run under `.codex-analysis/history/<run_id>/` whenever a new prepare run starts.

For ChatGPT Web handoffs, distinguish immutable submitted identity from relocated artifact paths:

- `prepared_handoff_identity`, `prompt_handoff_identity_block`, and `prompt_handoff_identity_sha256` describe the exact handoff identity that was prepared for submission and must not be rewritten after archival.
- `current_artifact_paths` describes where local artifacts live after active-run archival or when using an archived manifest.
- When verifying a ChatGPT answer, trust the immutable prepared identity over relocated local paths.

### 2) File inclusion defaults

Include these by default if they are text and not Git-ignored:

- source code
- tests
- root and module READMEs
- architecture and ADR documents
- build and toolchain config
- infra and deployment config
- CI workflows
- `AGENTS.md`, `PLANS.md`, migration notes, runbooks

### 3) Low-signal defaults

Skip these by default unless the user explicitly asks for them:

- binaries and images
- vendored dependencies
- generated bundles and minified assets
- coverage outputs
- cache folders
- snapshots and bulky fixtures
- lockfiles, unless dependency analysis is part of the request

### 4) Archive policy

Produce archives for reproducibility and transport, but do not assume the model should analyze an archive directly unless the user chose the manual ChatGPT Web handoff.

Use the archive to preserve the selected file set, then analyze either:

- importance-ranked raw files attached as `input_file` items for direct Responses API runs, or
- uploaded raw files through vector-store + `file_search`

## Selection policy inside a chosen mode

The packaging script emits a recommended mode. Follow it unless the user gave a stronger instruction.

### Direct full-context selection

Use direct full-context selection when the prepared full-context bundle is comfortably within the direct budget.

Default guidance:

- preferred under about 180k estimated input tokens
- allowed with warning between about 180k and 272k estimated input tokens
- only use above 272k when the user explicitly wants a full direct pass and accepts the cost and latency tradeoff

When using direct mode, attach the repository map and the highest-signal raw files as `input_file` items.
Preserve the preparation script's importance ordering when choosing files and stay within the combined request-size limit.

### Full retrieval selection

Use full retrieval selection when the repo is too large for an efficient direct pass but still practical to upload as a full knowledge base.

Typical trigger:

- estimated direct input is above the long-context warning band
- full file set is still text-heavy and operationally manageable

In this mode:

1. upload the raw selected files into a vector store
2. call the model with `file_search`
3. seed the model with the repo map and the user's exact goal

### Focused retrieval selection

Use focused retrieval selection when full-repo upload would be too expensive, too slow, or too diffuse.

Typical trigger:

- the repo is extremely large
- the user named a specific subsystem
- the target problem is narrow
- the full set would drown the model in low-value context

Focused mode should still be broad enough to preserve the relevant workflow. Always include:

- target paths
- entrypoints and wiring for the target workflow
- relevant configs
- surrounding docs
- nearby tests
- files with TODO/FIXME/DEPRECATED/LEGACY markers related to the target

## Warning policy

Surface a warning before the external step when one or more of these are true:

- estimated input tokens exceed the direct-warning threshold
- estimated input tokens exceed the long-context pricing threshold
- direct file-input payload would exceed the combined request-size limit
- the repo appears sensitive and external upload has not been acknowledged yet
- `background=true` or `store=true` would conflict with the user's data-retention requirements
- the selected ChatGPT Web upload archive is very large or near the per-file upload cap

Do not block automatically unless the chosen execution path cannot work. Warn, then proceed if the user's direction is clear.

## Execution mode A: `responses_api`

Use the helper script:

```bash
python scripts/run_gpt_pro_analysis.py \
  --manifest .codex-analysis/context/manifest.json \
  --goal "<user goal>" \
  --env-file .env \
  --mode auto
```

Before constructing the OpenAI client, this helper reads the specified `.env` file. If `OPENAI_API_KEY` is missing from both `.env` and the current environment, Codex should ask the user to set it and stop instead of attempting the API call.

For background runs on the default Pro model, the helper uses adaptive polling instead of a short fixed interval:

- under 30 minutes elapsed: sleep 10 minutes between polls
- 30 to under 40 minutes elapsed: sleep 5 minutes between polls
- 40 to under 50 minutes elapsed: sleep 3 minutes between polls
- 50 minutes and beyond: sleep 1 minute between polls

If the Responses API returns a terminal failure status, save `response.json` and a failed `run_meta.json`, do not write `analysis_report.md` as if it were a successful report, exit non-zero, and do not retry automatically. Pro requests are expensive, so failure handling should be explicit and user-driven.

### Model defaults

- model: `gpt-5.5-pro`
- endpoint family: Responses API
- reasoning effort:
  - `high` by default
  - `xhigh` for highly ambiguous cross-cutting analysis, large architectural redesigns, or deep legacy cleanup
  - `medium` for focused follow-up questions
- verbosity: `high` for detailed analysis reports
- `background=true` by default for pro-level runs
- `store=true` when follow-up design iteration is expected and the user has no retention objection
- do not auto-retry failed pro API runs

### Follow-up iteration

When analysis succeeds:

1. Save the response id and report artifacts.
2. Reuse `previous_response_id` for follow-up design questions when appropriate.
3. Feed the findings back into local planning or implementation work.
4. Do not blindly trust the external analysis; verify against code before editing.

## Execution mode B: `chatgpt_web_assisted`

This mode prepares a ChatGPT Web handoff package. It is manual by default. Computer Use is a narrow opt-in exception, not a fallback.

By default, it must never:

- open a browser on the user's behalf
- use Playwright or other browser automation
- click through ChatGPT Web UI
- auto-upload files
- auto-submit prompts
- scrape ChatGPT output from the page

It should only prepare a handoff package for the user. Computer Use is allowed only when both of these are true:

- The current user request explicitly asks to use `Computer Use` or `[@Computer Use](plugin://computer-use@openai-bundled)` for the ChatGPT Web handoff.
- The Computer Use plugin/tool is available in the current session.

Computer Use availability alone is never permission to automate ChatGPT Web. Do not infer permission from the selected `chatgpt_web_assisted` mode, from a prior run, or from the plugin being available.

For any ChatGPT Web Pro handoff, use Extended(확장) reasoning unless the user explicitly names a different reasoning level. Before the handoff or submission, state that the analysis can take more than 30 minutes.

When those conditions are true, use Computer Use to complete the ChatGPT Web handoff. Follow this procedure:

1. Open a new browser window for `chatgpt.com`; do not reuse an existing ChatGPT/browser window or tab from the user's current workspace.
2. Record the current handoff identity before submission: handoff directory, `request_meta.json` `run_id`, canonical `upload-source.zip` path, run-id-named accessible upload copy path, archive SHA-256, `chatgpt-prompt.txt` path, the prompt's `Handoff identity` block, `prompt_handoff_identity_sha256`, and the current user goal. Treat `prepared_handoff_identity` and `prompt_handoff_identity_sha256` as immutable submitted identity; use `current_artifact_paths` only to find relocated local files.
3. If ChatGPT Web requires authentication, pause and ask the user to authenticate in that new browser window; continue only after the user confirms authentication is complete.
4. Use the run-id-named accessible upload copy recorded in `request_meta.json` as `accessible_upload_copy_path`. The helper creates this copy in an easy-to-reach location such as `~/Downloads/upload-source-<run_id>.zip`; if the metadata is missing, copy the canonical `upload-source.zip` to `~/Downloads` or `~/Desktop` with that filename pattern and verify the SHA-256 still matches.
5. Attach that run-id-named zip through ChatGPT's attach-file button and the OS file picker.
6. Select Pro with Extended(확장) reasoning unless the user explicitly requested another reasoning level.
7. Paste the contents of `chatgpt-prompt.txt`, submit the analysis request, and wait for completion.
8. Before collecting any result, verify that the visible ChatGPT conversation is the one requested by this current session. Match it against the recorded immutable handoff identity, including `run_id`, user goal, `prompt_handoff_identity_sha256`, the prompt's `Handoff identity` block, uploaded archive presence, archive SHA-256 when visible or inferable, prompt content, and the run-id-named attached file when visible or otherwise inferable. Do not rely on relocated paths or the displayed upload filename alone because ChatGPT may rename duplicate uploads and local artifacts may move into history. If multiple ChatGPT tabs/windows are running analyses, do not take the most recent or completed answer by position alone.
9. If the current-session identity cannot be verified with high confidence, do not use the browser result. Ask the user to identify the correct tab or rerun the handoff in a fresh window.
10. Only after verification, collect the final answer and then continue local planning or implementation from that answer.

If Computer Use is unavailable, blocked, or unreliable for the handoff, keep the default manual-only rule: return the generated file paths plus any partial browser state already reached, and do not use Playwright, shell browser automation, scraping, or any other browser-control substitute.

Use the helper script:

```bash
python scripts/run_chatgpt_web_assisted.py \
  --manifest .codex-analysis/context/manifest.json \
  --goal "<user goal>" \
  --selection-mode auto
```

### What the helper generates

Under `.codex-analysis/chatgpt-web/` by default, generate for the active run. If the manifest points at `.codex-analysis/history/<run_id>/context/manifest.json`, write the handoff artifacts beside that archived run instead:

- `handoff/upload-source.zip`
- `handoff/chatgpt-prompt.txt`
- `handoff/next-steps.md`
- `handoff/return-to-agent-template.md`
- `request_meta.json`

The helper also copies the upload archive to an easy-to-select location, normally `~/Downloads/upload-source-<run_id>.zip`, and records that path as `accessible_upload_copy_path` in `request_meta.json`.

`request_meta.json` must preserve both identity and current local paths:

- immutable fields: `prepared_handoff_identity`, `prompt_handoff_identity_block`, `prompt_handoff_identity_sha256`
- mutable local path field: `current_artifact_paths`
- lifecycle field: `handoff_lifecycle: "prepared"`

### How this mode works

1. Codex prepares the upload zip and prompt.
2. If the current user request did not explicitly request Computer Use, return the handoff paths and tell the user to run ChatGPT Web Pro with Extended(확장) reasoning unless they want a different level.
3. If the current user request explicitly requested Computer Use and it is available, use it to operate ChatGPT Web end to end in a new browser window, selecting Extended(확장) reasoning and attaching the run-id-named accessible upload copy through ChatGPT's attach-file button and the OS file picker.
4. If authentication is required during Computer Use, ask the user to authenticate and wait for confirmation before continuing.
5. Expect the analysis to take more than 30 minutes when using Pro Extended reasoning.
6. Before reading or copying a completed ChatGPT answer, verify that it belongs to the current session's handoff by checking immutable submitted identity: `request_meta.json` `run_id`, user goal, `prompt_handoff_identity_sha256`, the prompt's `Handoff identity` block, uploaded archive presence, archive SHA-256 when visible or inferable, and run-id-named attached file. Use `current_artifact_paths` only to locate local files. If this cannot be confirmed, stop and ask the user instead of importing a possibly unrelated result.
7. After ChatGPT finishes and the current-session match is verified, use the returned answer as input to local design, implementation, or verification work.

### Rules for the ChatGPT Web path

- Do not programmatically interact with `chatgpt.com` unless the current user request explicitly opted into the Computer Use exception above.
- Do not scrape or auto-ingest the answer from the browser unless Computer Use is the active requested handoff mechanism.
- Do not use Playwright, shell browser automation, or another browser-control tool as a fallback for Computer Use.
- Do not treat Computer Use availability as authorization; it only matters after an explicit user opt-in.
- For Computer Use uploads, use the run-id-named accessible upload copy from `request_meta.json` and attach it with ChatGPT's attach-file button plus the OS file picker.
- For ChatGPT Web Pro, use Extended(확장) reasoning by default and account for analysis time longer than 30 minutes.
- When several Computer Use sessions or ChatGPT tabs are active, never collect an analysis result until the tab is verified as the current session's request. Compare the visible chat against the immutable prepared handoff metadata, `prompt_handoff_identity_sha256`, prompt `Handoff identity` block, upload SHA, attached filename, and goal; if ambiguous, ask the user rather than guessing.
- If Computer Use fails after the package is prepared or after partial browser setup, stop browser automation and return the handoff paths plus the current partial state. Do not use Playwright or another browser automation fallback.
- If ChatGPT displays the uploaded archive with a renamed filename, verify by `run_id`, prompt identity, goal, and archive presence instead of filename alone.
- Do not automatically switch to `responses_api` if upload fails or the archive is too large.
- If the user wants to switch modes after a failure, require an explicit new instruction.
- If ChatGPT Web says it cannot inspect the archive reliably, bring that answer back and decide the next step only after the user confirms.

### Selection rules in manual web mode

- Keep the same full-first behavior when the full archive is still practical.
- If `--selection-mode auto`, prefer the full archive unless:
  - the preparation step strongly recommends focused analysis, or
  - the full archive is too large to upload as a single ChatGPT file
- If the user explicitly requested `full`, do not silently switch to `focused`.
- If the user explicitly requested `focused`, do not silently switch to `full`.

## Default analysis methodology

If the user did not specify a framework, use this order.

### Phase 1: Establish a reliable map

Produce a compact map of:

- repo purpose
- major modules and responsibilities
- main entrypoints
- important runtime boundaries: UI, transport, domain, persistence, jobs, external integrations
- build/test/deploy surface

### Phase 2: Trace the most relevant workflows

Follow at least one concrete end-to-end path that matters for the user's goal.

Examples:

- request -> validation -> domain logic -> persistence -> side effects -> response
- UI event -> state transition -> API call -> backend effect -> user-visible outcome
- job trigger -> scheduler -> worker -> retry/failure path

### Phase 3: Evaluate by the default rubric

Unless the user set a different priority order, check these lenses in this order:

1. correctness and failure handling
2. design validity against use-cases and workflows
3. missing implementation, stubs, TODOs, and hidden assumptions
4. test quality, coverage shape, and missing cases
5. structural refactoring opportunities
6. performance and scalability risks
7. deprecated, dead, duplicate, or suspiciously unused logic
8. security and secrets hygiene where relevant
9. observability, diagnosability, and rollout risk
10. documentation or configuration drift

### Detailed review lenses

#### A. Structural refactoring

Look for:

- mixed responsibilities
- unclear ownership boundaries
- tight coupling across layers
- duplicate logic
- large stateful modules with poor seams
- naming or file layout that obscures actual ownership
- feature logic spread across too many places

#### B. Tests

Check:

- what behaviors are already protected
- which workflows lack tests entirely
- missing edge cases
- failure-path coverage
- contract and integration-test gaps
- flakiness risk from time, network, ordering, or global state
- whether the current test layout matches the actual architecture

#### C. Performance and scalability

Check:

- repeated work
- avoidable I/O
- N+1 patterns
- inefficient loops or quadratic behavior
- blocking calls on hot paths
- unbounded memory growth
- lack of caching or excessive caching
- serialization overhead
- UI over-rendering or unnecessary recomputation

#### D. Use-case and workflow validity

Check whether the implementation shape matches the business workflow:

- are invariants enforced in the right layer?
- do state transitions reflect the real user journey?
- is the design robust to retries, partial failure, or duplication?
- are async boundaries and side effects explicit enough?
- does the code support the likely next feature without awkward branching?

#### E. Missing implementation

Check for:

- TODO/FIXME/HACK/WIP markers
- stubbed branches
- placeholder values
- not-yet-wired commands or handlers
- config that implies a feature exists when it does not
- dead-end UI or API surfaces

#### F. Deprecated or unused logic

Check for:

- legacy adapters still referenced indirectly
- unreachable branches
- obsolete flags
- duplicate codepaths left after migrations
- tests covering behavior that no longer matters
- compatibility layers that no longer serve active callers

#### G. Additional advanced lenses

Use these when relevant:

- data model and schema consistency
- API contract stability
- security posture
- authorization boundaries
- migration readiness
- rollback strategy
- release and operational risk
- dependency hygiene
- documentation drift

## Output requirements for the external model

Ask the model for a report with this structure unless the user asked for something else:

1. Scope and assumptions
2. Short system map
3. Top findings (prioritized)
4. Evidence for each finding
5. Confirmed facts vs inference
6. Test-gap recommendations
7. Refactoring or redesign recommendations
8. Quick wins vs deeper changes
9. Suggested next design steps

## Quality bar for accepting the analysis

Do not treat the result as high quality unless it:

- clearly respects the user's stated goal
- cites real code locations
- separates fact from inference
- covers both architecture and execution details where needed
- includes actionable next steps instead of generic advice

## Example commands

### Broad architecture + test-gap pass with `responses_api`

```bash
python scripts/prepare_analysis_context.py \
  --root . \
  --goal "Analyze the overall system with a focus on structural refactoring and strengthening test coverage" \
  --mode auto

python scripts/run_gpt_pro_analysis.py \
  --manifest .codex-analysis/context/manifest.json \
  --goal "Analyze the overall system with a focus on structural refactoring and strengthening test coverage" \
  --env-file .env \
  --mode auto
```

### Focused subsystem pass with `responses_api`

```bash
python scripts/prepare_analysis_context.py \
  --root . \
  --goal "Review the checkout workflow for design validity and missing implementation" \
  --scope src/checkout tests/checkout docs/checkout.md \
  --mode auto

python scripts/run_gpt_pro_analysis.py \
  --manifest .codex-analysis/context/manifest.json \
  --goal "Review the checkout workflow for design validity and missing implementation" \
  --env-file .env \
  --mode auto
```

### Manual ChatGPT Web handoff

```bash
python scripts/prepare_analysis_context.py \
  --root . \
  --goal "Analyze the system to identify deprecated logic and unused flows" \
  --mode auto

python scripts/run_chatgpt_web_assisted.py \
  --manifest .codex-analysis/context/manifest.json \
  --goal "Analyze the system to identify deprecated logic and unused flows" \
  --selection-mode auto
```

Then hand the generated files to the user instead of trying to operate ChatGPT Web.

### Archived follow-up on an older prepared run

```bash
python scripts/run_chatgpt_web_assisted.py \
  --manifest .codex-analysis/history/<run_id>/context/manifest.json \
  --goal "Continue the older analysis run using its archived context" \
  --selection-mode auto
```

This writes the handoff package under `.codex-analysis/history/<run_id>/chatgpt-web/` instead of touching the current active run.

## Notes for Codex

- Prefer reading and summarizing the generated `manifest.json` before any external step.
- Require explicit mode confirmation before running either external path.
- Before `responses_api`, let the helper read `.env`. If `OPENAI_API_KEY` is still missing, ask the user to set it in `.env` or the current environment before retrying.
- If `chatgpt_web_assisted` was chosen, return the generated upload zip, prompt, accessible upload copy, and next-step file paths to the user, and state that ChatGPT Web Pro should use Extended(확장) reasoning by default and may take more than 30 minutes. Do this unless the current user request explicitly requested the Computer Use handoff and Computer Use is available. In that case, open ChatGPT Web in a new browser window, select Extended(확장) reasoning unless directed otherwise, attach the run-id-named accessible upload copy through ChatGPT's attach-file button and the OS file picker, and submit the handoff; if authentication is required, ask the user to authenticate and continue after confirmation. Before collecting the answer, verify that the ChatGPT tab belongs to the current handoff by checking the current goal, immutable `prepared_handoff_identity`, `prompt_handoff_identity_sha256`, uploaded archive presence, upload SHA, attached filename, and prompt `Handoff identity` block; if uncertain, do not import the result.
- If the external run returns a strong report, summarize the result back to the user in the same language they used.
- After the analysis, switch back to local repo work and use the report as an input to planning, design, or implementation.
