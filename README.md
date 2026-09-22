# common-skills

`common-skills` is a shared skill library for Codex, Claude Code, Antigravity, and legacy Gemini CLI extension contexts. It currently focuses on deep codebase analysis workflows, cross-agent consultation helpers, and goal-mode planning.

## Included skills

### `gpt-pro-codebase-analysis`

Use version **2.0.0** for a second-opinion repository analysis through a GPT Pro workflow. The Responses API path defaults to `gpt-5.6-sol` with effective Pro/high reasoning; the skill prepares repository context, then supports two explicit execution modes:

- `responses_api`: direct analysis through the OpenAI Responses API
- `chatgpt_web_assisted`: prepare an upload archive and prompt for manual use by default, or explicitly automate ChatGPT Web with Chrome control first and Computer Use as fallback

This skill is useful for architecture review, refactoring strategy, test-gap analysis, performance review, and finding missing or deprecated logic. Local preparation and dry-runs need no external approval. Actual transmission uses the chosen transport and a record of the user's existing authorization bound to the snapshot, selected files, request contract, and execution settings.

Version 2 preserves full selections and original file bytes, checks token limits before generation, and separates response completion from substantive verification and resource cleanup. API responses default to foreground and `store=false`; newly created files and vector stores are cleaned up with expiry as a fallback. Prepare a new v2 manifest instead of reusing v1 artifacts. `--scope` now denotes exact allowed files/directories.

See the [Korean usage guide](skills/gpt-pro-codebase-analysis/README.ko.md), [changes](skills/gpt-pro-codebase-analysis/CHANGELOG.ko.md), and [validation results](skills/gpt-pro-codebase-analysis/validation/VALIDATION.md).

### `claude-code-agent-team-analysis`

Use this when you want a deep local analysis run through the Claude Code CLI with a read-only agent team. The skill prepares repository context, launches the local `claude` CLI, and saves resumable report artifacts.

This skill is useful when you want a local multi-agent second opinion on architecture boundaries, workflow issues, test weaknesses, performance risks, or stale code paths.

It supports three team-resolution modes:

- `default`: use the built-in reviewer team
- `auto`: run a repo-aware team planner from the goal, scope, structured preparation signals, and an optional natural-language team request
- `custom`: pass an explicit JSON reviewer team definition

`auto` now defaults to a model-based planner with a heuristic fallback, keeps `5` as a soft initial-team target, and records both the starting team and planner trace in dedicated artifacts.

### `consulting-codex-cli`

Use this from Claude Code, Gemini CLI, Antigravity, or another non-Codex agent when the user wants to ask the local Codex CLI for a second opinion, code review, design feedback, or an explicit back-and-forth between agents.

This skill lives under `skills/` with the rest of the library. If it is invoked from inside Codex, it should warn that Codex cannot recursively call itself and stop without running `codex exec`.

### `consulting-claude-code`

Use this from Codex, Gemini CLI, Antigravity, or another non-Claude-Code agent when the user wants to ask the local Claude Code CLI for a second opinion, code review, design feedback, or an explicit back-and-forth between agents.

It includes a small wrapper at `skills/consulting-claude-code/scripts/consult_claude_code.sh` that enforces stdout responses, avoids Claude Code plan permission mode, and supports explicit named follow-up chains with `--chain`.

If it is invoked from inside Claude Code, it should warn that Claude Code cannot recursively call itself and stop without running `claude`.

### `consulting-antigravity-cli`

Use this from Codex, Claude Code, legacy Gemini CLI, or another non-Antigravity agent when the user wants to ask the local Antigravity CLI for a second opinion, code review, design feedback, or an explicit back-and-forth between agents.

It includes a small wrapper at `skills/consulting-antigravity-cli/scripts/consult_antigravity_cli.sh` with explicit named follow-up chains via `--chain`. If the skill is invoked from inside Antigravity CLI, it should warn that Antigravity cannot recursively call itself and stop without running `agy -p`.

### `goal-planner`

