#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
wrapper="$script_dir/consult_antigravity_cli.sh"
tmp_dir="$(mktemp -d)"
trap 'rm -rf "$tmp_dir"' EXIT

mock_bin="$tmp_dir/agy"
fake_shell="$tmp_dir/fake-login-shell"
mock_log="$tmp_dir/agy-args.log"
mock_help="$tmp_dir/agy-help.txt"
stdout_file="$tmp_dir/stdout.txt"
stderr_file="$tmp_dir/stderr.txt"

cat >"$mock_help" <<'HELP'
Usage: agy [options]
  -p string
      Prompt to run in non-interactive mode.
  --model string
      Model to use for this session.
  --sandbox
      Run terminal commands in sandbox mode.
  --dangerously-skip-permissions
      Skip permission prompts.
  --log-file string
      Override CLI log file path.
  --conversation string
      Resume a previous conversation by ID.
HELP

cat >"$mock_bin" <<'MOCK'
#!/usr/bin/env bash
set -euo pipefail

if [[ "${1:-}" == "--help" ]]; then
  cat "${MOCK_HELP:?}"
  exit 0
fi

cli_log_file=""
previous_arg=""
for arg in "$@"; do
  if [[ "$previous_arg" == "--log-file" ]]; then
    cli_log_file="$arg"
  fi
  previous_arg="$arg"
done

: >"${MOCK_LOG:?}"
printf '<env:ANTIGRAVITY_CLI=%s>\n' "${ANTIGRAVITY_CLI:-}" >>"$MOCK_LOG"
printf '<env:ANTIGRAVITY_CLI_SESSION_ID=%s>\n' "${ANTIGRAVITY_CLI_SESSION_ID:-}" >>"$MOCK_LOG"
printf '<env:AGY_SESSION_ID=%s>\n' "${AGY_SESSION_ID:-}" >>"$MOCK_LOG"
printf '<env:ANTIGRAVITY_INTERNAL_ORIGINATOR_OVERRIDE=%s>\n' "${ANTIGRAVITY_INTERNAL_ORIGINATOR_OVERRIDE:-}" >>"$MOCK_LOG"
for arg in "$@"; do
  printf '<%s>\n' "$arg" >>"$MOCK_LOG"
done

case "${MOCK_BEHAVIOR:-ok}" in
  ok)
    if [[ -n "$cli_log_file" ]]; then
      mkdir -p "$(dirname "$cli_log_file")"
      printf 'I0702 mock] Created conversation %s\n' "${MOCK_CONVERSATION_ID:-11111111-2222-3333-4444-555555555555}" >>"$cli_log_file"
    fi
    printf 'mock-ok\n'
    ;;
  auth-ok)
    printf 'antigravity-auth-ok\n'
    ;;
  auth-polluted)
    printf 'antigravity-auth-ok\nextra-context\n'
    ;;
  fail)
    printf 'mock failure\n'
    exit 2
    ;;
  *)
    printf 'unknown mock behavior: %s\n' "$MOCK_BEHAVIOR" >&2
    exit 99
    ;;
esac
MOCK
chmod +x "$mock_bin"

cat >"$fake_shell" <<'MOCKSHELL'
#!/usr/bin/env bash
set -euo pipefail

if [[ "${1:-}" == "-lc" && "${3:-}" == "_" && ( "${4:-}" == "agy" || "${4:-}" == "antigravity" ) ]]; then
  printf '%s\n' "${MOCK_DISCOVERY_BIN:?}"
  exit 0
fi

exit 1
MOCKSHELL
chmod +x "$fake_shell"

fail() {
  echo "FAIL: $*" >&2
  echo "--- stdout ---" >&2
  [[ -f "$stdout_file" ]] && cat "$stdout_file" >&2 || true
  echo "--- stderr ---" >&2
  [[ -f "$stderr_file" ]] && cat "$stderr_file" >&2 || true
  echo "--- args ---" >&2
  [[ -f "$mock_log" ]] && cat "$mock_log" >&2 || true
  exit 1
}

assert_contains() {
  local file="$1"
  local expected="$2"
  grep -Fq -- "$expected" "$file" || fail "expected $file to contain: $expected"
}

assert_not_contains() {
  local file="$1"
  local unexpected="$2"
  if grep -Fq -- "$unexpected" "$file"; then
    fail "expected $file not to contain: $unexpected"
  fi
}

assert_stdout_exact() {
  local expected="$1"
  local actual
  actual="$(cat "$stdout_file")"
  [[ "$actual" == "$expected" ]] || fail "expected stdout to equal: $expected"
}

