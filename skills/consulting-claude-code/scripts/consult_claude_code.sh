#!/usr/bin/env bash
set -euo pipefail

DEFAULT_CLAUDE_MODEL="opus"
DEFAULT_CLAUDE_EFFORT="medium"
DEFAULT_CLAUDE_PERMISSION_MODE="auto"
DEFAULT_CLAUDE_OUTPUT_FORMAT="text"

usage() {
  cat <<'USAGE'
Usage:
  consult_claude_code.sh [--model MODEL] [--effort LEVEL] [--permission-mode MODE] [--output-format FORMAT] [--cd DIR] [--add-dir DIR] [--chain KEY] [request...]
  consult_claude_code.sh --auth-smoke
  consult_claude_code.sh --reset-chain KEY [--cd DIR]
  consult_claude_code.sh [options] < prompt.md

Defaults:
  --model             opus
  --effort            medium
  --permission-mode   auto
  --output-format     text
  --cd                current directory
  --chain             disabled; named chains resume prior Claude Code context

Set CONSULT_CLAUDE_BIN to an executable claude path when you need to override
automatic discovery.

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
chain_key="${CONSULT_CLAUDE_CHAIN_KEY:-}"
reset_chain_key=""

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
    --chain)
      if (($# < 2)); then
        echo "Missing value for $1" >&2
        exit 64
      fi
      chain_key="$2"
      shift 2
      ;;
    --chain=*)
      chain_key="${1#*=}"
      shift
      ;;
    --reset-chain)
      if (($# < 2)); then
        echo "Missing value for $1" >&2
        exit 64
      fi
      reset_chain_key="$2"
      shift 2
      ;;
    --reset-chain=*)
      reset_chain_key="${1#*=}"
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

print_executable_path() {
  local candidate="$1"
  if [[ -n "$candidate" && -x "$candidate" && ! -d "$candidate" ]]; then
    printf '%s\n' "$candidate"
    return 0
  fi
  return 1
}

resolve_claude_bin() {
  local current_path_candidate shell_bin shell_lookup_output candidate

  if [[ -n "${CONSULT_CLAUDE_BIN:-}" ]]; then
    if print_executable_path "$CONSULT_CLAUDE_BIN"; then
      return 0
    fi
    echo "CONSULT_CLAUDE_BIN is set but is not executable: $CONSULT_CLAUDE_BIN" >&2
    exit 127
  fi

  current_path_candidate="$(command -v claude 2>/dev/null || true)"
  if print_executable_path "$current_path_candidate"; then
    return 0
  fi

  shell_bin="${SHELL:-}"
  if [[ -n "$shell_bin" && -x "$shell_bin" ]]; then
    shell_lookup_output="$("$shell_bin" -lc 'command -v "$1"' _ claude 2>/dev/null || true)"
    while IFS= read -r candidate; do
      if print_executable_path "$candidate"; then
        return 0
      fi
    done <<<"$shell_lookup_output"
  fi

  cat >&2 <<'ERROR'
claude CLI was not found.
Checked:
  - CONSULT_CLAUDE_BIN
  - command -v claude in the current process PATH
  - command -v claude from the user's login shell, when SHELL is executable
Install Claude Code, set CONSULT_CLAUDE_BIN, or add claude to your shell PATH.
ERROR
  exit 127
}

hash_chain_identity() {
  local identity="$1"

  if command -v shasum >/dev/null 2>&1; then
    printf '%s' "$identity" | shasum -a 256 | awk '{print $1}'
    return 0
  fi

  if command -v sha256sum >/dev/null 2>&1; then
    printf '%s' "$identity" | sha256sum | awk '{print $1}'
    return 0
  fi

  printf '%s' "$identity" | cksum | awk '{print $1}'
}

chain_state_root() {
  if [[ -n "${CONSULT_CLAUDE_CHAIN_STATE_DIR:-}" ]]; then
    printf '%s\n' "$CONSULT_CLAUDE_CHAIN_STATE_DIR"
  elif [[ -n "${XDG_STATE_HOME:-}" ]]; then
    printf '%s/common-skills/consultations/claude\n' "$XDG_STATE_HOME"
  elif [[ -n "${HOME:-}" ]]; then
    printf '%s/.local/state/common-skills/consultations/claude\n' "$HOME"
  else
    printf '%s/common-skills/consultations/claude\n' "$neutral_auth_dir"
  fi
}

chain_state_file_for() {
  local key="$1"
  local root identity digest

  root="$(chain_state_root)"
  identity="consulting-claude-code
workdir=$workdir
key=$key"
  digest="$(hash_chain_identity "$identity")"
  printf '%s/%s.session-id\n' "$root" "$digest"
}

generate_uuid() {
  local hex

  if command -v uuidgen >/dev/null 2>&1; then
    uuidgen | tr '[:upper:]' '[:lower:]'
    return 0
  fi

  if [[ -r /proc/sys/kernel/random/uuid ]]; then
    tr '[:upper:]' '[:lower:]' </proc/sys/kernel/random/uuid
    return 0
  fi

  hex="$(od -An -N16 -tx1 /dev/urandom | tr -d ' \n')"
  if [[ "${#hex}" -ne 32 ]]; then
    echo "Could not generate a UUID for Claude chain state." >&2
    exit 70
  fi

  printf '%s-%s-%s-%s-%s\n' \
    "${hex:0:8}" \
    "${hex:8:4}" \
    "${hex:12:4}" \
    "${hex:16:4}" \
    "${hex:20:12}"
}

is_uuid() {
  [[ "$1" =~ ^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$ ]]
}

if [[ ! -d "$workdir" ]]; then
  echo "Working directory does not exist: $workdir" >&2
  exit 66
fi

workdir="$(cd "$workdir" && pwd -P)"

if [[ "$auth_smoke" == true && -n "$chain_key" ]]; then
  echo "--chain cannot be combined with --auth-smoke" >&2
  exit 64
fi

if [[ -n "$reset_chain_key" ]]; then
  chain_state_file="$(chain_state_file_for "$reset_chain_key")"
  rm -f "$chain_state_file"
  printf 'Removed Claude chain state for key: %s\n' "$reset_chain_key"
  exit 0
fi

claude_bin="$(resolve_claude_bin)"

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

chain_status="disabled"
chain_state_file=""
chain_session_id=""
chain_is_new=false
if [[ -n "$chain_key" ]]; then
  chain_state_file="$(chain_state_file_for "$chain_key")"
  mkdir -p "$(dirname "$chain_state_file")"

  if [[ -s "$chain_state_file" ]]; then
    chain_session_id="$(sed -n '1p' "$chain_state_file" | tr -d '[:space:]')"
    if ! is_uuid "$chain_session_id"; then
      echo "Stored Claude chain session ID is invalid for key '$chain_key': $chain_session_id" >&2
      echo "Run --reset-chain '$chain_key' to clear it." >&2
      exit 65
    fi
    claude_args+=(--resume "$chain_session_id")
    chain_status="resume:$chain_key"
  else
    chain_session_id="$(generate_uuid)"
    claude_args+=(--session-id "$chain_session_id")
    chain_is_new=true
    chain_status="new:$chain_key"
  fi
fi

if ((${#add_dirs[@]} > 0)); then
  for add_dir in "${add_dirs[@]}"; do
    claude_args+=(--add-dir "$add_dir")
  done
fi

cat >&2 <<STATUS
Starting Claude Code consultation.
  mode: $([[ "$auth_smoke" == true ]] && printf 'auth-smoke' || printf 'consultation')
  claude: ${claude_bin}
  model: ${model}
  effort: ${effort}
  permission mode: ${permission_mode}
  output format: ${output_format}
  workdir: ${workdir}
  chain: ${chain_status}
Recommended host timeout: at least 3600000 ms for normal runs; longer for xhigh/max.
STATUS

run_claude() {
  local prompt="$1"
  (
    cd "$workdir"
    "$claude_bin" -p "$prompt" "${claude_args[@]}"
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

if [[ "$chain_is_new" == true ]]; then
  printf '%s\n' "$chain_session_id" >"$chain_state_file"
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
