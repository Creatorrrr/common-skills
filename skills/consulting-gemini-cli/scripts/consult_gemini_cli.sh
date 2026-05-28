#!/usr/bin/env bash
set -euo pipefail

DEFAULT_GEMINI_MODEL="pro"
DEFAULT_GEMINI_APPROVAL_MODE="plan"
DEFAULT_GEMINI_OUTPUT_FORMAT="text"

usage() {
  cat <<'USAGE'
Usage:
  consult_gemini_cli.sh [--model MODEL] [--approval-mode MODE] [--output-format FORMAT] [--cd DIR] [--include-dir DIR] [--sandbox] [request...]
  consult_gemini_cli.sh --auth-smoke
  consult_gemini_cli.sh [options] < prompt.md

Defaults:
  --model           pro
  --approval-mode   plan
  --output-format   text
  --cd              current directory

This wrapper intentionally does not set token, thinking, output-token, or budget caps.

--auth-smoke runs a minimal Gemini prompt from a neutral temp directory so the
CLI can open its browser authentication flow without sending repository context.
USAGE
}

neutral_auth_dir="/tmp"
if [[ -d /private/tmp ]]; then
  neutral_auth_dir="/private/tmp"
fi

model="${CONSULT_GEMINI_MODEL:-${GEMINI_MODEL:-$DEFAULT_GEMINI_MODEL}}"
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

if ! command -v gemini >/dev/null 2>&1; then
  echo "gemini CLI is not on PATH" >&2
  exit 127
fi

if [[ ! -d "$workdir" ]]; then
  echo "Working directory does not exist: $workdir" >&2
  exit 66
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
  --model "$model"
  --approval-mode="$approval_mode"
  --output-format "$output_format"
  --skip-trust
)

if [[ "$use_sandbox" == true ]]; then
  gemini_args+=(--sandbox)
fi

if ((${#include_dirs[@]} > 0)); then
  for include_dir in "${include_dirs[@]}"; do
    gemini_args+=(--include-directories "$include_dir")
  done
fi

cat >&2 <<STATUS
Starting Gemini consultation.
  mode: $([[ "$auth_smoke" == true ]] && printf 'auth-smoke' || printf 'consultation')
  model: ${model}
  approval mode: ${approval_mode}
  output format: ${output_format}
  sandbox: ${use_sandbox}
  workdir: ${workdir}
Recommended host timeout: at least 3600000 ms.
STATUS

(
  cd "$workdir"
  gemini "${gemini_args[@]}" -p "$request_prompt"
)
