---
name: consulting-gemini-cli
description: Use when a non-Gemini agent wants to consult the local Gemini CLI for a second opinion, cross-agent dialogue, code review, design feedback, or "ask Gemini" request. Triggers include phrases like "gemini한테 물어봐", "gemini 의견", "Gemini와 cross-check", "ask gemini", "consult gemini", or any request to invoke `gemini -p`. If invoked from inside Gemini CLI, warn that Gemini cannot recursively call itself and stop.
---

# Consulting Gemini CLI

This skill lets Codex, Claude Code, Antigravity, or another non-Gemini agent invoke the local `gemini` CLI as a subprocess, collect Gemini's opinion, and compare it with the calling agent's own reasoning.

Gemini CLI sessions must not use this skill to invoke `gemini -p`. If the current agent is Gemini CLI and this skill is triggered, respond with a warning and stop.

## Core principles

1. The user's explicit instructions override these defaults.
2. If the current agent is Gemini CLI, say: `Gemini cannot use consulting-gemini-cli because it would recursively call Gemini. I will not run gemini -p from inside Gemini CLI.` Then stop.
3. Run Gemini non-interactively with `gemini -p` / `gemini --prompt` so the subprocess returns.
4. If the user does not specify a model, use the Gemini CLI default by omitting `--model`. The wrapper accepts convenience aliases `pro`, `flash`, `lite`, and `flash-lite` for explicit overrides.
5. Use YOLO approval mode by default: `--approval-mode=yolo`. This auto-approves Gemini CLI tool calls so it can inspect repositories directly in non-interactive consultations.
6. Do not pass token, budget, output-token, or thinking-budget caps.
7. Long waits are normal for large repositories or Pro-model reasoning. Do not impose short shell timeouts or retry just because output is slow.
8. Pass the user's prompt faithfully. Preserve constraints, paths, language, and requested output shape.
9. Present Gemini's response before synthesizing agreement or disagreement.
10. Unless the user explicitly says otherwise, Gemini operates on the same repository at the same working directory as the calling agent.
11. If the calling harness runs shell commands in a host sandbox, run real Gemini CLI calls through that harness's explicit unsandboxed/escalated execution path after user approval. Sandboxed calls can hide CLI auth state, browser integration, or normal home-directory session files.

## Resolve the bundled script

Prefer the bundled wrapper because it encodes the defaults above and avoids retyping CLI flags.

Resolve the script path in this order:

1. Start from the directory that contains this `SKILL.md`.
2. Use `scripts/consult_gemini_cli.sh` relative to that directory.
3. If the active workspace does not contain this skill, look in the installed skill location such as `~/.claude/skills/consulting-gemini-cli/`, the linked `common-skills/skills/consulting-gemini-cli/`, or the agent's global skill install path.

Do not assume `scripts/consult_gemini_cli.sh` is project-local unless the user has vendored this skill into that project.

## Defaults

| Option | Default | How it is passed |
| --- | --- | --- |
| Model | Gemini CLI default | no `--model` argument |
| Approval mode | `yolo` | `--approval-mode=yolo` |
| Print mode | non-interactive | `-p` / `--prompt` |
| Output format | `text` | `--output-format text` |
| Workspace trust | Gemini CLI default | no trust flag |
| Working directory | caller's current `cwd` | inherited unless `--cd` is explicitly used |
| Extra directories | none | do not pass `--include-directories` unless the user names extra paths |
| Sandbox | Gemini CLI default | do not pass `--sandbox` unless the user asks |
| Budget/token caps | none | do not pass any cap flags |

If the user explicitly names another model, approval mode, working directory, output format, sandbox setting, or extra include directory, use that value and keep the remaining defaults.

Model aliases accepted by the wrapper:

- `pro` -> `gemini-2.5-pro`
- `flash` -> `gemini-2.5-flash`
- `lite` or `flash-lite` -> `gemini-2.5-flash-lite`
- `default` or `cli-default` -> omit `--model` and let Gemini CLI choose

## Canonical invocation

For a short prompt:

```bash
/path/to/consult_gemini_cli.sh "user prompt here"
```

For a detailed or shell-sensitive prompt, pass it through stdin:

```bash
/path/to/consult_gemini_cli.sh <<'PROMPT'
<user prompt verbatim>
PROMPT
```

For a repo-specific question, set the working directory:

```bash
/path/to/consult_gemini_cli.sh --cd /absolute/path/to/repo <<'PROMPT'
<question about this repository>
PROMPT
```

For an explicit model override:

```bash
/path/to/consult_gemini_cli.sh --model gemini-2.5-flash "user prompt here"
```

Short aliases such as `--model flash` are also supported by the wrapper, but exact Gemini model IDs are preferred in examples because Gemini CLI itself does not treat bare `pro` or `flash` as model aliases.

For an explicit lower-permission request, use the user's requested approval mode:

```bash
/path/to/consult_gemini_cli.sh --approval-mode plan <<'PROMPT'
<user explicitly requested read-only planning>
PROMPT
```

