# common-skills

`common-skills` is a shared skill library for Codex, Claude Code, Gemini CLI, and Antigravity. It currently focuses on deep codebase analysis workflows.

## Included skills

### `gpt-pro-codebase-analysis`

Use this when you want a second-opinion repository analysis through a GPT Pro workflow. The skill prepares repository context, then supports two explicit execution modes:

- `responses_api`: direct analysis through the OpenAI Responses API
- `chatgpt_web_assisted`: prepare an upload archive and prompt for manual use in ChatGPT Web

This skill is useful for architecture review, refactoring strategy, test-gap analysis, performance review, and finding missing or deprecated logic. When you use it through an agent, choose one mode explicitly before execution starts.

### `claude-code-agent-team-analysis`

Use this when you want a deep local analysis run through the Claude Code CLI with a read-only agent team. The skill prepares repository context, launches the local `claude` CLI, and saves resumable report artifacts.

This skill is useful when you want a local multi-agent second opinion on architecture boundaries, workflow issues, test weaknesses, performance risks, or stale code paths.

It supports three team-resolution modes:

- `default`: use the built-in reviewer team
- `auto`: run a repo-aware team planner from the goal, scope, structured preparation signals, and an optional natural-language team request
- `custom`: pass an explicit JSON reviewer team definition

`auto` now defaults to a model-based planner with a heuristic fallback, keeps `5` as a soft initial-team target, and records both the starting team and planner trace in dedicated artifacts.

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
