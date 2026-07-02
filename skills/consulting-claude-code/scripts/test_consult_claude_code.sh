#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
wrapper="$script_dir/consult_claude_code.sh"
tmp_dir="$(mktemp -d)"
trap 'rm -rf "$tmp_dir"' EXIT

mock_bin="$tmp_dir/claude"
fake_shell="$tmp_dir/fake-login-shell"
mock_log="$tmp_dir/claude-args.log"
stdout_file="$tmp_dir/stdout.txt"
stderr_file="$tmp_dir/stderr.txt"

cat >"$mock_bin" <<'MOCK'
#!/usr/bin/env bash
set -euo pipefail

: >"${MOCK_LOG:?}"
for arg in "$@"; do
  printf '<%s>\n' "$arg" >>"$MOCK_LOG"
done

case "${MOCK_BEHAVIOR:-ok}" in
  ok)
    printf 'mock-ok\n'
    ;;
  auth-ok)
    printf 'claude-auth-ok\n'
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

if [[ "${1:-}" == "-lc" && "${3:-}" == "_" && "${4:-}" == "claude" ]]; then
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
  CONSULT_CLAUDE_BIN="$mock_bin" \
    CONSULT_CLAUDE_MODEL= \
    CLAUDE_MODEL= \
    CONSULT_CLAUDE_EFFORT= \
    CONSULT_CLAUDE_PERMISSION_MODE= \
    CONSULT_CLAUDE_OUTPUT_FORMAT= \
    CONSULT_CLAUDE_CHAIN_STATE_DIR="${CONSULT_CLAUDE_CHAIN_STATE_DIR:-}" \
    MOCK_LOG="$mock_log" \
    MOCK_BEHAVIOR="$behavior" \
    "$wrapper" "$@" >"$stdout_file" 2>"$stderr_file" </dev/null
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
  CONSULT_CLAUDE_BIN= \
    CONSULT_CLAUDE_MODEL= \
    CLAUDE_MODEL= \
    CONSULT_CLAUDE_EFFORT= \
    CONSULT_CLAUDE_PERMISSION_MODE= \
    CONSULT_CLAUDE_OUTPUT_FORMAT= \
    CONSULT_CLAUDE_CHAIN_STATE_DIR="${CONSULT_CLAUDE_CHAIN_STATE_DIR:-}" \
    MOCK_DISCOVERY_BIN="$mock_bin" \
    MOCK_LOG="$mock_log" \
    MOCK_BEHAVIOR="$behavior" \
    PATH="/usr/bin:/bin" \
    SHELL="$fake_shell" \
    "$wrapper" "$@" >"$stdout_file" 2>"$stderr_file" </dev/null
  local status=$?
  set -e

  [[ "$status" -eq "$expected_status" ]] || fail "expected status $expected_status, got $status"
}

run_wrapper 0 ok "hello"
assert_contains "$stderr_file" "claude: $mock_bin"
assert_contains "$mock_log" "<-p>"
assert_contains "$mock_log" "<--model>"
assert_contains "$mock_log" "<opus>"
assert_contains "$mock_log" "<--effort>"
assert_contains "$mock_log" "<medium>"
assert_contains "$mock_log" "<--permission-mode>"
assert_contains "$mock_log" "<auto>"
assert_contains "$mock_log" "<--output-format>"
assert_contains "$mock_log" "<text>"

run_wrapper 0 ok --permission-mode plan "hello"
assert_contains "$stderr_file" "does not use --permission-mode plan"
assert_contains "$mock_log" "<auto>"

run_wrapper 0 auth-ok --auth-smoke
assert_stdout_exact "claude-auth-ok"

chain_state_dir="$tmp_dir/claude-chain-state"
CONSULT_CLAUDE_CHAIN_STATE_DIR="$chain_state_dir" run_wrapper 0 ok --chain main "first chained question"
assert_contains "$mock_log" "<--session-id>"
chain_session_file="$(find "$chain_state_dir" -type f -name '*.session-id' 2>/dev/null | head -n 1 || true)"
if [[ -z "$chain_session_file" ]]; then
  fail "expected Claude chain session file to be created"
fi
chain_session_id="$(cat "$chain_session_file")"

CONSULT_CLAUDE_CHAIN_STATE_DIR="$(dirname "$chain_session_file")" run_wrapper 0 ok --chain main "follow-up chained question"
assert_contains "$mock_log" "<--resume>"
assert_contains "$mock_log" "<$chain_session_id>"

CONSULT_CLAUDE_CHAIN_STATE_DIR="$(dirname "$chain_session_file")" run_wrapper 0 ok --reset-chain main
[[ ! -e "$chain_session_file" ]] || fail "expected Claude chain session file to be removed"

run_wrapper_discovered 0 ok "hello"
assert_contains "$stderr_file" "claude: $mock_bin"
assert_contains "$mock_log" "<--model>"

set +e
CONSULT_CLAUDE_BIN="$tmp_dir/missing-claude" "$wrapper" "hello" >"$stdout_file" 2>"$stderr_file" </dev/null
missing_status=$?
set -e
[[ "$missing_status" -eq 127 ]] || fail "expected missing CONSULT_CLAUDE_BIN to exit 127, got $missing_status"
assert_contains "$stderr_file" "CONSULT_CLAUDE_BIN is set but is not executable"

echo "consult_claude_code.sh tests passed"
