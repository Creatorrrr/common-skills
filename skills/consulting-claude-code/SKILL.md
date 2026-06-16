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
4. Long waits can happen at higher effort levels. At the default `medium` effort responses are usually fast, but `high`/`xhigh`/`max` on `opus` can take many minutes. Do not abort early, do not impose a short shell timeout, and do not retry just because output is slow.
5. Pass the user's prompt through as faithfully as possible. Do not silently rewrite it.
6. Never start a nested `claude` from inside a session that is already running Claude Code. This skill is one-way: non-Claude agent → Claude Code, never Claude Code → Claude Code.
7. Unless the user explicitly says otherwise, `claude` operates on the **same repository at the same working directory** as the calling agent. Spawn `claude` from the caller's current `cwd`; do not `cd` somewhere else, do not point it at another repo, and do not append extra `--add-dir` paths that the user did not ask for. A different target path must come from an explicit user instruction (e.g. "X 리포지토리에 대해 물어봐", "이건 ~/other-repo 기준으로", "이 경로도 같이 봐줘").
8. If the calling harness runs shell commands in a host sandbox, run real Claude CLI calls through that harness's explicit unsandboxed/escalated execution path after user approval. Sandboxed calls can hide Claude's normal auth state, browser integration, or home-directory session files.
9. Require a console response. Claude must put the complete answer in stdout. It must not answer by only saying it wrote a plan, report, markdown file, or other artifact.
10. Do not use Claude Code's plan permission mode for this skill. Planning requests are still valid, but the plan must be returned as text through stdout while keeping `--permission-mode auto`.

## Defaults (when not explicitly specified)

| Option | Default | CLI flag |
|--------|---------|----------|
| Model | `opus` | `--model opus` |
| Effort | `medium` (calling agent escalates per request difficulty — see below) | `--effort medium` |
| Permission mode | `auto` (Claude Code decides per-tool) | `--permission-mode auto` |
| Print mode | non-interactive | `-p` |
| Output format | text | `--output-format text` |
| Working directory | caller's current `cwd` (same repo) | inherited from the shell; no `cd`, no extra `--add-dir` |
| Budget cap | none | (do NOT pass `--max-budget-usd`) |

If the user provides a different model (e.g. "sonnet에게 물어봐"), effort (e.g. "effort xhigh로"), or permission mode other than plan mode (e.g. "edits 까지 허용"), use the user-specified value and leave the rest at defaults. If the user asks for plan mode, do not pass `--permission-mode plan`; keep `--permission-mode auto` and ask Claude to return the plan in stdout.

## Effort selection guidance

The default is `medium`. The calling agent is expected to **judge the difficulty of the user's request** and raise or lower `--effort` accordingly. Pick the smallest level that fits the task — there is no benefit in burning `max` on a trivial question.

Valid levels: `low`, `medium`, `high`, `xhigh`, `max`.

| Level | Pick when the request is… | Examples |
|-------|---------------------------|----------|
| `low` | A direct factual lookup, syntax check, or one-line answer that does not need reasoning across files | "What does this regex match?", "Is this Korean translation natural?", "What's the difference between A and B in TypeScript?" |
| `medium` (default) | A normal opinion, short code review, single-file explanation, small refactor suggestion, or any "second opinion" without architectural depth | "Review this 30-line function", "Is this naming clear?", "Critique this commit message", "Is this test missing an edge case?" |
| `high` | Multi-file reasoning, design trade-off discussion, or a careful review where one wrong call has real cost | "Compare these two API designs", "Review the auth flow across these 4 files", "Is this migration plan safe?" |
| `xhigh` | Whole-subsystem or architectural reasoning, long-horizon impact analysis, or genuinely cross-cutting decisions | "Should we split this service?", "Plan a 3-step refactor that preserves behavior", "Audit this module for security and performance together" |
| `max` | The hardest end of the spectrum — ambiguous specs, deep correctness reasoning, or problems that have already resisted normal analysis | "Why is this distributed cache inconsistent under partition?", "Prove this algorithm terminates", "Reconcile these contradicting requirements" |

When the user **explicitly states an effort** (e.g. "xhigh로 물어봐", "effort max"), use that value verbatim — do not second-guess it.

When the user **does not state an effort**:

1. Start by classifying the request against the table above.
2. If it clearly fits one row, use that level.
3. If it sits between two rows, prefer the **lower** level. Escalation is cheap (the user can ask again with a higher effort); over-spending compute is not.
4. Never silently raise effort because "the model might do better" — that defeats the medium default and burns time the user did not ask for.

## Resolve the bundled script

Prefer the bundled wrapper because it encodes the defaults above, prevents `--permission-mode plan`, adds the stdout-only consultation prompt, and retries once if Claude replies only with a file-artifact notice.

Resolve the script path in this order:

