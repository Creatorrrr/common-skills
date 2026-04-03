---
name: claude-code-agent-team-analysis
description: Use this skill when the user wants a deep second-opinion repository analysis using Claude Code CLI with local agent teams. It prepares repository context, launches a read-only multi-agent review from the local claude CLI, and stores a resumable evidence-based report for architecture review, refactoring strategy, test-gap analysis, performance, workflow validity, missing implementation, or deprecated and unused logic when the repository is too large to inspect comfortably in-session.
---

# Claude Code agent-team codebase analysis

This skill uses a broad, evidence-first analysis style with a single local execution path built around Claude Code CLI agent teams.

It is designed for large or messy repositories where a single in-session pass is likely to miss architecture boundaries, workflow breakpoints, test gaps, or stale logic.

## Core principles

1. The user's stated goal, scope, and direction override every default in this skill.
2. This skill uses one execution path only: local `claude` CLI analysis.
3. Prefer a small read-only agent team over a monolithic single-pass review when the work can be split into independent lenses.
4. Keep the analysis grounded in concrete repository files.
5. Distinguish confirmed findings from inference and unknowns.
6. Preserve resumability: follow-up design work should continue the saved Claude Code session when practical.
7. Avoid nested Claude Code launches from inside a Claude-spawned shell.
8. Use the preparation step to reduce context sprawl even though the repository remains local.
9. For analysis-only runs, keep the team read-only and prevent edits, writes, commits, or destructive shell commands.

## Execution model

This skill intentionally supports only:

- `claude_code_cli_local`

The helper script launches local Claude Code with:

- `-p` non-interactive execution
- `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` in the helper subprocess environment
- CLI-defined custom subagents passed through `--agents`
- appended system instructions through `--append-system-prompt-file` when supported, or `--append-system-prompt` as an inline fallback
- a lead prompt that explicitly asks Claude to create and coordinate the team
- resumable sessions through saved `session_id`

This skill does **not** require any manual browser steps.

## Use this skill when

- The user explicitly wants a deeper multi-agent analysis pass run locally.
- The repository or subsystem is large enough that a coordinated second-opinion review is useful.
- The user wants a design review before implementation.
- The user wants one or more of these lenses:
  - structural refactoring
  - architecture and workflow tracing
  - test inventory, gap analysis, and reinforcement
  - performance and scalability review
  - use-case or workflow validity
  - missing or stubbed implementation detection
  - deprecated, dead, duplicate, or suspiciously unused logic
  - optional security review when the target area is security-sensitive

## Do not use this skill when

- The task is small and can be answered reliably from a few files already in context.
- The task is strictly sequential or confined to a tiny number of files.
- The user explicitly does not want a local Claude Code run.

## Required first pass

Before calling local Claude Code:

1. Read any applicable `AGENTS.md` files.
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

## Context preparation policy

Use the existing preparation script first:

```bash
python scripts/prepare_analysis_context.py --root . --goal "<user goal>" --mode auto
```

That script writes artifacts under `.codex-analysis/context/` by default.

### File inclusion defaults

Include these by default if they are text and not Git-ignored:

- source code
- tests
- root and module READMEs
- architecture and ADR documents
- build and toolchain config
- infra and deployment config
- CI workflows
- `AGENTS.md`, `PLANS.md`, migration notes, runbooks

### Low-signal defaults

Skip these by default unless the user explicitly asks for them:

- binaries and images
- vendored dependencies
- generated bundles and minified assets
- coverage outputs
- cache folders
- snapshots and bulky fixtures
- lockfiles, unless dependency analysis is part of the request

### Why keep a preparation step for a local CLI run

Even though Claude Code can inspect the local repository directly, the preparation artifacts still matter because they:

- produce a repo map up front
- identify likely high-signal files
- preserve a focused subset when the user gave a narrow scope
- reduce wasted exploration by the lead agent and teammates

## Recommended agent-team pattern

Use a lead/supervisor pattern with specialized read-only workers.

### Lead session

The main Claude session should:

