# Installing common-skills for Gemini CLI

Install this repository as a Gemini CLI extension. The required extension metadata lives at the repository root in `gemini-extension.json`, and Gemini CLI loads `GEMINI.md` as the extension context.

## Prerequisites

- Gemini CLI
- Git

## Installation

1. Install the extension from GitHub.

   ```bash
   gemini extensions install https://github.com/Creatorrrr/common-skills
   ```

2. Restart Gemini CLI so it reloads installed extensions.

## Verify

```bash
gemini extensions list
```

You should see `common-skills` in the installed extensions list.

## Usage

After restart, start a new Gemini CLI session and use the installed extension when needed. The extension context will direct Gemini to these skill files:

- `gpt-5.4-pro-codebase-analysis`
- `claude-code-agent-team-analysis`

## Updating

```bash
gemini extensions update common-skills
```

## Uninstalling

```bash
gemini extensions uninstall common-skills
```
