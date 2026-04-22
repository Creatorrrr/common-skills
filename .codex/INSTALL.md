# Installing common-skills for Codex

Enable these skills in Codex via native skill discovery by linking a `skills/` directory into `~/.agents/skills`, then restart Codex.

## Prerequisites

- Codex
- Git for the managed global install mode
- An existing local `common-skills` checkout if you want to link a development copy directly

## Choose an install mode

If Codex is following this guide for a user, ask once before making changes:

- `global_checkout`: manage a dedicated clone at `~/.codex/common-skills`
- `local_checkout`: link an existing local repository path that the user wants to edit and test directly

If the user chooses `local_checkout` and has not provided a path yet, ask for the absolute path first. Only continue once the mode and source path are clear.

## Installation

1. Prepare the source checkout you are going to link.

   For `global_checkout`:

   ```bash
   if [ -d ~/.codex/common-skills/.git ]; then
     git -C ~/.codex/common-skills pull
   else
     git clone https://github.com/Creatorrrr/common-skills.git ~/.codex/common-skills
   fi
   ```

   For `local_checkout`:

   ```bash
   LOCAL_COMMON_SKILLS=/absolute/path/to/common-skills
   test -d "$LOCAL_COMMON_SKILLS/skills"
   ```

2. Expose the selected checkout to Codex.

   For `global_checkout`:

   ```bash
   mkdir -p ~/.agents/skills
   rm -f ~/.agents/skills/common-skills
   ln -s ~/.codex/common-skills/skills ~/.agents/skills/common-skills
   ```

   For `local_checkout`:

   ```bash
   mkdir -p ~/.agents/skills
   rm -f ~/.agents/skills/common-skills
   ln -s "$LOCAL_COMMON_SKILLS/skills" ~/.agents/skills/common-skills
   ```

3. Restart Codex so it re-scans the global skills directory.

## Verify

```bash
readlink ~/.agents/skills/common-skills
```

You should see the selected source path ending in `/skills`, for example `~/.codex/common-skills/skills` or your chosen local checkout path.

## Usage

After restart, Codex can discover these skills automatically. You can also call them explicitly with the namespace created by the symlink name:

- `common-skills:gpt-pro-codebase-analysis`
- `common-skills:claude-code-agent-team-analysis`

## Updating

For `global_checkout`:

```bash
git -C ~/.codex/common-skills pull
```

For `local_checkout`, update the repository you linked instead, for example:

```bash
git -C /absolute/path/to/common-skills pull
```

If you linked your active development checkout, Codex sees file changes immediately through the symlink as soon as they are saved.

## Uninstalling

```bash
rm ~/.agents/skills/common-skills
```

If you used `global_checkout` and no longer want the managed clone:

```bash
rm -rf ~/.codex/common-skills
```

If you used `local_checkout`, keep or remove that repository separately based on what the user asked for.
