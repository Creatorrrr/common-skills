#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
wrapper="$script_dir/consult_gemini_cli.sh"
tmp_dir="$(mktemp -d)"
trap 'rm -rf "$tmp_dir"' EXIT

mock_bin="$tmp_dir/gemini"
fake_shell="$tmp_dir/fake-login-shell"
mock_log="$tmp_dir/gemini-args.log"
mock_help="$tmp_dir/gemini-help.txt"
stdout_file="$tmp_dir/stdout.txt"
stderr_file="$tmp_dir/stderr.txt"

cat >"$mock_help" <<'HELP'
Usage: gemini [options] [command]
      --approval-mode             Set the approval mode  [string] [choices: "default", "auto_edit", "yolo"]
  -o, --output-format             The format of the CLI output.  [string] [choices: "text", "json"]
HELP

cat >"$mock_bin" <<'MOCK'
#!/usr/bin/env bash
set -euo pipefail

if [[ "${1:-}" == "--help" ]]; then
  cat "${MOCK_HELP:?}"
  exit 0
fi

: >"${MOCK_LOG:?}"
for arg in "$@"; do
  printf '<%s>\n' "$arg" >>"$MOCK_LOG"
done

case "${MOCK_BEHAVIOR:-ok}" in
  ok)
    printf 'mock-ok\n'
    ;;
  auth-ok)
    printf 'gemini-auth-ok\n'
    ;;
  auth-polluted)
    printf 'gemini-auth-ok\nextra-context\n'
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

if [[ "${1:-}" == "-lc" && "${3:-}" == "_" && "${4:-}" == "gemini" ]]; then
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
  CONSULT_GEMINI_BIN="$mock_bin" \
    CONSULT_GEMINI_MODEL= \
    GEMINI_MODEL= \
    CONSULT_GEMINI_APPROVAL_MODE= \
    MOCK_HELP="$mock_help" \
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
  CONSULT_GEMINI_BIN= \
    CONSULT_GEMINI_MODEL= \
    GEMINI_MODEL= \
    CONSULT_GEMINI_APPROVAL_MODE= \
    MOCK_DISCOVERY_BIN="$mock_bin" \
    MOCK_HELP="$mock_help" \
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
assert_contains "$mock_log" "<--approval-mode=yolo>"
assert_contains "$mock_log" "<--output-format>"
assert_contains "$mock_log" "<text>"
assert_not_contains "$mock_log" "<--model>"
assert_not_contains "$mock_log" "<--skip-trust>"

run_wrapper 0 ok --model pro "hello"
assert_contains "$mock_log" "<--model>"
assert_contains "$mock_log" "<gemini-2.5-pro>"

run_wrapper 0 ok --model flash "hello"
assert_contains "$mock_log" "<gemini-2.5-flash>"

run_wrapper 0 ok --model lite "hello"
assert_contains "$mock_log" "<gemini-2.5-flash-lite>"

run_wrapper 0 ok --model flash-lite "hello"
assert_contains "$mock_log" "<gemini-2.5-flash-lite>"

run_wrapper 0 ok --model gemini-3.1-pro-preview "hello"
assert_contains "$mock_log" "<gemini-3.1-pro-preview>"

run_wrapper 0 ok --model cli-default "hello"
assert_not_contains "$mock_log" "<--model>"

run_wrapper 0 ok --approval-mode plan "hello"
assert_contains "$mock_log" "<--approval-mode=default>"
assert_contains "$stderr_file" "does not support --approval-mode=plan"

run_wrapper 0 auth-ok --auth-smoke
assert_stdout_exact "gemini-auth-ok"

run_wrapper 65 auth-polluted --auth-smoke
assert_contains "$stderr_file" "did not return the expected exact output"

run_wrapper_discovered 0 ok "hello"
assert_contains "$stderr_file" "gemini: $mock_bin"
assert_contains "$mock_log" "<--approval-mode=yolo>"

set +e
CONSULT_GEMINI_BIN="$tmp_dir/missing-gemini" "$wrapper" "hello" >"$stdout_file" 2>"$stderr_file" </dev/null
missing_status=$?
set -e
[[ "$missing_status" -eq 127 ]] || fail "expected missing CONSULT_GEMINI_BIN to exit 127, got $missing_status"
assert_contains "$stderr_file" "CONSULT_GEMINI_BIN is set but is not executable"

echo "consult_gemini_cli.sh tests passed"
