# Installing common-skills for Claude Code

This repository currently ships skills, not a published Claude marketplace plugin. Install it by linking each skill from a chosen source checkout into Claude Code's personal skills directory at `~/.claude/skills`.

## Prerequisites

- Claude Code
- Git for the managed global install mode
- An existing local `common-skills` checkout if you want to link a development copy directly

## Choose an install mode

If Claude Code is following this guide for a user, ask once before making changes:

- `global_checkout`: manage a dedicated clone at `~/.claude/common-skills`
- `local_checkout`: link an existing local repository path that the user wants to edit and test directly

If the user chooses `local_checkout` and has not provided a path yet, ask for the absolute path first. Only continue once the mode and source path are clear.

## Installation

1. Prepare the source checkout you are going to link.

   For `global_checkout`:

   ```bash
   if [ -d ~/.claude/common-skills/.git ]; then
     git -C ~/.claude/common-skills pull
   else
     git clone https://github.com/Creatorrrr/common-skills.git ~/.claude/common-skills
   fi
   ```

   For `local_checkout`:

   ```bash
   LOCAL_COMMON_SKILLS=/absolute/path/to/common-skills
   test -d "$LOCAL_COMMON_SKILLS/skills"
   ```

2. Link the selected skill directories into Claude's global skills directory.

   For `global_checkout`:

   ```bash
   mkdir -p ~/.claude/skills
   for skill_dir in ~/.claude/common-skills/skills/*; do
     skill_name="$(basename "$skill_dir")"
     rm -f ~/.claude/skills/"$skill_name"
     ln -s "$skill_dir" ~/.claude/skills/"$skill_name"
   done
   ```

   For `local_checkout`:

   ```bash
   mkdir -p ~/.claude/skills
   for skill_dir in "$LOCAL_COMMON_SKILLS"/skills/*; do
     skill_name="$(basename "$skill_dir")"
     rm -f ~/.claude/skills/"$skill_name"
     ln -s "$skill_dir" ~/.claude/skills/"$skill_name"
   done
   ```

3. Restart Claude Code so it reloads the global skills directory.

## Verify

```bash
readlink ~/.claude/skills/gpt-pro-codebase-analysis
readlink ~/.claude/skills/claude-code-agent-team-analysis
```

You should see paths pointing into the selected source checkout, either under `~/.claude/common-skills/skills` or under your chosen local repository path.

## Usage

After restart, Claude Code can discover the skills automatically when the task matches the skill descriptions. You can also name them directly:

- `gpt-pro-codebase-analysis`
- `claude-code-agent-team-analysis`

## Updating

For `global_checkout`:

```bash
git -C ~/.claude/common-skills pull
```

For `local_checkout`, update the repository you linked instead, for example:

```bash
git -C /absolute/path/to/common-skills pull
```

If you linked your active development checkout, Claude Code sees file changes immediately through the symlinks as soon as they are saved.

## Uninstalling

For either install mode, remove the exposed skill links:

```bash
for skill_name in gpt-pro-codebase-analysis claude-code-agent-team-analysis; do
  rm -f ~/.claude/skills/"$skill_name"
done
```

If you used `global_checkout` and no longer want the managed clone:

```bash
rm -rf ~/.claude/common-skills
```

If you used `local_checkout`, keep or remove that repository separately based on what the user asked for.