Use `--approval-mode plan`, `default`, or `auto_edit` only when the user explicitly asks for a lower-permission posture than the default. If the installed Gemini CLI does not support `plan`, the wrapper maps that explicit lower-permission request to `default` and prints a status note before running Gemini.

## Image and media file analysis

Gemini models can analyze images, but this wrapper does not automatically forward image attachments from the calling chat UI. The wrapper sends text to `gemini -p`; Gemini CLI only receives local image content when the prompt uses Gemini CLI file-context syntax.

Rules for image, audio, video, and PDF analysis:

1. Resolve the real local filesystem path first. Do not assume a chat attachment, Markdown image, or plain path string is available to the Gemini subprocess.
2. Use `@path` syntax in the prompt for every media file Gemini must inspect. A plain path such as `/tmp/image.png` is only text; `@image.png` is file context.
3. Prefer `--cd` to a directory that contains the media file, then reference the file with a relative `@` path:

```bash
/path/to/consult_gemini_cli.sh --cd /absolute/path/to/images <<'PROMPT'
Analyze this image: @image.png
PROMPT
```

4. Escape spaces and shell-sensitive characters inside the `@` path. For example:

```text
Analyze this image: @generated\ image\ 1.png
```

5. If the media file is outside the consultation working directory, only use `--include-dir` when the user explicitly named that extra path. Then reference a path that Gemini CLI can resolve inside the configured workspace.
6. Do not rely on `@directory/` to include images. Gemini CLI's multi-file reader is primarily text-oriented and may skip image, audio, video, or PDF files unless their exact file name or extension is explicitly requested. For visual analysis, name each image directly: `@a.png @b.jpg`.
7. If Gemini says it cannot see or analyze the image, inspect the invocation before blaming the model: check that the prompt used `@`, the file existed, spaces were escaped, the path was inside Gemini's workspace/include directories, and the file was not ignored by `.gitignore` or `.geminiignore`.
8. If headless Gemini rejects the image directory as untrusted, do not silently retry with a broader trust scope. Surface the error unless the user's current request explicitly asks to analyze that local image path; in that case, use the installed CLI's documented trust bypass only for that run when available, and state that the media directory is being trusted for the consultation.

For a quick visual smoke, ask Gemini to prove it received the image:

```bash
/path/to/consult_gemini_cli.sh --cd /absolute/path/to/images <<'PROMPT'
Look at @image.png. Start your answer with VISUAL_OK if you can see it, or VISUAL_NOT_AVAILABLE if you cannot. Then summarize the visible subject in one sentence.
PROMPT
```

## Browser authentication flow

Gemini CLI may require browser authentication before the first real `gemini -p` call can complete. If the command prints an auth prompt such as `Opening authentication page in your browser. Do you want to continue? [Y/n]:`, do not leave a non-interactive subprocess hanging.

Rules:

1. Make the risk explicit: this opens a browser login/consent flow for the local Gemini CLI, and a real Gemini request goes to an external Google service.
2. If the current user request already asks to consult Gemini, verify Gemini, authenticate Gemini, or open the Gemini auth page, do not ask a second "open the browser?" confirmation. State that auth smoke is starting and proceed.
3. Only ask before opening the browser when Gemini auth is incidental and the user has not asked for a real Gemini CLI call in the current turn.
4. For authentication, avoid sending repository context. Run the bundled wrapper's auth smoke mode from a neutral temp directory:

```bash
/path/to/consult_gemini_cli.sh --auth-smoke
```

The wrapper uses this minimal prompt:

```text
Reply exactly with: gemini-auth-ok
```

5. If the host supports an interactive TTY and Gemini prints the browser-auth prompt, answer `Y` so the authentication page opens for the user. The user completes login/consent in the browser.
6. If the host cannot provide a TTY or cannot open a browser, give the user the manual command instead:

```bash
cd /private/tmp
gemini -p "Reply exactly with: gemini-auth-ok" --approval-mode=yolo --output-format text
```

7. After auth smoke succeeds, rerun the original consultation prompt from the intended working directory.

Never start browser authentication from the repository directory with the real consultation prompt just to solve auth. Authenticate first with the neutral smoke prompt, then run the real consultation separately.

## Host sandbox and session recovery

Some harnesses run shell commands in a sandbox even when the target CLI itself is not sandboxed. This can make Gemini CLI look logged out or disconnected because it cannot read its normal credentials, use browser auth, or access session files.

Treat these as auth/session symptoms:

- `session revoked`
- `session expired`
- `logged out`
- `authentication required`
- repeated browser-auth prompts
- auth works in a normal terminal but fails from the agent harness

Rules:

