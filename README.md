# common-skills

`common-skills` is a shared skill library for Codex, Claude Code, and Gemini CLI. It currently focuses on deep codebase analysis workflows.

## Included skills

### `gpt-5.4-pro-codebase-analysis`

Use this when you want a second-opinion repository analysis with GPT-5.4 Pro. The skill prepares repository context, then supports two explicit execution modes:

- `responses_api`: direct analysis through the OpenAI Responses API
- `chatgpt_web_assisted`: prepare an upload archive and prompt for manual use in ChatGPT Web

This skill is useful for architecture review, refactoring strategy, test-gap analysis, performance review, and finding missing or deprecated logic. When you use it through an agent, choose one mode explicitly before execution starts.

### `claude-code-agent-team-analysis`

Use this when you want a deep local analysis run through the Claude Code CLI with a read-only agent team. The skill prepares repository context, launches the local `claude` CLI, and saves resumable report artifacts.

This skill is useful when you want a local multi-agent second opinion on architecture boundaries, workflow issues, test weaknesses, performance risks, or stale code paths.

## Installation

### Codex

Tell Codex:

```text
Fetch and follow instructions from https://raw.githubusercontent.com/Creatorrrr/common-skills/main/.codex/INSTALL.md
```

Manual install guide: [`.codex/INSTALL.md`](.codex/INSTALL.md)

### Claude Code

Tell Claude:

```text
Fetch and follow instructions from https://raw.githubusercontent.com/Creatorrrr/common-skills/main/.claude/INSTALL.md
```

Manual install guide: [`.claude/INSTALL.md`](.claude/INSTALL.md)

### Gemini CLI

Install the extension with:

```bash
gemini extensions install https://github.com/Creatorrrr/common-skills
```

Manual install guide: [`.gemini/INSTALL.md`](.gemini/INSTALL.md)

## Updating

Pull the repository again from the install location you chose:

```bash
git -C ~/.codex/common-skills pull
```

or:

```bash
git -C ~/.claude/common-skills pull
```

For Gemini CLI:

```bash
gemini extensions update common-skills
```

## License

This repository is `UNLICENSED`.