1. Start from the directory that contains this `SKILL.md`.
2. Use `scripts/consult_claude_code.sh` relative to that directory.
3. If the active workspace does not contain this skill, look in the linked `common-skills/skills/consulting-claude-code/` checkout or the agent's global skill install path.

Do not assume `scripts/consult_claude_code.sh` is project-local unless the user has vendored this skill into that project.

## Canonical invocation

Spawn the wrapper from the calling agent's current `cwd`. By default that means the **same repository at the same path** the caller is already working in — no `cd`, no path override.

For a short prompt:

```bash
/path/to/consult_claude_code.sh "user prompt here"
```

For a detailed or shell-sensitive prompt, pass it through stdin:

```bash
/path/to/consult_claude_code.sh <<'PROMPT'
<user prompt verbatim>
PROMPT
```

For a repo-specific question, set the working directory only when the user explicitly named that target:

```bash
/path/to/consult_claude_code.sh --cd /absolute/path/to/repo <<'PROMPT'
<question about this repository>
PROMPT
```

Only when the **user explicitly** asks Claude to look at an additional directory alongside the current repo, scope it with `--add-dir`:

```bash
/path/to/consult_claude_code.sh --add-dir "$HOME/other-repo" <<'PROMPT'
<question that explicitly includes the extra path>
PROMPT
```

For an explicit model or effort override:

```bash
/path/to/consult_claude_code.sh --model sonnet --effort high "user prompt here"
```

When the calling agent needs to parse the response, switch the output format only:

```bash
/path/to/consult_claude_code.sh --output-format json <<'PROMPT'
<prompt>
PROMPT
```

## Console response contract

Always use the bundled wrapper when available. It wraps the user's prompt with a console-response instruction. This wrapper is not a rewrite of the user's request; it is an execution constraint that prevents Claude Code from replacing stdout with a file-artifact notice.

The wrapper sends this constraint before the user's prompt:

```text
Return the complete answer directly in stdout.
Do not create, write, or update files as the answer artifact for this consultation.
Do not respond only by saying that you wrote a plan, report, markdown file, or other artifact.
If a plan, report, diff, checklist, or markdown document would be useful, include its full contents in this stdout response instead.
```

If Claude still replies only with a file path or a message like "I wrote the plan to ...", the wrapper retries once with the same user prompt and an explicit "print the full answer now" correction. Do not inspect or summarize a generated plan file as a substitute for stdout unless the user explicitly asks you to read that file.

## Host sandbox and session recovery

Some harnesses run shell commands in a sandbox even when the target CLI itself is not sandboxed. This can make Claude Code look logged out or disconnected because it cannot read its normal credentials, use browser auth, or access session files.

Treat these as auth/session symptoms:

- `session revoked`
- `session expired`
- `logged out`
- `authentication required`
- repeated login or browser-auth prompts
- auth works in a normal terminal but fails from the agent harness

Rules:

1. If the current user request asks to consult Claude, verify Claude, authenticate Claude, or run Claude analysis, that request is permission to use the host's explicit unsandboxed/escalated execution path for the wrapper's `claude` subprocess. Do not ask a second natural-language confirmation, but do use the host tool's approval mechanism when it requires one.
2. In Codex, run the wrapper with `sandbox_permissions="require_escalated"`. The justification should say that Claude Code needs normal local auth/browser/session access.
3. For authentication/session recovery, avoid sending repository context first. Run the wrapper's neutral auth smoke from `/private/tmp`:

```bash
/path/to/consult_claude_code.sh --auth-smoke
```

4. If the host supports an interactive TTY and Claude opens or prompts for browser login, let the user complete login/consent in the browser.
5. If auth smoke succeeds, retry the original Claude consultation once outside the host sandbox from the intended working directory.
6. If the outside-sandbox retry still says the session is revoked/expired/logged out, stop and surface the exact error. The user likely needs to complete Claude Code login or account recovery outside the agent flow.
7. Outside the host sandbox does not mean `--permission-mode bypassPermissions`. Keep Claude Code's own permission mode at `auto` unless the user explicitly asked for another mode.

## Waiting policy

Response time scales with `--effort`. Rough expectations on `opus`:

- `low` / `medium`: typically seconds to a few minutes
- `high`: a few minutes
- `xhigh`: regularly 5–30 minutes, occasionally longer
- `max`: can run longer than `xhigh`; treat any duration as normal until the process exits

Rules regardless of level:

- Do not set a short shell timeout. If the shell environment imposes one, set it generously (e.g. 2 hours for `xhigh`/`max`) or run the command in the background and poll status rather than killing it.
- If the process is still running, keep waiting. Slow ≠ stuck.
- Only treat the call as failed if `claude` exits with a non-zero status, prints a hard authentication or quota error, or the user explicitly cancels.
- Do not start a second `claude` call to "speed it up" while the first is still running.

