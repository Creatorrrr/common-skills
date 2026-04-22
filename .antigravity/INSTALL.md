# Installing common-skills for Antigravity

Enable these skills in Antigravity via native skill discovery by linking a `skills/` directory into `~/.gemini/antigravity/skills`, then restart Antigravity.

## Prerequisites

- Antigravity
- Git for the managed global install mode
- An existing local `common-skills` checkout if you want to link a development copy directly

## Choose an install mode

If Antigravity is following this guide for a user, ask once before making changes:

- `global_checkout`: manage a dedicated clone at `~/.gemini/antigravity/common-skills`
- `local_checkout`: link an existing local repository path that the user wants to edit and test directly

If the user chooses `local_checkout` and has not provided a path yet, ask for the absolute path first. Only continue once the mode and source path are clear.

## Installation

1. Prepare the source checkout you are going to link.

   For `global_checkout`:

   ```bash
   if [ -d ~/.gemini/antigravity/common-skills/.git ]; then
     git -C ~/.gemini/antigravity/common-skills pull
   else
     git clone https://github.com/Creatorrrr/common-skills.git ~/.gemini/antigravity/common-skills
   fi
   ```

   For `local_checkout`:

   ```bash
   LOCAL_COMMON_SKILLS=/absolute/path/to/common-skills
   test -d "$LOCAL_COMMON_SKILLS/skills"
   ```

2. Expose the selected checkout to Antigravity.

   For `global_checkout`:

   ```bash
   mkdir -p ~/.gemini/antigravity/skills
   rm -f ~/.gemini/antigravity/skills/common-skills
   ln -s ~/.gemini/antigravity/common-skills/skills ~/.gemini/antigravity/skills/common-skills
   ```

   For `local_checkout`:

   ```bash
   mkdir -p ~/.gemini/antigravity/skills
   rm -f ~/.gemini/antigravity/skills/common-skills
   ln -s "$LOCAL_COMMON_SKILLS/skills" ~/.gemini/antigravity/skills/common-skills
   ```

3. Restart Antigravity so it re-scans the global skills directory.

## Verify

```bash
readlink ~/.gemini/antigravity/skills/common-skills
```

You should see the selected source path ending in `/skills`, for example `~/.gemini/antigravity/common-skills/skills` or your chosen local checkout path.

## Usage

After restart, Antigravity can discover these skills automatically. You can also call them explicitly with the namespace created by the symlink name:

- `common-skills:gpt-pro-codebase-analysis`
- `common-skills:claude-code-agent-team-analysis`

## Updating

For `global_checkout`:

```bash
git -C ~/.gemini/antigravity/common-skills pull
```

For `local_checkout`, update the repository you linked instead, for example:

```bash
git -C /absolute/path/to/common-skills pull
```

If you linked your active development checkout, Antigravity sees file changes immediately through the symlink as soon as they are saved.

## Uninstalling

```bash
rm ~/.gemini/antigravity/skills/common-skills
```

If you used `global_checkout` and no longer want the managed clone:

```bash
rm -rf ~/.gemini/antigravity/common-skills
```

If you used `local_checkout`, keep or remove that repository separately based on what the user asked for.