run_wrapper() {
  local expected_status="$1"
  local behavior="$2"
  shift 2

  : >"$mock_log"
  : >"$stdout_file"
  : >"$stderr_file"

  set +e
  CONSULT_ANTIGRAVITY_BIN="$mock_bin" \
    CONSULT_AGY_BIN= \
    CONSULT_ANTIGRAVITY_MODEL= \
    AGY_MODEL= \
    CONSULT_ANTIGRAVITY_PERMISSION_MODE= \
    CONSULT_ANTIGRAVITY_CHAIN_STATE_DIR="${CONSULT_ANTIGRAVITY_CHAIN_STATE_DIR:-}" \
    MOCK_HELP="$mock_help" \
    MOCK_LOG="$mock_log" \
    MOCK_BEHAVIOR="$behavior" \
    MOCK_CONVERSATION_ID="${MOCK_CONVERSATION_ID:-11111111-2222-3333-4444-555555555555}" \
    "$wrapper" "$@" >"$stdout_file" 2>"$stderr_file" </dev/null
  local status=$?
  set -e

  [[ "$status" -eq "$expected_status" ]] || fail "expected status $expected_status, got $status"
}

run_wrapper_stdin() {
  local expected_status="$1"
  local behavior="$2"
  local stdin_data="$3"
  shift 3

  : >"$mock_log"
  : >"$stdout_file"
  : >"$stderr_file"

  set +e
  printf '%s' "$stdin_data" | CONSULT_ANTIGRAVITY_BIN="$mock_bin" \
    CONSULT_AGY_BIN= \
    CONSULT_ANTIGRAVITY_MODEL= \
    AGY_MODEL= \
    CONSULT_ANTIGRAVITY_PERMISSION_MODE= \
    CONSULT_ANTIGRAVITY_CHAIN_STATE_DIR="${CONSULT_ANTIGRAVITY_CHAIN_STATE_DIR:-}" \
    MOCK_HELP="$mock_help" \
    MOCK_LOG="$mock_log" \
    MOCK_BEHAVIOR="$behavior" \
    MOCK_CONVERSATION_ID="${MOCK_CONVERSATION_ID:-11111111-2222-3333-4444-555555555555}" \
    "$wrapper" "$@" >"$stdout_file" 2>"$stderr_file"
  local status=$?
  set -e

  [[ "$status" -eq "$expected_status" ]] || fail "expected status $expected_status, got $status"
}

run_wrapper_discovered() {
  local expected_status="$1"
  local behavior="$2"
  shift 2

  : >"$mock_log"
  : >"$stdout_file"
  : >"$stderr_file"

  set +e
  CONSULT_ANTIGRAVITY_BIN= \
    CONSULT_AGY_BIN= \
    CONSULT_ANTIGRAVITY_MODEL= \
    AGY_MODEL= \
    CONSULT_ANTIGRAVITY_PERMISSION_MODE= \
    CONSULT_ANTIGRAVITY_CHAIN_STATE_DIR="${CONSULT_ANTIGRAVITY_CHAIN_STATE_DIR:-}" \
    MOCK_DISCOVERY_BIN="$mock_bin" \
    MOCK_HELP="$mock_help" \
    MOCK_LOG="$mock_log" \
    MOCK_BEHAVIOR="$behavior" \
    MOCK_CONVERSATION_ID="${MOCK_CONVERSATION_ID:-11111111-2222-3333-4444-555555555555}" \
    PATH="/usr/bin:/bin" \
    SHELL="$fake_shell" \
    "$wrapper" "$@" >"$stdout_file" 2>"$stderr_file" </dev/null
  local status=$?
  set -e

  [[ "$status" -eq "$expected_status" ]] || fail "expected status $expected_status, got $status"
}

run_wrapper 0 ok "hello"
assert_contains "$mock_log" "<--dangerously-skip-permissions>"
assert_contains "$mock_log" "<-p>"
assert_not_contains "$mock_log" "<--model>"

run_wrapper 0 ok --model "Gemini 3.5 Flash (High)" "hello"
assert_contains "$mock_log" "<--model>"
assert_contains "$mock_log" "<Gemini 3.5 Flash (High)>"

run_wrapper 0 ok --model cli-default "hello"
assert_not_contains "$mock_log" "<--model>"

run_wrapper 0 ok --permission-mode request-review "hello"
assert_not_contains "$mock_log" "<--dangerously-skip-permissions>"
assert_not_contains "$mock_log" "<--sandbox>"

run_wrapper 0 ok --no-dangerously-skip-permissions "hello"
assert_not_contains "$mock_log" "<--dangerously-skip-permissions>"

run_wrapper 0 ok --permission-mode sandbox "hello"
assert_contains "$mock_log" "<--sandbox>"
assert_not_contains "$mock_log" "<--dangerously-skip-permissions>"

run_wrapper 0 ok --sandbox "hello"
assert_contains "$mock_log" "<--sandbox>"
assert_not_contains "$mock_log" "<--dangerously-skip-permissions>"

run_wrapper 0 ok --approval-mode yolo "hello"
assert_contains "$stderr_file" "--approval-mode is a Gemini CLI compatibility alias"
assert_contains "$mock_log" "<--dangerously-skip-permissions>"

run_wrapper 0 ok --approval-mode plan "hello"
assert_contains "$stderr_file" "--approval-mode is a Gemini CLI compatibility alias"
assert_not_contains "$mock_log" "<--dangerously-skip-permissions>"

