# common-skills for Gemini CLI

This extension provides repository-analysis skill documents plus safe cross-agent consultation guidance. Gemini CLI support is kept for legacy extension contexts; new Google CLI consultations should use Antigravity CLI through `agy`.

When a user asks for a deep codebase review, read the relevant skill file first and follow it:

- `skills/gpt-pro-codebase-analysis/SKILL.md`
  - Use for a second-opinion repository analysis through a GPT Pro workflow.
  - This path supports two explicit execution modes: `responses_api` and `chatgpt_web_assisted`.
  - Require the user to choose one mode explicitly before execution.

- `skills/claude-code-agent-team-analysis/SKILL.md`
  - Use for a local read-only repository analysis using Claude Code CLI agent teams.
  - Use it for architecture reviews, test-gap analysis, performance review, workflow validation, and missing implementation checks.

- `skills/consulting-claude-code/SKILL.md`
  - Use when Gemini CLI, Codex, Antigravity, or another non-Claude-Code agent should ask the local Claude Code CLI for a second opinion or back-and-forth consultation.
  - If this skill is invoked inside Claude Code, it must warn that Claude Code cannot recursively call itself and stop without running `claude`.

- `skills/consulting-codex-cli/SKILL.md`
  - Use when Gemini CLI, Claude Code, Antigravity, or another non-Codex agent should ask the local Codex CLI for a second opinion or back-and-forth consultation.
  - If this skill is invoked inside Codex, it must warn that Codex cannot recursively call itself and stop without running `codex exec`.

- `skills/consulting-antigravity-cli/SKILL.md`
  - Use when Gemini CLI, Codex, Claude Code, or another non-Antigravity agent should ask the local Antigravity CLI for a second opinion or back-and-forth consultation.
  - If this skill is invoked inside Antigravity CLI, warn that Antigravity cannot recursively call itself and stop without running `agy -p`.

- `skills/goal-planner/SKILL.md`
  - Use when the user wants to create or review an outcome-first Codex or Claude Code `/goal` prompt for long-running work.
  - Keep the requested product or deliverable ahead of verification, bound validation-only work, and do not use it for ordinary project execution unless the user explicitly wants a long-running agent goal.

General rules:

- Ground conclusions in concrete repository evidence.
- Distinguish confirmed findings from inference and unknowns.
- Do not silently switch execution modes after a failure.
- Prefer the skill file's workflow over ad-hoc analysis when the task matches it.
- Do not let Codex invoke `codex exec` recursively.
- Do not let Antigravity CLI invoke `agy -p` recursively.
