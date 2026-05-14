---
name: consulting-claude-code
description: Use when a non-Claude-Code agent (Codex, Gemini CLI, etc.) wants to consult Claude Code via its local `claude` CLI for a second opinion, cross-model dialogue, code review, design feedback, or general "ask Claude" requests. Triggers include phrases like "claude한테 물어봐", "클로드 의견", "opus 의견", "두 번째 의견", "cross-check", "consult claude", or any explicit request to invoke the `claude` CLI from inside a non-Claude agent session. This skill is NOT for Claude Code itself — Claude Code must never invoke this skill or call `claude` on itself.
---

# Consulting Claude Code from a non-Claude agent

This skill defines how a **non-Claude-Code** agent session (Codex, Gemini CLI, or any other harness) invokes the local `claude` CLI as a subprocess to obtain Claude Code's opinion, then surfaces the response back to the user (or feeds it into further reasoning on the caller side).

It is a thin, one-shot bridge — not a full multi-agent analysis pipeline. For a heavy repository review, prefer `claude-code-agent-team-analysis` instead.

## Audience boundary (READ FIRST)

**This skill is for non-Claude-Code agents only.**

- ✅ Codex CLI calling `claude`
- ✅ Gemini CLI / other harnesses calling `claude`
- ❌ Claude Code calling `claude` — **never**. Self-invocation is not a valid use of this skill.

If you are Claude Code reading this skill, stop. Do not invoke the workflow below; ignore this skill and answer using your own reasoning (or, if a heavy second pass is genuinely needed, use `claude-code-agent-team-analysis` which is the analysis-targeted path).

The intentional placement is:

- Source of truth: `/Users/chasoik/Projects/common-skills/skills/consulting-claude-code/` (this file)
- Exposed to Codex via the existing symlink at `~/.agents/skills/common-skills/`
- **NOT** mirrored into `~/.claude/common-skills/skills/`. Do not copy it there. Do not symlink it there. Do not add it to any Claude Code skill discovery path.

If a future sync ever lands this file inside a Claude-Code-visible location, the correct action is to remove it from that location, not to "make it work for Claude Code too".

## Core principles

1. The user's explicit instructions always win. Defaults below apply ONLY when the user did not specify a value.
2. Always run `claude` non-interactively with `-p` so the call returns and the caller can read the response.
3. Never pass `--max-budget-usd` or any other budget cap. Claude Code must run without a spend limit.
4. Long waits are expected. `xhigh` effort on `opus` can take many minutes. Do not abort early, do not impose a short shell timeout, and do not retry just because output is slow.
5. Pass the user's prompt through as faithfully as possible. Do not silently rewrite it.
6. Never start a nested `claude` from inside a session that is already running Claude Code. This skill is one-way: non-Claude agent → Claude Code, never Claude Code → Claude Code.

## Defaults (when not explicitly specified)

| Option | Default | CLI flag |
|--------|---------|----------|
| Model | `opus` | `--model opus` |
| Effort | `xhigh` | `--effort xhigh` |
| Permission mode | `auto` (Claude Code decides per-tool) | `--permission-mode auto` |
| Print mode | non-interactive | `-p` |
| Output format | text | `--output-format text` |
| Budget cap | none | (do NOT pass `--max-budget-usd`) |

If the user provides a different model (e.g. "sonnet에게 물어봐"), effort (e.g. "effort medium"), or permission mode (e.g. "plan 모드로", "edits 까지 허용"), use the user-specified value and leave the rest at defaults.

## Canonical invocation

```bash
claude -p "<user prompt verbatim>" \
  --model opus \
  --effort xhigh \
  --permission-mode auto \
  --output-format text
```

When the consultation should also reason about the current repo, add the working directory explicitly so Claude Code is allowed to read it:

```bash
claude -p "<prompt>" \
  --model opus \
  --effort xhigh \
  --permission-mode auto \
  --output-format text \
  --add-dir "$(pwd)"
```

