#!/usr/bin/env bash
set -euo pipefail

DEFAULT_ANTIGRAVITY_PERMISSION_MODE="dangerously-skip-permissions"

usage() {
  cat <<'USAGE'
Usage:
  consult_antigravity_cli.sh [--model MODEL] [--permission-mode MODE] [--cd DIR] [--sandbox] [--chain KEY] [request...]
  consult_antigravity_cli.sh [--dangerously-skip-permissions|--no-dangerously-skip-permissions] [request...]
  consult_antigravity_cli.sh --auth-smoke
  consult_antigravity_cli.sh --reset-chain KEY [--cd DIR]
  consult_antigravity_cli.sh [options] < prompt.md

Defaults:
  --model                         Antigravity CLI default (no --model argument is passed)
  --permission-mode               dangerously-skip-permissions
  --cd                            current directory
  --sandbox                       disabled unless explicitly requested
  --chain                         disabled; named chains resume prior Antigravity context

Permission modes:
  dangerously-skip-permissions    pass --dangerously-skip-permissions
  always-proceed, yolo            aliases for dangerously-skip-permissions
  request-review, default, ask    omit --dangerously-skip-permissions
  strict, plan                    omit --dangerously-skip-permissions
  sandbox, proceed-in-sandbox     pass --sandbox and omit --dangerously-skip-permissions

Set CONSULT_ANTIGRAVITY_BIN or CONSULT_AGY_BIN to an executable agy path when
you need to override automatic discovery.

This wrapper intentionally does not set token, thinking, output-token, or budget caps.
The default permission mode is dangerously-skip-permissions, so Antigravity CLI
can directly inspect the repository in non-interactive consultation runs.

--auth-smoke runs a minimal Antigravity prompt from a neutral temp directory so
the CLI can verify authentication without sending repository context.
USAGE
}

neutral_auth_dir="/tmp"
if [[ -d /private/tmp ]]; then
  neutral_auth_dir="/private/tmp"
fi

model="${CONSULT_ANTIGRAVITY_MODEL:-${AGY_MODEL:-}}"
permission_mode="${CONSULT_ANTIGRAVITY_PERMISSION_MODE:-$DEFAULT_ANTIGRAVITY_PERMISSION_MODE}"
permission_mode_explicit=false
workdir="${CONSULT_ANTIGRAVITY_WORKDIR:-$PWD}"
use_sandbox=false
auth_smoke=false
prompt_args=()
chain_key="${CONSULT_ANTIGRAVITY_CHAIN_KEY:-}"
reset_chain_key=""

set_permission_mode() {
  permission_mode="$1"
  permission_mode_explicit=true
}

unsupported_option() {
  local option="$1"
  local reason="$2"
  echo "$option is not supported by consulting-antigravity-cli: $reason" >&2
  exit 64
}

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
    --permission-mode)
      if (($# < 2)); then
        echo "Missing value for $1" >&2
        exit 64
      fi
      set_permission_mode "$2"
      shift 2
      ;;
    --permission-mode=*)
      set_permission_mode "${1#*=}"
      shift
      ;;
    --approval-mode)
      if (($# < 2)); then
        echo "Missing value for $1" >&2
        exit 64
      fi
      echo "--approval-mode is a Gemini CLI compatibility alias; prefer --permission-mode for Antigravity CLI." >&2
      set_permission_mode "$2"
      shift 2
      ;;
    --approval-mode=*)
      echo "--approval-mode is a Gemini CLI compatibility alias; prefer --permission-mode for Antigravity CLI." >&2
      set_permission_mode "${1#*=}"
      shift
      ;;
    --dangerously-skip-permissions|--yolo)
      set_permission_mode "dangerously-skip-permissions"
      shift
      ;;
    --no-dangerously-skip-permissions|--request-review|--ask)
      set_permission_mode "request-review"
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
    -s|--sandbox)
      use_sandbox=true
      if [[ "$permission_mode_explicit" == false ]]; then
        permission_mode="sandbox"
      fi
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
      workdir="${CONSULT_ANTIGRAVITY_AUTH_WORKDIR:-$neutral_auth_dir}"
      shift
      ;;
    --output-format|--output-format=*)
      unsupported_option "$1" "Antigravity CLI does not expose the Gemini CLI --output-format contract."
      ;;
    --include-dir|--include-directory|--include-directories|--include-dir=*|--include-directory=*|--include-directories=*)
      unsupported_option "$1" "Antigravity CLI workspace/file scope should be controlled with --cd and @path file context."
      ;;
    --skip-trust|--trust|--trust-workspace)
      unsupported_option "$1" "Antigravity CLI has no documented headless trust bypass; trust the workspace interactively."
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