1. If the current user request asks to consult Gemini, verify Gemini, authenticate Gemini, or run Gemini analysis, that request is permission to use the host's explicit unsandboxed/escalated execution path for the Gemini CLI subprocess. Do not ask a second natural-language confirmation, but do use the host tool's approval mechanism when it requires one.
2. In Codex, run the wrapper with `sandbox_permissions="require_escalated"` for both `--auth-smoke` and the real consultation. The justification should say that Gemini CLI needs normal local auth/browser/session access.
3. Use the same intended working directory rules as usual: `--auth-smoke` runs from `/private/tmp`; the real consultation runs from the caller's current `cwd` unless the user named another path.
4. If a sandboxed attempt fails with an auth/session symptom, stop that run. Do not keep retrying inside the sandbox.
5. Run one outside-sandbox `--auth-smoke` first. If it succeeds, retry the original Gemini consultation once outside the host sandbox.
6. If the outside-sandbox retry still says the session is revoked/expired/logged out, stop and surface the exact error. The user likely needs to complete Gemini CLI login or account recovery outside the agent flow.
7. Outside the host sandbox does not change Gemini CLI's own approval mode. Keep the wrapper default `yolo` unless the user explicitly asked for another mode.

## Waiting policy

Gemini CLI default or Pro-model runs can take many minutes on large or cross-cutting questions. Treat that as normal.

- Set a generous shell timeout. Use at least `3600000` ms when the host tool requires a timeout value.
- If the process is still running and there is no hard error, continue waiting.
- Do not launch duplicate Gemini consultations to speed up a slow run.
- Only treat the call as failed if `gemini` exits non-zero, reports authentication or quota failure, or the user cancels.

## Permission policy

Default to direct repository inspection:

```bash
--approval-mode=yolo
```

YOLO mode auto-approves Gemini CLI tool calls, including shell commands. This is deliberately less restrictive than plan mode so non-interactive consultations can read repositories directly without stopping on shell approval. Override only when the user explicitly asks for a different posture:

- `--approval-mode=plan` - read-only planning mode; can block shell-based repository inspection in non-interactive runs.
- `--approval-mode=default` - Gemini prompts for tool approvals; in non-interactive runs, approval prompts can become denials.
- `--approval-mode=auto_edit` - Gemini may auto-approve edit tools while prompting for other tools.
- `--approval-mode=yolo` - Gemini auto-approves all tool calls. This is this skill's default.

Do not use deprecated `--yolo`; use `--approval-mode=yolo`. Some Gemini CLI versions do not support `plan`; the wrapper maps an explicit `plan` request to `default` only when `plan` is unavailable.

## How to use Gemini's response

Default behavior:

1. Run your own initial analysis enough to know what you are asking Gemini.
2. Invoke Gemini with the user's prompt and any necessary repo paths.
3. Show Gemini's response or a faithful summary, depending on the user's request.
4. Compare Gemini's answer with your own assessment.
5. If there is disagreement, state the disagreement and the evidence needed to resolve it.

Do not claim consensus unless both agents reached the same conclusion for compatible reasons.

## Common mistakes

| Mistake | Why it is wrong |
| --- | --- |
| Running `gemini -p` from Gemini CLI | Recursive. Warn and stop instead. |
| Omitting `-p` / `--prompt` | Can start an interactive session that never returns. |
| Adding token, thinking, or budget caps | Can truncate or weaken the consultation. |
| Using a short timeout | Pro-model runs may be killed before they finish. |
| Lowering the model because the run is slow | Changes the requested consultation quality without user approval. |
| Assuming `yolo` is read-only | It auto-approves tool calls, including shell commands. Use `--approval-mode plan` or `default` explicitly for read-only-only consultations. |
| Adding `--include-directories` proactively | Expands Gemini's read scope beyond what the user asked for. |
| Assuming chat image attachments are forwarded automatically | The wrapper only sends text to `gemini -p`; use local `@image.png` file context. |
| Passing a media path without `@` | Gemini receives a path string, not the image/audio/video/PDF content. |
| Using `@directory/` and expecting images inside it to be analyzed | Gemini CLI may skip binary assets unless each media file is explicitly named. |
| Forgetting to escape spaces in `@` paths | The at-command parser stops at unescaped whitespace, so Gemini may read the wrong path or no file. |
| Opening browser auth with the real repo prompt | Sends more context than needed for login. Use `--auth-smoke` first. |
| Retrying session errors inside the host sandbox | Repeats the same broken auth environment. Use approved outside-sandbox auth smoke, then retry once. |
| Hiding Gemini disagreement | The user asked for cross-agent judgment, not artificial consensus. |

## Notes for the calling agent

- This skill is one-shot per request. If the user asks for an ongoing back-and-forth, run `gemini -p ...` once per turn and keep the conversation transcript on the caller side.
- If `gemini` is not on the current process PATH, the wrapper checks `CONSULT_GEMINI_BIN`, then `command -v gemini`, then `command -v gemini` through the user's login shell when `SHELL` is executable. Surface the final error if none are executable.
- The default scope is the caller's current repository at its current path. Treat any other repo or path as opt-in: the user must name it explicitly before you `cd` or pass `--include-directories`.
- If you are Gemini CLI, you reached this file by mistake. Stop following it and answer using your own reasoning.
