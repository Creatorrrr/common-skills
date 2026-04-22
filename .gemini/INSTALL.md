# Installing common-skills for Gemini CLI

Install this repository as a Gemini CLI extension. The required extension metadata lives at the repository root in `gemini-extension.json`, and Gemini CLI loads `GEMINI.md` as the extension context.

## Prerequisites

- Gemini CLI
- Git for the managed global install mode
- An existing local `common-skills` checkout if you want to link a development copy directly

## Choose an install mode

If Gemini CLI is following this guide for a user, ask once before making changes:

- `global_install`: install the extension from GitHub and let Gemini CLI manage it
- `local_checkout`: link an existing local repository path that the user wants to edit and test directly

If the user chooses `local_checkout` and has not provided a path yet, ask for the absolute path first. Only continue once the mode and source path are clear.

## Installation

1. Install or link the extension.

   For `global_install`:

   ```bash
   gemini extensions install https://github.com/Creatorrrr/common-skills
   ```

   For `local_checkout`:

   ```bash
   LOCAL_COMMON_SKILLS=/absolute/path/to/common-skills
   test -f "$LOCAL_COMMON_SKILLS/gemini-extension.json"
   gemini extensions link "$LOCAL_COMMON_SKILLS"
   ```

2. Restart Gemini CLI so it reloads installed extensions.

## Verify

```bash
gemini extensions list
```

You should see `common-skills` in the installed extensions list. If you used `local_checkout`, Gemini CLI should treat the linked local path as the live extension source.

## Usage

After restart, start a new Gemini CLI session and use the installed extension when needed. The extension context will direct Gemini to these skill files:

- `gpt-pro-codebase-analysis`
- `claude-code-agent-team-analysis`

## Updating

For `global_install`:

```bash
gemini extensions update common-skills
```

For `local_checkout`, no separate update step is required. Changes in the linked local repository are reflected immediately.

## Uninstalling

For `global_install`:

```bash
gemini extensions uninstall common-skills
```

For `local_checkout`:

```bash
gemini extensions uninstall /absolute/path/to/common-skills
```
