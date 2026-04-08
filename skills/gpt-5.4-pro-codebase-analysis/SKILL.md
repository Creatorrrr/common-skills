---
name: gpt-5.4-pro-codebase-analysis
description: Use this skill when the user wants a deep second-opinion analysis of a repository with gpt-5.4-pro, either through the OpenAI Responses API or through a fully manual ChatGPT Web handoff. Use it for architecture review, refactoring strategy, test-gap analysis, performance, workflow or use-case validity, missing implementation, or deprecated and unused logic when the repository is too large to inspect comfortably in-session.
---

# GPT-5.4 Pro codebase analysis

This skill prepares repository context, chooses between a direct API run and a fully manual ChatGPT Web handoff, and returns an evidence-based analysis report that can drive follow-up design work.

## Core principles

1. The user's stated goal, scope, and direction override every default in this skill.
2. Explicit mode confirmation is mandatory before any external execution step.
3. Never auto-switch between `responses_api` and `chatgpt_web_assisted`.
4. Prefer the most complete context that is still practical inside the chosen mode.
5. Exclude Git-ignored files exactly when possible.
6. For `responses_api`, treat archives as transport artifacts and analyze text shards or uploaded raw files.
7. For `chatgpt_web_assisted`, do not automate the browser; prepare only the upload zip, prompt, and next-step instructions.
8. Keep every conclusion grounded in concrete files.
9. Distinguish confirmed findings from inference or uncertainty.
10. If external upload could be sensitive, surface a brief privacy note before proceeding.

## Script location resolution

When this skill tells you to run a bundled helper like `scripts/prepare_analysis_context.py` or `scripts/run_gpt54pro_analysis.py`, do not assume that `scripts/` exists in the active project.

Resolve helper paths in this order:

1. Start from the directory that contains this `SKILL.md`. Treat `scripts/...` as relative to the skill directory first.
2. If the active workspace does not contain the skill files, check the tool's global skill install area or linked checkout, for example `~/.codex/common-skills/skills/gpt-5.4-pro-codebase-analysis/`, `~/.claude/common-skills/skills/gpt-5.4-pro-codebase-analysis/`, or another global install location that points at this skill.
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
- chatgpt_web_assisted: I will prepare the upload archive and prompt, then the user runs it manually in ChatGPT Web and sends the result back
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
python scripts/run_gpt54pro_analysis.py \
  --manifest .codex-analysis/context/manifest.json \
  --goal "<user goal>" \
  --env-file .env \
  --mode auto
```

Before constructing the OpenAI client, this helper reads the specified `.env` file. If `OPENAI_API_KEY` is missing from both `.env` and the current environment, Codex should ask the user to set it and stop instead of attempting the API call.

For `gpt-5.4-pro` background runs, the helper uses adaptive polling instead of a short fixed interval:

- under 30 minutes elapsed: sleep 10 minutes between polls
- 30 to under 40 minutes elapsed: sleep 5 minutes between polls
- 40 to under 50 minutes elapsed: sleep 3 minutes between polls
- 50 minutes and beyond: sleep 1 minute between polls

If the Responses API returns a terminal failure status, stop immediately and do not retry automatically. Pro requests are expensive, so failure handling should be explicit and user-driven.

### Model defaults

- model: `gpt-5.4-pro`
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

This mode is fully manual.

It must never:

- open a browser on the user's behalf
- use Playwright or other browser automation
- click through ChatGPT Web UI
- auto-upload files
- auto-submit prompts
- scrape ChatGPT output from the page

It should only prepare a handoff package for the user.

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

### How this mode works

1. Codex prepares the upload zip and prompt only.
2. The user manually opens ChatGPT Web.
3. The user manually starts a new chat.
4. The user manually chooses `Pro` if that is the approved model for this run.
5. The user manually uploads `upload-source.zip`.
6. The user manually pastes `chatgpt-prompt.txt`.
7. The user manually waits for the answer.
8. The user manually pastes the result back to Codex using `return-to-agent-template.md`.
9. Codex then continues local design or implementation work based on that pasted result.

### Rules for the manual web path

- Do not programmatically interact with `chatgpt.com`.
- Do not scrape or auto-ingest the answer from the browser.
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

1. scope and assumptions
2. short system map
3. top findings, prioritized
4. evidence for each finding with file paths and line references when possible
5. confirmed facts vs inference or uncertainty
6. test-gap recommendations
7. refactoring or redesign recommendations
8. quick wins vs deeper changes
9. suggested next design steps

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

python scripts/run_gpt54pro_analysis.py \
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

python scripts/run_gpt54pro_analysis.py \
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
- If `chatgpt_web_assisted` was chosen, return the generated upload zip, prompt, and next-step file paths to the user. Do not browse to ChatGPT Web for them.
- If the external run returns a strong report, summarize the result back to the user in the same language they used.
- After the analysis, switch back to local repo work and use the report as an input to planning, design, or implementation.