run_wrapper_stdin 0 ok $'line1\nline2\n'
assert_contains "$mock_log" "Request from stdin:"
assert_contains "$mock_log" "line1"
assert_contains "$mock_log" "line2"

chain_state_dir="$tmp_dir/antigravity-chain-state"
chain_conversation_id="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
CONSULT_ANTIGRAVITY_CHAIN_STATE_DIR="$chain_state_dir" MOCK_CONVERSATION_ID="$chain_conversation_id" run_wrapper 0 ok --chain main "first chained question"
assert_contains "$mock_log" "<--log-file>"
chain_conversation_file="$(find "$chain_state_dir" -type f -name '*.conversation-id' 2>/dev/null | head -n 1 || true)"
if [[ -z "$chain_conversation_file" ]]; then
  fail "expected Antigravity chain conversation file to be created"
fi
[[ "$(cat "$chain_conversation_file")" == "$chain_conversation_id" ]] || fail "expected Antigravity conversation ID to be stored"

CONSULT_ANTIGRAVITY_CHAIN_STATE_DIR="$chain_state_dir" run_wrapper 0 ok --chain main "follow-up chained question"
assert_contains "$mock_log" "<--conversation>"
assert_contains "$mock_log" "<$chain_conversation_id>"

CONSULT_ANTIGRAVITY_CHAIN_STATE_DIR="$chain_state_dir" run_wrapper 0 ok --reset-chain main
[[ ! -e "$chain_conversation_file" ]] || fail "expected Antigravity chain conversation file to be removed"

run_wrapper 64 ok
assert_contains "$stderr_file" "No Antigravity request prompt received from command arguments or stdin."
assert_contains "$stderr_file" "stdin was non-interactive but empty"

set +e
ANTIGRAVITY_INTERNAL_ORIGINATOR_OVERRIDE="Antigravity CLI" CODEX_SHELL=1 CONSULT_ANTIGRAVITY_BIN="$mock_bin" MOCK_HELP="$mock_help" MOCK_LOG="$mock_log" MOCK_BEHAVIOR=ok "$wrapper" "hello" >"$stdout_file" 2>"$stderr_file" </dev/null
inherited_originator_status=$?
set -e
[[ "$inherited_originator_status" -eq 0 ]] || fail "expected inherited Antigravity originator to be scrubbed and allowed, got $inherited_originator_status"
assert_contains "$mock_log" "<env:ANTIGRAVITY_INTERNAL_ORIGINATOR_OVERRIDE=>"

set +e
env -u CODEX_SHELL -u CODEX_THREAD_ID -u CODEX_INTERNAL_ORIGINATOR_OVERRIDE ANTIGRAVITY_CLI_SESSION_ID="agy-session" CONSULT_ANTIGRAVITY_BIN="$mock_bin" MOCK_HELP="$mock_help" MOCK_LOG="$mock_log" "$wrapper" "hello" >"$stdout_file" 2>"$stderr_file" </dev/null
recursive_status=$?
set -e
[[ "$recursive_status" -eq 65 ]] || fail "expected recursive Antigravity session to exit 65, got $recursive_status"
assert_contains "$stderr_file" "Antigravity cannot use consulting-antigravity-cli"

set +e
CONSULT_ANTIGRAVITY_CLI_FROM_ANTIGRAVITY=1 CODEX_SHELL=1 CONSULT_ANTIGRAVITY_BIN="$mock_bin" MOCK_HELP="$mock_help" MOCK_LOG="$mock_log" "$wrapper" "hello" >"$stdout_file" 2>"$stderr_file" </dev/null
explicit_recursive_status=$?
set -e
[[ "$explicit_recursive_status" -eq 65 ]] || fail "expected explicit recursive marker to exit 65, got $explicit_recursive_status"
assert_contains "$stderr_file" "Antigravity cannot use consulting-antigravity-cli"

run_wrapper 64 ok --skip-trust "hello"
assert_contains "$stderr_file" "has no documented headless trust bypass"

run_wrapper 64 ok --include-dir /tmp "hello"
assert_contains "$stderr_file" "workspace/file scope should be controlled with --cd"

run_wrapper 0 auth-ok --auth-smoke
assert_stdout_exact "antigravity-auth-ok"

run_wrapper 65 auth-polluted --auth-smoke
assert_contains "$stderr_file" "did not return the expected exact output"

run_wrapper_discovered 0 ok "hello"
assert_contains "$stderr_file" "agy: $mock_bin"
assert_contains "$mock_log" "<--dangerously-skip-permissions>"

set +e
CONSULT_ANTIGRAVITY_BIN="$tmp_dir/missing-agy" "$wrapper" "hello" >"$stdout_file" 2>"$stderr_file" </dev/null
missing_status=$?
set -e
[[ "$missing_status" -eq 127 ]] || fail "expected missing CONSULT_ANTIGRAVITY_BIN to exit 127, got $missing_status"
assert_contains "$stderr_file" "CONSULT_ANTIGRAVITY_BIN is set but is not executable"

echo "consult_antigravity_cli.sh tests passed"