is_known_non_antigravity_agent() {
  [[ -n "${CODEX_SHELL:-}" ]] ||
    [[ -n "${CODEX_THREAD_ID:-}" ]] ||
    [[ "${CODEX_INTERNAL_ORIGINATOR_OVERRIDE:-}" == Codex* ]] ||
    [[ -n "${CLAUDECODE:-}" ]] ||
    [[ -n "${CLAUDE_CODE:-}" ]] ||
    [[ -n "${ANTHROPIC_AGENT:-}" ]] ||
    [[ -n "${GEMINI_CLI:-}" ]] ||
    [[ -n "${GEMINI_CLI_SESSION_ID:-}" ]]
}

has_antigravity_session_marker() {
  [[ -n "${ANTIGRAVITY_CLI:-}" ]] ||
    [[ -n "${ANTIGRAVITY_CLI_SESSION_ID:-}" ]] ||
    [[ -n "${AGY_CLI:-}" ]] ||
    [[ -n "${AGY_SESSION_ID:-}" ]] ||
    [[ -n "${AGY_BROWSER_WS_URL:-}" ]] ||
    [[ "${ANTIGRAVITY_INTERNAL_ORIGINATOR_OVERRIDE:-}" == Antigravity* ]]
}

if [[ "${CONSULT_ANTIGRAVITY_CLI_FROM_ANTIGRAVITY:-}" == "1" ]] ||
  { has_antigravity_session_marker && ! is_known_non_antigravity_agent; }; then
  echo "Antigravity cannot use consulting-antigravity-cli because it would recursively call Antigravity. I will not run agy -p from inside Antigravity CLI." >&2
  exit 65
fi

scrub_inherited_antigravity_env=false
if has_antigravity_session_marker; then
  scrub_inherited_antigravity_env=true
fi

print_executable_path() {
  local candidate="$1"
  if [[ -n "$candidate" && -x "$candidate" && ! -d "$candidate" ]]; then
    printf '%s\n' "$candidate"
    return 0
  fi
  return 1
}

resolve_antigravity_bin() {
  local override_name override_value command_name current_path_candidate shell_bin shell_lookup_output candidate

  for override_name in CONSULT_ANTIGRAVITY_BIN CONSULT_AGY_BIN; do
    override_value="${!override_name:-}"
    if [[ -n "$override_value" ]]; then
      if print_executable_path "$override_value"; then
        return 0
      fi
      echo "$override_name is set but is not executable: $override_value" >&2
      exit 127
    fi
  done

  for command_name in agy antigravity; do
    current_path_candidate="$(command -v "$command_name" 2>/dev/null || true)"
    if print_executable_path "$current_path_candidate"; then
      return 0
    fi
  done

  shell_bin="${SHELL:-}"
  if [[ -n "$shell_bin" && -x "$shell_bin" ]]; then
    for command_name in agy antigravity; do
      shell_lookup_output="$("$shell_bin" -lc 'command -v "$1"' _ "$command_name" 2>/dev/null || true)"
      while IFS= read -r candidate; do
        if print_executable_path "$candidate"; then
          return 0
        fi
      done <<<"$shell_lookup_output"
    done
  fi

  cat >&2 <<'ERROR'
Antigravity CLI was not found.
Checked:
  - CONSULT_ANTIGRAVITY_BIN
  - CONSULT_AGY_BIN
  - command -v agy / antigravity in the current process PATH
  - command -v agy / antigravity from the user's login shell, when SHELL is executable
Install Antigravity CLI, set CONSULT_ANTIGRAVITY_BIN, or add agy to your shell PATH.
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
  if [[ -n "${CONSULT_ANTIGRAVITY_CHAIN_STATE_DIR:-}" ]]; then
    printf '%s\n' "$CONSULT_ANTIGRAVITY_CHAIN_STATE_DIR"
  elif [[ -n "${XDG_STATE_HOME:-}" ]]; then
    printf '%s/common-skills/consultations/antigravity\n' "$XDG_STATE_HOME"
  elif [[ -n "${HOME:-}" ]]; then
    printf '%s/.local/state/common-skills/consultations/antigravity\n' "$HOME"
  else
    printf '%s/common-skills/consultations/antigravity\n' "$neutral_auth_dir"
  fi
}