- read `manifest.json` and `repo_tree.txt`
- decide whether to run a broad whole-repo pass or a focused scoped pass
- create the team
- assign independent lenses to teammates
- synthesize the final report
- save the resulting `session_id` for follow-up work

### Default worker roles

Unless the user asked for something different, use these roles:

1. `architecture-mapper`
   - maps modules, entrypoints, major boundaries, and visible workflows
2. `correctness-gap-reviewer`
   - checks workflow validity, failure handling, TODO/FIXME/HACK markers, missing implementation, and deprecated or dead logic
3. `tests-refactor-reviewer`
   - checks test coverage shape, missing scenarios, flakiness risk, duplication, and refactoring seams
4. `performance-reviewer`
   - checks hot paths, repeated work, avoidable I/O, N+1 patterns, caching, async boundaries, and scaling risks
5. `security-reviewer` (conditional)
   - add when the target area touches auth, permissions, secrets, payments, external input, public APIs, or other clearly security-sensitive surfaces

### Default model split

Use this split unless the user asks otherwise:

- lead: `opus`
- worker subagents: `sonnet`

This keeps synthesis quality high while avoiding an all-Opus team for every independent workstream.

### Read-only enforcement

This skill is analysis-first, not implementation-first.

The helper should:

- restrict the available tool set to read/search/LSP/team coordination tools plus tightly scoped read-only shell usage
- prevent file edits and writes
- avoid commits and destructive commands
- avoid browser automation and web research unless the user explicitly asks for it inside Claude Code

## Selection policy

The preparation script emits a recommendation.

Use it like this:

### `full_repo_team`

Use a broader team pass when:

- the repo is moderate in size
- the user wants architecture-level conclusions
- the codebase shape itself is part of the question
- no narrow scope was given

### `focused_team`

Use a focused team pass when:

- explicit scope paths were provided
- the target problem is narrow
- the repo is large enough that broad exploration would dilute the result
- a subsystem review is more valuable than a shallow whole-repo pass

Even in focused mode, the lead and workers may expand slightly into dependent files, configs, tests, or docs when needed to validate a workflow.

## Waiting and polling behavior

The helper uses the same adaptive waiting schedule as the prior background helper flow, but halves each interval for the local Claude CLI subprocess:

- under 30 minutes elapsed: sleep 5 minutes between polls
- 30 to under 40 minutes elapsed: sleep 2 minutes 30 seconds between polls
- 40 to under 50 minutes elapsed: sleep 1 minute 30 seconds between polls
- 50 minutes and beyond: sleep 30 seconds between polls

## Execution path

Use the helper script:

```bash
python scripts/run_claude_code_agent_team_analysis.py \
  --manifest .codex-analysis/context/manifest.json \
  --goal "<user goal>" \
  --mode auto
```

### What the helper generates

Under `.codex-analysis/claude-code/` by default, generate:

- `claude-agents.json`
- `claude-system-prompt.md`
- `claude-user-prompt.txt`
- `request_meta.json`
- `run_meta.json`
- `analysis-status.json`
- `analysis-result.json`
- `analysis-report.md`
- `analysis-report.partial.md` when the first result is incomplete and the automatic follow-up still fails
- `claude-stdout.json`
- `claude-stderr.log`

### How the helper works

1. Reads the local preparation manifest.
2. Chooses a broad or focused team mode.
3. Generates CLI-defined subagent roles.
4. Generates an appended system prompt for the lead.
5. Runs a CLI capability probe and saves the result into `request_meta.json`, `run_meta.json`, and `analysis-status.json`.
6. Selects `system_prompt_mode` based on CLI capability support: `file` when `--append-system-prompt-file` is available, otherwise `inline` via `--append-system-prompt`.
7. Optionally runs a short preflight Claude probe. The default policy is `auto`, which probes when the lead model is `opus` or the estimated context is large.
8. Launches local `claude -p` with agent teams activated by environment and started from the prompt.
9. Polls the subprocess with the halved adaptive waiting schedule.
10. Saves the structured JSON output and resumable session metadata.
11. Applies a report completeness gate before accepting `analysis-report.md`.
12. If the first report is incomplete and a `session_id` exists, automatically resumes the same session once to request a final consolidated report.
13. Writes `analysis-report.md` only for a report that passes the completeness gate. On failure after follow-up, leaves `analysis-report.partial.md` plus a classified failure in `analysis-status.json`.