When the calling agent needs to parse the response, switch the output format only — never strip the defaults above:

```bash
claude -p "<prompt>" \
  --model opus \
  --effort xhigh \
  --permission-mode auto \
  --output-format json
```

## Waiting policy

`xhigh` effort responses regularly take 5–30 minutes and can occasionally run longer. Treat this as the normal case.

- Do not set a short shell timeout. If the shell environment imposes one, set it generously (e.g. 2 hours) or run the command in the background and poll status rather than killing it.
- If the process is still running, keep waiting. Slow ≠ stuck.
- Only treat the call as failed if `claude` exits with a non-zero status, prints a hard authentication or quota error, or the user explicitly cancels.
- Do not start a second `claude` call to "speed it up" while the first is still running.

If the run is happening inside a wrapper that does need a heartbeat, prefer launching `claude -p ...` as a background job and polling for completion rather than killing it.

## Permission mode notes

`--permission-mode auto` lets Claude Code judge each tool request on its own. This is the requested default and matches "권한은 자동 판단".

Override only when the user explicitly asks for it:

- `--permission-mode plan` — review-only / planning consultation, no edits
- `--permission-mode acceptEdits` — auto-accept edits Claude proposes
- `--permission-mode bypassPermissions` — only if the user explicitly opts in; warn them first since it disables permission checks entirely
- `--permission-mode dontAsk` / `default` — explicit user choice only

Never silently upgrade to `bypassPermissions`.

## What to send back to the user

By default, surface Claude Code's response to the user as-is. Do not summarize, rewrite, or filter unless the user asked for that.

If the calling agent is going to chain the response into further reasoning (e.g. "compare your view with Claude's"), make the round-trip explicit to the user: state that you are calling `claude`, wait, then present Claude's reply before continuing.

## Quick reference

| Situation | Command shape |
|-----------|---------------|
| Ask for an opinion, no repo access needed | `claude -p "..." --model opus --effort xhigh --permission-mode auto --output-format text` |
| Ask about the current repo | Same as above plus `--add-dir "$(pwd)"` |
| User specified a different model | Replace `--model opus` with the requested model alias or full ID |
| User specified a different effort | Replace `--effort xhigh` with `low`, `medium`, `high`, `xhigh`, or `max` |
| User wants planning only | Replace `--permission-mode auto` with `--permission-mode plan` |
| Caller needs structured output | Replace `--output-format text` with `--output-format json` |

## Common mistakes

| Mistake | Effect |
|---------|--------|
| Adding `--max-budget-usd` | Violates "no budget limit". The response can be truncated mid-stream. |
| Omitting `-p` | `claude` enters interactive mode and the subprocess hangs forever. |
| Imposing a short shell timeout (e.g. 60s) | `xhigh` effort never finishes; the call is killed and Codex reports a false failure. |
| Silently changing the model or effort because the run feels slow | Misrepresents the consultation. Slow is expected; keep the requested settings. |
| Rewriting the user's prompt before sending | Loses nuance the user wanted Claude to see. Pass it verbatim, or quote it inside a wrapper sentence at most. |
| Starting nested `claude` calls from inside a Claude Code session | Causes recursive sessions and is explicitly disallowed by this skill. |
| Calling `--permission-mode bypassPermissions` without asking | Silently disables permission checks. Always confirm with the user first. |

## Notes for the calling agent

- This skill is one-shot per request. If the user asks for an ongoing back-and-forth, run `claude -p ...` once per turn and keep the conversation transcript on the caller side; do not try to keep `claude` interactive.
- If `claude` is not on PATH, surface the error to the user rather than guessing an install location. The user keeps `claude` at the binary returned by `which claude`.
- The defaults in this skill are deliberate. Do not "optimize" them away on the assumption that a smaller model or lower effort is good enough — the user picked `opus` + `xhigh` on purpose.
- If you are Claude Code, you reached this file by mistake. Stop following it — see the "Audience boundary" section above.