chain_state_base_for() {
  local key="$1"
  local root identity digest

  root="$(chain_state_root)"
  identity="consulting-antigravity-cli
workdir=$workdir
key=$key"
  digest="$(hash_chain_identity "$identity")"
  printf '%s/%s\n' "$root" "$digest"
}

is_uuid() {
  [[ "$1" =~ ^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$ ]]
}

extract_conversation_id() {
  local log_file="$1"

  if [[ ! -f "$log_file" ]]; then
    return 1
  fi

  sed -nE \
    -e 's/.*Created conversation ([0-9a-fA-F-]{36}).*/\1/p' \
    -e 's/.*Print mode: conversation=([0-9a-fA-F-]{36}).*/\1/p' \
    "$log_file" | tail -n 1 | tr '[:upper:]' '[:lower:]'
}

normalize_model() {
  case "$1" in
    ""|default|cli-default)
      printf '\n'
      ;;
    *)
      printf '%s\n' "$1"
      ;;
  esac
}

normalize_permission_mode() {
  case "$1" in
    ""|dangerously-skip-permissions|dangerous|skip-permissions|skip|always-proceed|yolo)
      printf 'dangerously-skip-permissions\n'
      ;;
    request-review|request_review|default|ask|manual|strict|plan|auto_edit)
      printf 'request-review\n'
      ;;
    sandbox|proceed-in-sandbox|proceed_in_sandbox)
      printf 'sandbox\n'
      ;;
    *)
      echo "Unsupported Antigravity permission mode: $1" >&2
      echo "Use dangerously-skip-permissions, request-review, strict, or sandbox." >&2
      exit 64
      ;;
  esac
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
  chain_state_base="$(chain_state_base_for "$reset_chain_key")"
  rm -f "${chain_state_base}.conversation-id" "${chain_state_base}.log"
  printf 'Removed Antigravity chain state for key: %s\n' "$reset_chain_key"
  exit 0
fi

antigravity_bin="$(resolve_antigravity_bin)"
model="$(normalize_model "$model")"
permission_mode="$(normalize_permission_mode "$permission_mode")"
if [[ "$permission_mode" == "sandbox" ]]; then
  use_sandbox=true
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
  argument_prompt="Reply exactly with: antigravity-auth-ok"
fi
if [[ -z "$argument_prompt" && -z "$stdin_prompt" ]]; then
  echo "No Antigravity request prompt received from command arguments or stdin." >&2
  if [[ -t 0 ]]; then
    echo "stdin is a TTY; pass a prompt argument or pipe/heredoc prompt text." >&2
  else
    echo "stdin was non-interactive but empty; pass a prompt argument or non-empty stdin." >&2
  fi
  usage >&2
  exit 64
fi

if [[ "$auth_smoke" == true ]]; then
  request_prompt="Reply exactly with: antigravity-auth-ok"
else
  request_prompt="You are Antigravity CLI being consulted by another local AI coding agent as an independent engineering reviewer.

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

antigravity_args=()

if [[ -n "$model" ]]; then
  antigravity_args+=(--model "$model")
fi

if [[ "$use_sandbox" == true ]]; then
  antigravity_args+=(--sandbox)
fi

