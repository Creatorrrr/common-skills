#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
wrapper="$script_dir/consult_codex_cli.sh"
tmp_dir="$(mktemp -d)"
mock_bin="$tmp_dir/codex"
mock_ps="$tmp_dir/ps"
mock_log="$tmp_dir/codex-args.log"
stdout_file="$tmp_dir/stdout.txt"
stderr_file="$tmp_dir/stderr.txt"
thread_id="11111111-2222-3333-4444-555555555555"

cat >"$mock_ps" <<'MOCK_PS'
#!/usr/bin/env bash
set -euo pipefail
# The runner's parent is this test shell. Present it as a non-Codex caller.
parent_pid="$(/bin/ps -o ppid= -p "$PPID")"
printf '%s 1 claude\n' "${parent_pid//[[:space:]]/}"
MOCK_PS
chmod +x "$mock_ps"

cat >"$mock_bin" <<'MOCK_CODEX'
#!/usr/bin/env bash
set -euo pipefail
printf '%s\n' "$@" >"${MOCK_LOG:?}"
output_path=""
reported_id="${MOCK_THREAD_ID:?}"
previous=""
for arg in "$@"; do
  if [[ "$previous" == "-o" ]]; then
    output_path="$arg"
  fi
  if [[ "$arg" =~ ^[0-9a-f]{8}-([0-9a-f]{4}-){3}[0-9a-f]{12}$ ]]; then
    reported_id="$arg"
  fi
  previous="$arg"
done
[[ -n "$output_path" ]]
printf 'mock-codex-answer\n' >"$output_path"
printf '{"type":"thread.started","thread_id":"%s"}\n' "$reported_id"
printf '{"type":"turn.completed"}\n'
MOCK_CODEX
chmod +x "$mock_bin"

fail() {
  printf 'FAIL: %s\n' "$*" >&2
  cat "$stdout_file" "$stderr_file" "$mock_log" >&2
  exit 1
}

run_wrapper() {
  local caller_id="$1"
  shift
  : >"$mock_log"
  CONSULT_CODEX_BIN="$mock_bin" \
    CONSULT_CODEX_STATE_DIR="$tmp_dir/state" \
    MOCK_LOG="$mock_log" \
    MOCK_THREAD_ID="$thread_id" \
    PATH="$tmp_dir:$PATH" \
    "$wrapper" -C "$tmp_dir" --caller-kind claude --caller-session-id "$caller_id" "$@" \
    >"$stdout_file" 2>"$stderr_file" </dev/null
}

run_wrapper caller-session-0001 "first question"
[[ "$(cat "$stdout_file")" == "mock-codex-answer" ]] || fail "first answer missing"
grep -Eq '^--approve-for-me$' "$mock_log" || fail "approval flag missing"
grep -Eq '^exec$' "$mock_log" || fail "exec command missing"
! grep -Eq '^resume$' "$mock_log" || fail "unexpected resume on first call"

run_wrapper caller-session-0001 "follow-up question"
grep -Eq '^resume$' "$mock_log" || fail "follow-up did not resume"
grep -Eq "^$thread_id$" "$mock_log" || fail "saved thread ID was not used"
grep -q 'consultation: resume' "$stderr_file" || fail "resume was not reported"

run_wrapper caller-session-0002 "different caller question"
! grep -Eq '^resume$' "$mock_log" || fail "different caller resumed the first caller's thread"
grep -q 'consultation: new' "$stderr_file" || fail "new caller did not start a new thread"

printf 'consult_codex_cli.sh tests passed\n'