## Nested-session safety

This helper is meant to launch from a normal shell, CI runner, or another external automation context.

If it is started from a shell already spawned by Claude Code, it should stop early rather than attempting a nested Claude Code launch.

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
8. optional security posture where relevant
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

## Output requirements for the local Claude run

Ask for a report with this structure unless the user asked for something else:

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

The helper enforces a minimum acceptance gate before it writes `analysis-report.md`:

- minimum report length
- required section headings matching the requested report structure
- explicit `top findings`, `evidence`, `test-gap`, and `next steps` coverage

The section check is heading-aware rather than raw substring-based:

- numbered markdown headings such as `## 3. Top findings (prioritized)` are accepted
- canonical-equivalent headings such as `Evidence per finding`, `Test gap recommendations`, and `Refactoring / redesign recommendations` are accepted
- body text that merely mentions a section name does not satisfy the gate unless it appears as a heading

Treat `analysis-status.json` as the source of truth for run outcome:

- `status: succeeded` means the final report passed the gate
- `status: failed` plus `failure_kind` explains whether the run failed because of quota, access, CLI contract drift, invalid output, or report incompleteness
- `analysis-report.partial.md` is only a fallback artifact for incomplete runs that could not be repaired automatically
- `request_meta.json` and `run_meta.json` record `system_prompt_mode` as `file` or `inline` so CLI contract drift is visible after the run

## Example commands

### Broad architecture + test-gap pass

```bash
python scripts/prepare_analysis_context.py \
  --root . \
  --goal "Analyze the overall system with a focus on structural refactoring and strengthening test coverage" \
  --mode auto

python scripts/run_claude_code_agent_team_analysis.py \
  --manifest .codex-analysis/context/manifest.json \
  --goal "Analyze the overall system with a focus on structural refactoring and strengthening test coverage" \
  --mode auto \
  --preflight-probe auto
```

### Focused subsystem pass

```bash
python scripts/prepare_analysis_context.py \
  --root . \
  --goal "Review the checkout workflow for design validity and missing implementation" \
  --scope src/checkout tests/checkout docs/checkout.md \
  --mode auto

python scripts/run_claude_code_agent_team_analysis.py \
  --manifest .codex-analysis/context/manifest.json \
  --goal "Review the checkout workflow for design validity and missing implementation" \
  --mode auto \
  --preflight-probe auto
```

### Follow-up design iteration on the saved session

```bash
python scripts/run_claude_code_agent_team_analysis.py \
  --manifest .codex-analysis/context/manifest.json \
  --goal "Use the prior analysis to design refactoring priorities and the order for strengthening tests" \
  --preflight-probe off \
  --resume-last
```

### Dry run to inspect prompts and team roles without launching Claude

```bash
python scripts/run_claude_code_agent_team_analysis.py \
  --manifest .codex-analysis/context/manifest.json \
  --goal "Analyze the auth module structure and failure-handling risks" \
  --mode auto \
  --dry-run
```

### Inspect the classified run state

```bash
jq . .codex-analysis/claude-code/analysis-status.json
```

## Notes for the calling agent

- Prefer reading and summarizing the generated `manifest.json` before the Claude run.
- Prefer `focused_team` when explicit scope hints were given.
- Save and reuse the generated `session_id` for follow-up design questions.
- The helper only uses agent-team activation through environment plus prompt. Do not reintroduce undocumented CLI activation flags.
- The helper prefers `--append-system-prompt-file` but can fall back to inline `--append-system-prompt` if the local CLI only exposes the inline variant.
- `analysis-status.json` is the primary place to check run outcome, classified failure kind, stdout and stderr locations, and whether automatic follow-up was used.
- `analysis-report.md` exists only when the final report passed the completeness gate.
- If the repo is security-sensitive, enable the conditional security reviewer.
- After the analysis finishes, switch back to local repo work and treat the report as a strong input, not infallible truth.