if [[ "$permission_mode" == "dangerously-skip-permissions" ]]; then
  antigravity_args+=(--dangerously-skip-permissions)
fi

chain_status="disabled"
chain_state_base=""
chain_conversation_file=""
chain_log_file=""
chain_conversation_id=""
chain_is_new=false
if [[ -n "$chain_key" ]]; then
  chain_state_base="$(chain_state_base_for "$chain_key")"
  mkdir -p "$(dirname "$chain_state_base")"
  chain_conversation_file="${chain_state_base}.conversation-id"
  chain_log_file="${chain_state_base}.log"

  if [[ -s "$chain_conversation_file" ]]; then
    chain_conversation_id="$(sed -n '1p' "$chain_conversation_file" | tr -d '[:space:]')"
    if ! is_uuid "$chain_conversation_id"; then
      echo "Stored Antigravity chain conversation ID is invalid for key '$chain_key': $chain_conversation_id" >&2
      echo "Run --reset-chain '$chain_key' to clear it." >&2
      exit 65
    fi
    antigravity_args+=(--conversation "$chain_conversation_id")
    chain_status="resume:$chain_key"
  else
    : >"$chain_log_file"
    antigravity_args+=(--log-file "$chain_log_file")
    chain_is_new=true
    chain_status="new:$chain_key"
  fi
fi

model_status="$model"
if [[ -z "$model_status" ]]; then
  model_status="Antigravity CLI default"
fi

cat >&2 <<STATUS
Starting Antigravity consultation.
  mode: $([[ "$auth_smoke" == true ]] && printf 'auth-smoke' || printf 'consultation')
  agy: ${antigravity_bin}
  model: ${model_status}
  permission mode: ${permission_mode}
  sandbox: ${use_sandbox}
  workdir: ${workdir}
  chain: ${chain_status}
Recommended host timeout: at least 3600000 ms.
STATUS

run_antigravity() {
  (
    cd "$workdir"
    if [[ "$scrub_inherited_antigravity_env" == true ]]; then
      unset ANTIGRAVITY_CLI || true
      unset ANTIGRAVITY_CLI_SESSION_ID || true
      unset AGY_CLI || true
      unset AGY_SESSION_ID || true
      unset AGY_BROWSER_WS_URL || true
      unset ANTIGRAVITY_INTERNAL_ORIGINATOR_OVERRIDE || true
    fi
    if ((${#antigravity_args[@]} > 0)); then
      "$antigravity_bin" "${antigravity_args[@]}" -p "$request_prompt"
    else
      "$antigravity_bin" -p "$request_prompt"
    fi
  )
}

if [[ "$auth_smoke" == true ]]; then
  set +e
  auth_output="$(run_antigravity)"
  auth_status=$?
  set -e

  if ((auth_status != 0)); then
    printf '%s\n' "$auth_output"
    exit "$auth_status"
  fi

  normalized_auth_output="$(printf '%s\n' "$auth_output" | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//' -e '/^$/d')"
  if [[ "$normalized_auth_output" != "antigravity-auth-ok" ]]; then
    echo "Antigravity auth smoke did not return the expected exact output." >&2
    echo "Expected: antigravity-auth-ok" >&2
    echo "Actual output:" >&2
    printf '%s\n' "$auth_output" >&2
    exit 65
  fi

  printf 'antigravity-auth-ok\n'
else
  if [[ "$chain_is_new" == true ]]; then
    set +e
    antigravity_output="$(run_antigravity)"
    antigravity_status=$?
    set -e

    printf '%s\n' "$antigravity_output"

    if ((antigravity_status != 0)); then
      exit "$antigravity_status"
    fi

    chain_conversation_id="$(extract_conversation_id "$chain_log_file")"
    if ! is_uuid "$chain_conversation_id"; then
      echo "Antigravity chain '$chain_key' completed, but no conversation ID could be found in: $chain_log_file" >&2
      echo "The response above is valid, but this chain cannot be resumed until the ID is available." >&2
      exit 65
    fi

    printf '%s\n' "$chain_conversation_id" >"$chain_conversation_file"
  else
    run_antigravity
  fi
fi