If the run is happening inside a host that does need a heartbeat, prefer launching the wrapper as a background job and polling for completion rather than killing it.

## Permission mode notes

`--permission-mode auto` lets Claude Code judge each tool request on its own. This is the requested default and matches "권한은 자동 판단".

Override only when the user explicitly asks for it:

- `--permission-mode acceptEdits` — auto-accept edits Claude proposes
- `--permission-mode bypassPermissions` — only if the user explicitly opts in; warn them first since it disables permission checks entirely
- `--permission-mode dontAsk` / `default` — explicit user choice only

Do not use `--permission-mode plan` in this skill. If the user wants a plan, request a plan-shaped stdout answer while keeping `--permission-mode auto`.
Never silently upgrade to `bypassPermissions`.

## What to send back to the user

By default, surface Claude Code's response to the user as-is. Do not summarize, rewrite, or filter unless the user asked for that.

If the calling agent is going to chain the response into further reasoning (e.g. "compare your view with Claude's"), make the round-trip explicit to the user: state that you are calling `claude`, wait, then present Claude's reply before continuing.

## Quick reference

| Situation | Command shape |
|-----------|---------------|
| Default ask (same repo, same cwd) | `/path/to/consult_claude_code.sh "..."` |
| User explicitly named another repo/path | Use `--cd <path>` for a different target root, or `--add-dir <path>` if the user asked to include it alongside the current repo |
| User specified a different model | Pass `--model <model>` |
| Request is harder than "medium" | Pass `--effort high`, `--effort xhigh`, or `--effort max` per the Effort selection guidance |
| Request is trivial | Pass `--effort low` |
| User specified a different effort | Pass the user-specified effort verbatim, no second-guessing |
| User wants planning only | Keep the wrapper default `--permission-mode auto`; ask Claude to return the plan in stdout and not write a plan file |
| Caller needs structured output | Pass `--output-format json` |

## Common mistakes

| Mistake | Effect |
|---------|--------|
| Adding `--max-budget-usd` | Violates "no budget limit". The response can be truncated mid-stream. |
| Bypassing the wrapper and omitting `-p` | `claude` enters interactive mode and the subprocess hangs forever. |
| Imposing a short shell timeout (e.g. 60s) | High-effort runs (`high`/`xhigh`/`max`) never finish; the call is killed and the caller reports a false failure. |
| Silently changing the model or effort because the run feels slow | Misrepresents the consultation. Slow is expected at high effort; keep the chosen settings. |
| Defaulting to `xhigh`/`max` for every request | Wastes time and compute on trivial questions. The default is `medium` — escalate only when the request earns it. |
| Lowering effort below the user's explicit choice "to save time" | The user picked that level on purpose. Honor it. |
| Rewriting the user's prompt before sending | Loses nuance the user wanted Claude to see. Pass it verbatim, or quote it inside a wrapper sentence at most. |
| Asking Claude for a plan without the console-response wrapper | Claude Code may write a plan artifact and leave stdout with only a file notice. |
| Using `--permission-mode plan` for this skill | Plan mode can encourage file-backed planning instead of the stdout consultation the caller needs. |
| Starting nested `claude` calls from inside a Claude Code session | Causes recursive sessions and is explicitly disallowed by this skill. |
| Calling `--permission-mode bypassPermissions` without asking | Silently disables permission checks. Always confirm with the user first. |
| `cd`ing to a different directory before spawning `claude` without an explicit user instruction | Changes the repo Claude operates on. Claude must default to the caller's current repo and cwd. |
| Adding `--add-dir <somewhere>` proactively "just in case" | Expands Claude's read scope beyond what the user asked for. Pass `--add-dir` only when the user named the extra path. |
| Retrying session errors inside the host sandbox | Repeats the same broken auth environment. Use approved outside-sandbox auth smoke, then retry once. |

## Notes for the calling agent

- This skill is one-shot per request. If the user asks for an ongoing back-and-forth, run the wrapper once per turn and keep the conversation transcript on the caller side; do not try to keep `claude` interactive.
- If `claude` is not on the current process PATH, the wrapper checks `CONSULT_CLAUDE_BIN`, then `command -v claude`, then `command -v claude` through the user's login shell when `SHELL` is executable. Surface the final error if none are executable.
- The defaults (`opus` + `medium`) are deliberate. Do not swap the model away without an explicit user instruction. For effort, follow the Effort selection guidance: judge per request, prefer the lower of two adjacent levels when uncertain, and never override an explicit user choice.
- The default scope is **the caller's current repository at its current path**. Treat any other repo or path as opt-in: the user must name it explicitly before you `cd` or add it via `--add-dir`.
- If you are Claude Code, you reached this file by mistake. Stop following it — see the "Audience boundary" section above.
