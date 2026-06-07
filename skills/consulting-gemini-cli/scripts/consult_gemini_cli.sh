#!/usr/bin/env bash
set -euo pipefail

DEFAULT_GEMINI_APPROVAL_MODE="yolo"
DEFAULT_GEMINI_OUTPUT_FORMAT="text"

GEMINI_MODEL_PRO="gemini-2.5-pro"
GEMINI_MODEL_FLASH="gemini-2.5-flash"
GEMINI_MODEL_FLASH_LITE="gemini-2.5-flash-lite"

usage() {
  cat <<'USAGE'
Usage:
  consult_gemini_cli.sh [--model MODEL] [--approval-mode MODE] [--output-format FORMAT] [--cd DIR] [--include-dir DIR] [--sandbox] [request...]
  consult_gemini_cli.sh --auth-smoke
  consult_gemini_cli.sh [options] < prompt.md

Defaults:
  --model           Gemini CLI default (no --model argument is passed)
  --approval-mode   yolo
  --output-format   text
  --cd              current directory

Model aliases:
  pro               gemini-2.5-pro
  flash             gemini-2.5-flash
  lite, flash-lite  gemini-2.5-flash-lite
  default, cli-default
                    Gemini CLI default (no --model argument is passed)

Set CONSULT_GEMINI_BIN to an executable gemini path when you need to override
automatic discovery.

This wrapper intentionally does not set token, thinking, output-token, or budget caps.
The default approval mode is yolo, so Gemini CLI can directly inspect the
repository with shell tools in non-interactive consultation runs.

--auth-smoke runs a minimal Gemini prompt from a neutral temp directory so the
CLI can open its browser authentication flow without sending repository context.
USAGE
}

neutral_auth_dir="/tmp"
if [[ -d /private/tmp ]]; then
  neutral_auth_dir="/private/tmp"
fi

model="${CONSULT_GEMINI_MODEL:-${GEMINI_MODEL:-}}"
approval_mode="${CONSULT_GEMINI_APPROVAL_MODE:-$DEFAULT_GEMINI_APPROVAL_MODE}"
output_format="${CONSULT_GEMINI_OUTPUT_FORMAT:-$DEFAULT_GEMINI_OUTPUT_FORMAT}"
workdir="${CONSULT_GEMINI_WORKDIR:-$PWD}"
use_sandbox=false
auth_smoke=false
include_dirs=()
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
    --approval-mode)
      if (($# < 2)); then
        echo "Missing value for $1" >&2
        exit 64
      fi
      approval_mode="$2"
      shift 2
      ;;
    --approval-mode=*)
      approval_mode="${1#*=}"
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
    --include-dir|--include-directory|--include-directories)
      if (($# < 2)); then
        echo "Missing value for $1" >&2
        exit 64
      fi
      include_dirs+=("$2")
      shift 2
      ;;
    --include-dir=*|--include-directory=*|--include-directories=*)
      include_dirs+=("${1#*=}")
      shift
      ;;
    -s|--sandbox)
      use_sandbox=true
      shift
      ;;
    --auth-smoke|--auth-check)
      auth_smoke=true
      workdir="${CONSULT_GEMINI_AUTH_WORKDIR:-$neutral_auth_dir}"
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

if [[ -n "${GEMINI_CLI:-}" || -n "${GEMINI_CLI_SESSION_ID:-}" || "${GEMINI_INTERNAL_ORIGINATOR_OVERRIDE:-}" == Gemini* || "${CONSULT_GEMINI_CLI_FROM_GEMINI:-}" == "1" ]]; then
  echo "Gemini cannot use consulting-gemini-cli because it would recursively call Gemini. I will not run gemini -p from inside Gemini CLI." >&2
  exit 0
fi

print_executable_path() {
  local candidate="$1"
  if [[ -n "$candidate" && -x "$candidate" && ! -d "$candidate" ]]; then
    printf '%s\n' "$candidate"
    return 0
  fi
  return 1
}

resolve_gemini_bin() {
  local current_path_candidate shell_bin shell_lookup_output candidate

  if [[ -n "${CONSULT_GEMINI_BIN:-}" ]]; then
    if print_executable_path "$CONSULT_GEMINI_BIN"; then
      return 0
    fi
    echo "CONSULT_GEMINI_BIN is set but is not executable: $CONSULT_GEMINI_BIN" >&2
    exit 127
  fi

  current_path_candidate="$(command -v gemini 2>/dev/null || true)"
  if print_executable_path "$current_path_candidate"; then
    return 0
  fi

  shell_bin="${SHELL:-}"
  if [[ -n "$shell_bin" && -x "$shell_bin" ]]; then
    shell_lookup_output="$("$shell_bin" -lc 'command -v "$1"' _ gemini 2>/dev/null || true)"
    while IFS= read -r candidate; do
      if print_executable_path "$candidate"; then
        return 0
      fi
    done <<<"$shell_lookup_output"
  fi

  cat >&2 <<'ERROR'
gemini CLI was not found.
Checked:
  - CONSULT_GEMINI_BIN
  - command -v gemini in the current process PATH
  - command -v gemini from the user's login shell, when SHELL is executable
Install Gemini CLI, set CONSULT_GEMINI_BIN, or add gemini to your shell PATH.
ERROR
  exit 127
}