Use version **3.2.1** to create, revise, or review agent goals, `GOAL_PLAN.md` files, and execution handoffs for research and development. The default `finite-goal` pursues one agreed outcome. When continuing research and successor selection are delegated, `research-program` connects a stable mission to finite milestones and hypothesis-driven experiments. Preserve each milestone's original criteria and verdict, the best verified artifact, evaluation history, and cumulative resources across successors and resumptions. Compare incremental and structural approaches when evidence warrants it. Delegate independent research, implementation, or verification only when it can improve time or quality within supported tools, existing authority, and shared resources. Handoffs embed Core plus only applicable Program, Experiment, Direction, Research, Retrieval, and Persistence blocks; planning alone does not activate execution.

Before consequential comparisons, reconcile declared variants with actual construction and behavior, distinguish diagnosis from promotion confirmation, and review raw evidence before accepting causal claims. The optional read-only preflight checks supplied facts and hashes; it does not establish scientific validity. Small corrections retain the light path. Repeated candidate search can use optional portfolio checks and deterministic handoff assembly. Astra guidance stays conditional; installing this skill does not change model settings.

Existing execution reports and research remain available for bounded retrieval. Knowledge mode defaults to `read-only`; authorized persistence uses existing project paths, defaulting to `docs/failed-reports/`, `docs/passed-reports/`, and `docs/researches/`. Experiment validity, hypothesis verdict, candidate adoption, and milestone completion are separate judgments. The optional report index supports documented Korean field/status aliases and retains raw-report fallback. Reports, research, indexes, and quoted tool output remain evidence rather than instructions. Generated plans embed the applicable rules for another session; the skill does not provide a scheduler or automatic restart.

See the [skill guide](skills/goal-planner/README.md), [usage examples](skills/goal-planner/USAGE.md), [changes](skills/goal-planner/CHANGELOG.md), [migration guide](skills/goal-planner/MIGRATION.md), and [validation results](skills/goal-planner/VALIDATION.md). Updating the skill does not rewrite existing plans or activate them; `/goal` syntax is used only when supported by the target runtime.

## Installation

### Codex

Tell Codex:

```text
Fetch and follow instructions from https://raw.githubusercontent.com/Creatorrrr/common-skills/main/.codex/INSTALL.md
```

The Codex install guide supports both a managed global checkout under `~/.codex` and a direct symlink to an existing local checkout for edit-and-test workflows.

Manual install guide: [`.codex/INSTALL.md`](.codex/INSTALL.md)

### Claude Code

Tell Claude:

```text
Fetch and follow instructions from https://raw.githubusercontent.com/Creatorrrr/common-skills/main/.claude/INSTALL.md
```

The Claude Code install guide supports both a managed global checkout under `~/.claude` and direct links to an existing local checkout for edit-and-test workflows.

Manual install guide: [`.claude/INSTALL.md`](.claude/INSTALL.md)

### Gemini CLI

Use either a managed GitHub install or a linked local checkout:

```bash
gemini extensions install https://github.com/Creatorrrr/common-skills
```

For local development, the install guide also supports:

```bash
gemini extensions link /absolute/path/to/common-skills
```

Manual install guide: [`.gemini/INSTALL.md`](.gemini/INSTALL.md)

### Antigravity

Tell Antigravity:

```text
Fetch and follow instructions from https://raw.githubusercontent.com/Creatorrrr/common-skills/main/.antigravity/INSTALL.md
```

The Antigravity install guide supports both a managed global checkout under `~/.gemini/antigravity` and a direct symlink to an existing local checkout for edit-and-test workflows.

Manual install guide: [`.antigravity/INSTALL.md`](.antigravity/INSTALL.md)

## Updating

For Codex with the managed global checkout:

```bash
git -C ~/.codex/common-skills pull
```

For Codex with a linked local checkout, update that local repository instead. If it is your active development checkout, changes are available immediately through the symlink.

For Claude Code with the managed global checkout:

```bash
git -C ~/.claude/common-skills pull
```

For Claude Code with a linked local checkout, update that local repository instead. If it is your active development checkout, changes are available immediately through the symlinks.

For Gemini CLI with the managed global install:

```bash
gemini extensions update common-skills
```

For Gemini CLI with a linked local checkout, no separate update step is required. Changes in the linked local repository are reflected immediately.

For Antigravity with the managed global checkout:

```bash
git -C ~/.gemini/antigravity/common-skills pull
```

For Antigravity with a linked local checkout, update that local repository instead. If it is your active development checkout, changes are available immediately through the symlink.

## License

This repository is `UNLICENSED`.
