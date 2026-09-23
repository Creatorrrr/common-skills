---
name: consulting-claude-code
description: Use when a non-Claude-Code agent wants to consult Claude Code through the local claude CLI for a second opinion, code review, design feedback, or an ongoing cross-model dialogue. Claude Code must never invoke this skill on itself.
---

# Consult Claude Code from another agent

This skill calls `claude -p` and returns Claude's answer to the calling agent. It is for Codex, Antigravity, and other **non-Claude-Code** callers. A Claude Code session must not invoke `claude` recursively.

The source is this directory in the common-skills checkout. The launcher at [scripts/consult_claude_code.sh](scripts/consult_claude_code.sh) uses the shared runner at `../../lib/consultation_runner.py`; keep the checkout together when installing or copying the skill. Do not expose this skill in Claude Code's own skill discovery path.

## Defaults and boundaries

| Setting | Default |
| --- | --- |
| Model | `opus` |
| Effort | `max` |
| Permission mode | `auto` |
| Output | complete answer on stdout, text by default |
| Working directory | caller's current directory |
| Spend and token caps | none |

Honor explicit user overrides. Never lower effort merely because a call is slow. Do not use `--permission-mode plan` for this consultation; the wrapper converts it to `auto` and requires plans in stdout. Do not select `bypassPermissions` unless the user explicitly requests it. Pass the user's request faithfully, and use `--cd` or `--add-dir` only for paths the user specified.

## Conversation continuity

By default, calls from the **same identifiable caller conversation** and physical working directory continue one Claude conversation. A new caller conversation receives a separate state key, even in the same repository. The wrapper accepts a caller ID only from the immediate agent process or from explicit per-call `--caller-kind` and `--caller-session-id` arguments. If the current caller cannot be identified, it warns and runs an independent one-shot consultation. It never guesses from the working directory or uses Claude's global `--continue`.

The caller must pass its actual current conversation ID. Do not copy an ID from a prior task, shell profile, saved file, or an outer agent whose environment was inherited. If the caller cannot supply a current ID, leave the safe one-shot fallback in place.

| Request | Wrapper option | Effect |
| --- | --- | --- |
| Normal follow-up | none | Resume this caller's saved Claude ID |
| Independent question | `--one-shot` | Start separately without reading or changing saved state |
| Replace current consultation | `--new-session` | Retire the old mapping before invoking Claude |
| Another thread within this caller | `--chain NAME` | Parent-scoped named conversation |
| Intentionally share across callers | `--shared-chain NAME` | Cross-caller conversation, only on explicit user request |
| Inspect or clear mapping | `--status`, `--reset-session`, `--reset-chain NAME`, `--reset-shared-chain NAME` | State only; clearing does not delete Claude's transcript |

Inherited `CONSULT_CLAUDE_CHAIN_KEY` is ignored. Earlier globally keyed `--chain` files are not imported into the new caller-scoped state. `--status` remains available while a consultation is running. A confirmed failure before Claude starts preserves the prior mapping; an uncertain failure after launch blocks it. Do not silently retry a blocked conversation; use `--new-session` or an explicit reset after reviewing the error. Once Claude has started, a failed `--new-session` never restores the old mapping.

## Invocation

Run the launcher from the caller's current directory:

```bash
/path/to/consult_claude_code.sh "user prompt here"
```

Use stdin for detailed or shell-sensitive prompts:

```bash
/path/to/consult_claude_code.sh <<'PROMPT'
<user prompt verbatim>
PROMPT
```

When a prompt is supplied as arguments, stdin is ignored. Choose one input form per call.

Examples of explicit controls:

```bash
/path/to/consult_claude_code.sh --new-session "Start a separate review"
/path/to/consult_claude_code.sh --one-shot "Independent check"
/path/to/consult_claude_code.sh --chain architecture "Follow up in this named thread"
/path/to/consult_claude_code.sh --model sonnet --effort high "Review this function"
```

For a caller without an automatically available session ID, its host integration may pass `--caller-kind antigravity --caller-session-id <current-conversation-id>` on **each** call. Only do this when the host supplied that ID for the current conversation. `--output-format json` or `stream-json` is available when structured output is needed.

The wrapper creates a UUID on a fresh call, resumes by exact ID on later calls, and checks Claude's returned session ID. If Claude responds only with a file-artifact notice, it asks the same Claude session once to print the complete answer. Present Claude's answer to the user before synthesizing it with your own assessment, unless the user requested another presentation.

## Authentication and waiting

If host sandboxing hides Claude's normal login or session files, use the host's authorized normal-local execution path. For authentication diagnosis, run `--auth-smoke` from its neutral temporary directory before sending repository context. Keep Claude's permission mode at `auto` unless the user specified another supported mode.

`opus` at `max` may take a long time. Do not impose a short shell timeout, kill a slow call, or start a duplicate consultation. If the CLI exits with an auth, quota, or session error, report the error rather than silently changing model or conversation.
