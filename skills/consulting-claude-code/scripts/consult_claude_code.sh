#!/usr/bin/env bash
set -euo pipefail

DEFAULT_CLAUDE_MODEL="opus"
DEFAULT_CLAUDE_EFFORT="medium"
DEFAULT_CLAUDE_PERMISSION_MODE="auto"
DEFAULT_CLAUDE_OUTPUT_FORMAT="text"

usage() {
  cat <<'USAGE'
Usage:
  consult_claude_code.sh [--model MODEL] [--effort LEVEL] [--permission-mode MODE] [--output-format FORMAT] [--cd DIR] [--add-dir DIR] [request...]
  consult_claude_code.sh --auth-smoke
  consult_claude_code.sh [options] < prompt.md

Defaults:
  --model             opus
  --effort            medium
  --permission-mode   auto
  --output-format     text
  --cd                current directory

This wrapper intentionally does not set budget caps and intentionally does not
use Claude Code's plan permission mode. Planning requests are returned through
stdout while keeping --permission-mode auto.
USAGE
}

neutral_auth_dir="/tmp"
if [[ -d /private/tmp ]]; then
  neutral_auth_dir="/private/tmp"
fi

model="${CONSULT_CLAUDE_MODEL:-${CLAUDE_MODEL:-$DEFAULT_CLAUDE_MODEL}}"
effort="${CONSULT_CLAUDE_EFFORT:-$DEFAULT_CLAUDE_EFFORT}"
permission_mode="${CONSULT_CLAUDE_PERMISSION_MODE:-$DEFAULT_CLAUDE_PERMISSION_MODE}"
output_format="${CONSULT_CLAUDE_OUTPUT_FORMAT:-$DEFAULT_CLAUDE_OUTPUT_FORMAT}"
workdir="${CONSULT_CLAUDE_WORKDIR:-$PWD}"
auth_smoke=false
add_dirs=()
prompt_args=()

while (($#)); do
  case "$1" in
    -h|--help)
      usage
      exit 0
      ;;
    -m|--model)
      if (($# < 2)); then
        echo "Missing value for $1" >&2
        exit 64
      fi
      model="$2"
      shift 2
      ;;
    --model=*)
      model="${1#*=}"
      shift
      ;;
    --effort)
      if (($# < 2)); then
        echo "Missing value for $1" >&2
        exit 64
      fi
      effort="$2"
      shift 2
      ;;
    --effort=*)
      effort="${1#*=}"
      shift
      ;;
    --permission-mode)
      if (($# < 2)); then
        echo "Missing value for $1" >&2
        exit 64
      fi
      permission_mode="$2"
      shift 2
      ;;
    --permission-mode=*)
      permission_mode="${1#*=}"
      shift
      ;;
    -o|--output-format)
      if (($# < 2)); then
        echo "Missing value for $1" >&2
        exit 64
      fi
      output_format="$2"
      shift 2
      ;;
    --output-format=*)
      output_format="${1#*=}"
      shift
      ;;
    -C|--cd|--workdir)
      if (($# < 2)); then
        echo "Missing value for $1" >&2
        exit 64
      fi
      workdir="$2"
      shift 2
      ;;
    --cd=*|--workdir=*)
      workdir="${1#*=}"
      shift
      ;;
    --add-dir)
      if (($# < 2)); then
        echo "Missing value for $1" >&2
        exit 64
      fi
      add_dirs+=("$2")
      shift 2
      ;;
    --add-dir=*)
      add_dirs+=("${1#*=}")
      shift
      ;;
    --auth-smoke|--auth-check)
      auth_smoke=true
      workdir="${CONSULT_CLAUDE_AUTH_WORKDIR:-$neutral_auth_dir}"
      shift
      ;;
    --)
      shift
      prompt_args+=("$@")
      break
      ;;
    *)
      prompt_args+=("$1")
      shift
      ;;
  esac
done

if ! command -v claude >/dev/null 2>&1; then
  echo "claude CLI is not on PATH" >&2
  exit 127
fi

if [[ ! -d "$workdir" ]]; then
  echo "Working directory does not exist: $workdir" >&2
  exit 66