normalize_model() {
  case "$1" in
    ""|default|cli-default)
      printf '\n'
      ;;
    pro)
      printf '%s\n' "$GEMINI_MODEL_PRO"
      ;;
    flash)
      printf '%s\n' "$GEMINI_MODEL_FLASH"
      ;;
    lite|flash-lite)
      printf '%s\n' "$GEMINI_MODEL_FLASH_LITE"
      ;;
    *)
      printf '%s\n' "$1"
      ;;
  esac
}

help_supports_approval_mode() {
  local help_text="$1"
  local mode="$2"
  [[ "$help_text" == *"\"$mode\""* ]]
}

normalize_approval_mode() {
  local requested="$1"
  local help_text="$2"

  case "$requested" in
    default|auto_edit|yolo)
      if help_supports_approval_mode "$help_text" "$requested"; then
        printf '%s\n' "$requested"
        return 0
      fi
      ;;
    plan)
      if help_supports_approval_mode "$help_text" plan; then
        printf 'plan\n'
      else
        echo "Gemini CLI does not support --approval-mode=plan; using --approval-mode=default for this lower-permission request." >&2
        printf 'default\n'
      fi
      return 0
      ;;
  esac

  echo "Gemini CLI does not support --approval-mode=$requested" >&2
  exit 64
}

if [[ ! -d "$workdir" ]]; then
  echo "Working directory does not exist: $workdir" >&2
  exit 66
fi

gemini_bin="$(resolve_gemini_bin)"
gemini_help="$("$gemini_bin" --help 2>&1 || true)"
model="$(normalize_model "$model")"
approval_mode="$(normalize_approval_mode "$approval_mode" "$gemini_help")"

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
  argument_prompt="Reply exactly with: gemini-auth-ok"
fi
if [[ -z "$argument_prompt" && -z "$stdin_prompt" ]]; then
  usage >&2
  exit 64
fi

if [[ "$auth_smoke" == true ]]; then
  request_prompt="Reply exactly with: gemini-auth-ok"
else
  request_prompt="You are Gemini CLI being consulted by another local AI coding agent as an independent engineering reviewer.

Take the time needed for a careful answer. There is no requested token, thinking, output-token, or budget cap for this consultation; prioritize correctness and concrete evidence over brevity.

Return a concise but complete response that the calling agent can compare against its own reasoning. Call out uncertainties, cite local file paths when relevant, and state when you are making an inference."
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

gemini_args=(
  --approval-mode="$approval_mode"
  --output-format "$output_format"
)

if [[ -n "$model" ]]; then
  gemini_args=(--model "$model" "${gemini_args[@]}")
fi

if [[ "$use_sandbox" == true ]]; then
  gemini_args+=(--sandbox)
fi

if ((${#include_dirs[@]} > 0)); then
  for include_dir in "${include_dirs[@]}"; do
    gemini_args+=(--include-directories "$include_dir")
  done
fi

model_status="$model"
if [[ -z "$model_status" ]]; then
  model_status="Gemini CLI default"
fi

cat >&2 <<STATUS
Starting Gemini consultation.
  mode: $([[ "$auth_smoke" == true ]] && printf 'auth-smoke' || printf 'consultation')
  gemini: ${gemini_bin}
  model: ${model_status}
  approval mode: ${approval_mode}
  output format: ${output_format}
  sandbox: ${use_sandbox}
  workdir: ${workdir}
Recommended host timeout: at least 3600000 ms.
STATUS

run_gemini() {
  (
    cd "$workdir"
    "$gemini_bin" "${gemini_args[@]}" -p "$request_prompt"
  )
}

if [[ "$auth_smoke" == true ]]; then
  set +e
  auth_output="$(run_gemini)"
  auth_status=$?
  set -e

  if ((auth_status != 0)); then
    printf '%s\n' "$auth_output"
    exit "$auth_status"
  fi

  normalized_auth_output="$(printf '%s\n' "$auth_output" | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//' -e '/^$/d')"
  if [[ "$normalized_auth_output" != "gemini-auth-ok" ]]; then
    echo "Gemini auth smoke did not return the expected exact output." >&2
    echo "Expected: gemini-auth-ok" >&2
    echo "Actual output:" >&2
    printf '%s\n' "$auth_output" >&2
    exit 65
  fi

  printf 'gemini-auth-ok\n'
else
  run_gemini
fi
