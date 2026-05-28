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

If the user provides a different model (e.g. "sonnet에게 물어봐"), effort (e.g. "effort xhigh로"), or permission mode (e.g. "plan 모드로", "edits 까지 허용"), use the user-specified value and leave the rest at defaults.

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

## Canonical invocation

Spawn `claude` from the calling agent's current `cwd`. By default that means the **same repository at the same path** the caller is already working in — no `cd`, no path override.

```bash
claude -p "<user prompt verbatim>" \
  --model opus \
  --effort medium \
  --permission-mode auto \
  --output-format text
```

Only when the **user explicitly** asks Claude to look at a different or additional repository, scope it with `--add-dir` (or, if the user named a different root, change `cwd` to that root before spawning):

```bash
# User said: "이 경로도 같이 봐줘: ~/other-repo"
claude -p "<prompt>" \
  --model opus \
  --effort medium \
  --permission-mode auto \
  --output-format text \
  --add-dir "$HOME/other-repo"
```

When the calling agent needs to parse the response, switch the output format only — never strip the defaults above:

```bash
claude -p "<prompt>" \
  --model opus \
  --effort medium \
  --permission-mode auto \
  --output-format json
```

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

1. If the current user request asks to consult Claude, verify Claude, authenticate Claude, or run Claude analysis, that request is permission to use the host's explicit unsandboxed/escalated execution path for the `claude` subprocess. Do not ask a second natural-language confirmation, but do use the host tool's approval mechanism when it requires one.
2. In Codex, run `claude` with `sandbox_permissions="require_escalated"`. The justification should say that Claude Code needs normal local auth/browser/session access.
3. For authentication/session recovery, avoid sending repository context first. Run a neutral auth smoke from `/private/tmp`:

```bash
cd /private/tmp
claude -p "Reply exactly with: claude-auth-ok" \
  --model opus \
  --effort low \
  --permission-mode plan \
  --output-format text
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
| Default ask (same repo, same cwd) | `claude -p "..." --model opus --effort medium --permission-mode auto --output-format text` (spawn from caller's cwd; no `--add-dir`) |
| User explicitly named another repo/path | Either `cd` to that root before spawning, or add `--add-dir <path>` if the user asked to include it alongside the current repo |
| User specified a different model | Replace `--model opus` with the requested model alias or full ID |
| Request is harder than "medium" | Raise `--effort` to `high`, `xhigh`, or `max` per the Effort selection guidance |
| Request is trivial | Lower `--effort` to `low` |
| User specified a different effort | Use the user-specified level verbatim, no second-guessing |
| User wants planning only | Replace `--permission-mode auto` with `--permission-mode plan` |
| Caller needs structured output | Replace `--output-format text` with `--output-format json` |

## Common mistakes

| Mistake | Effect |
|---------|--------|
| Adding `--max-budget-usd` | Violates "no budget limit". The response can be truncated mid-stream. |
| Omitting `-p` | `claude` enters interactive mode and the subprocess hangs forever. |
| Imposing a short shell timeout (e.g. 60s) | High-effort runs (`high`/`xhigh`/`max`) never finish; the call is killed and the caller reports a false failure. |
| Silently changing the model or effort because the run feels slow | Misrepresents the consultation. Slow is expected at high effort; keep the chosen settings. |
| Defaulting to `xhigh`/`max` for every request | Wastes time and compute on trivial questions. The default is `medium` — escalate only when the request earns it. |
| Lowering effort below the user's explicit choice "to save time" | The user picked that level on purpose. Honor it. |
| Rewriting the user's prompt before sending | Loses nuance the user wanted Claude to see. Pass it verbatim, or quote it inside a wrapper sentence at most. |
| Starting nested `claude` calls from inside a Claude Code session | Causes recursive sessions and is explicitly disallowed by this skill. |
| Calling `--permission-mode bypassPermissions` without asking | Silently disables permission checks. Always confirm with the user first. |
| `cd`ing to a different directory before spawning `claude` without an explicit user instruction | Changes the repo Claude operates on. Claude must default to the caller's current repo and cwd. |
| Adding `--add-dir <somewhere>` proactively "just in case" | Expands Claude's read scope beyond what the user asked for. Pass `--add-dir` only when the user named the extra path. |
| Retrying session errors inside the host sandbox | Repeats the same broken auth environment. Use approved outside-sandbox auth smoke, then retry once. |

## Notes for the calling agent

- This skill is one-shot per request. If the user asks for an ongoing back-and-forth, run `claude -p ...` once per turn and keep the conversation transcript on the caller side; do not try to keep `claude` interactive.
- If `claude` is not on PATH, surface the error to the user rather than guessing an install location. The user keeps `claude` at the binary returned by `which claude`.
- The defaults (`opus` + `medium`) are deliberate. Do not swap the model away without an explicit user instruction. For effort, follow the Effort selection guidance: judge per request, prefer the lower of two adjacent levels when uncertain, and never override an explicit user choice.
- The default scope is **the caller's current repository at its current path**. Treat any other repo or path as opt-in: the user must name it explicitly before you `cd` or add it via `--add-dir`.
- If you are Claude Code, you reached this file by mistake. Stop following it — see the "Audience boundary" section above.