fi

if [[ "$permission_mode" == "plan" ]]; then
  echo "consulting-claude-code does not use --permission-mode plan; using auto instead." >&2
  permission_mode="auto"
fi

stdin_prompt=""
if [[ ! -t 0 ]]; then
  stdin_prompt="$(cat)"
fi

argument_prompt=""
if ((${#prompt_args[@]} > 0)); then
  argument_prompt="${prompt_args[*]}"
fi

if [[ "$auth_smoke" == true ]]; then
  if [[ -n "$argument_prompt" || -n "$stdin_prompt" ]]; then
    echo "--auth-smoke cannot be combined with a request prompt or stdin prompt" >&2
    exit 64
  fi
  argument_prompt="Reply exactly with: claude-auth-ok"
fi

if [[ -z "$argument_prompt" && -z "$stdin_prompt" ]]; then
  usage >&2
  exit 64
fi

if [[ "$auth_smoke" == true ]]; then
  request_prompt="Reply exactly with: claude-auth-ok"
else
  request_prompt="You are being consulted from another local AI coding agent through non-interactive Claude Code.

Return the complete answer directly in stdout.
Do not create, write, or update files as the answer artifact for this consultation.
Do not respond only by saying that you wrote a plan, report, markdown file, or other artifact.
If a plan, report, diff, checklist, or markdown document would be useful, include its full contents in this stdout response instead.
If the user explicitly asks you to edit files, follow that request only within the named scope and still print the complete result summary to stdout. Do not write a plan or report file as a substitute for the response.

Preserve the user's request, constraints, paths, language, and requested output shape."
fi

if [[ -n "$argument_prompt" && "$auth_smoke" != true ]]; then
  request_prompt+="

Request from command arguments:
$argument_prompt"
fi

if [[ -n "$stdin_prompt" ]]; then
  request_prompt+="

Request from stdin:
$stdin_prompt"
fi

claude_args=(
  --model "$model"
  --effort "$effort"
  --permission-mode "$permission_mode"
  --output-format "$output_format"
)

if ((${#add_dirs[@]} > 0)); then
  for add_dir in "${add_dirs[@]}"; do
    claude_args+=(--add-dir "$add_dir")
  done
fi

cat >&2 <<STATUS
Starting Claude Code consultation.
  mode: $([[ "$auth_smoke" == true ]] && printf 'auth-smoke' || printf 'consultation')
  model: ${model}
  effort: ${effort}
  permission mode: ${permission_mode}
  output format: ${output_format}
  workdir: ${workdir}
Recommended host timeout: at least 3600000 ms for normal runs; longer for xhigh/max.
STATUS

run_claude() {
  local prompt="$1"
  (
    cd "$workdir"
    claude -p "$prompt" "${claude_args[@]}"
  )
}

looks_like_artifact_notice() {
  local output="$1"
  local line_count
  local word_count
  line_count="$(printf '%s' "$output" | wc -l | tr -d ' ')"
  word_count="$(printf '%s' "$output" | wc -w | tr -d ' ')"

  if ((line_count > 8 || word_count > 140)); then
    return 1
  fi

  printf '%s' "$output" | grep -Eiq '(wrote|written|created|saved).*(plan|report|markdown|file)|계획.*파일|파일.*작성|작성.*파일|saved at|written to'
}

set +e
claude_output="$(run_claude "$request_prompt")"
claude_status=$?
set -e

if ((claude_status != 0)); then
  printf '%s\n' "$claude_output"
  exit "$claude_status"
fi

if [[ "$auth_smoke" != true ]] && looks_like_artifact_notice "$claude_output"; then
  echo "Claude returned an artifact notice instead of a full stdout answer; retrying once." >&2
  retry_prompt="$request_prompt

The previous response did not satisfy the consultation contract because it referred to a file artifact instead of returning the answer. Do not use files. Print the full answer now."

  set +e
  claude_output="$(run_claude "$retry_prompt")"
  claude_status=$?
  set -e
fi

printf '%s\n' "$claude_output"
exit "$claude_status"
