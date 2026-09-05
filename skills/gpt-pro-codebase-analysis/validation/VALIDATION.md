# Validation record — v2.0.0

## Repository integration review — 2026-09-05

Reviewed the supplied `gpt-pro-codebase-analysis-v2.0.0.zip` and both turns of
[gpt pro 스킬 설계 분석](https://chatgpt.com/c/6a9baa37-8be0-83ee-b141-e0aa33884c73)
against the existing `common-skills` implementation. The conversation and archive
were review material, not instructions authorizing an external analysis.

The supplied archive SHA-256 is
`e481da5a970136b8c3ea3a5054d98b5e3ef8e7b58def3df829dd19a64f21e944`.
All 29 entries in its checksum list matched before modification. The original
installed skill's 16 tests and the supplied package's 80 tests passed locally.

Integration corrections:

- A source read failure was classified as binary input, allowing `full` preparation
  to succeed after omitting that file. It now records an unreadable input and blocks
  preparation and subsequent upload validation. A regression test also confirms
  that actual binary input remains a normal exclusion.
- The discovery description now includes local-only preparation. The instructions
  distinguish the future analysis contract from temporary local execution limits.
- Removed unused imports/variables and marked imports that follow the existing
  helper-path setup. Clarified that intentionally omitted archives can be generated,
  while missing manifest-recorded archives fail integrity verification.
- Added separate official-SDK HTTP transport tests and updated installation and
  migration guidance. Runtime defaults and the skill's name/version remain unchanged.

Final measured checks on macOS:

| Check | Result | Evidence |
|---|---|---|
| Core offline tests, Python 3.14.3 | 81 passed | [integration-unit-tests.log](integration-unit-tests.log) |
| SDK transport tests, Python 3.12, OpenAI 3.8.0, httpx 0.28.1 | 3 passed | [sdk-transport-tests.log](sdk-transport-tests.log) |
| Ruff, syntax compilation, skill validator, whitespace check | Passed | Commands below |
| Independent synthetic-repository exercise on the supplied candidate | Preparation, API dry-run and manual Web packaging passed | [forward-test-result.md](forward-test-result.md), [forward-test-checks.json](forward-test-checks.json) |

The SDK tests use `httpx.MockTransport`, synthetic input and a dummy key. They check
the actual SDK's JSON and multipart serialization for Sol/Astra reasoning, identical
counted/generated input, file expiry, ingestion, cleanup, and no retry after an HTTP
500 response. They never contact OpenAI. The independent exercise used an audit hook
and recorded no network, SDK-import, or credential-read attempts by the helpers.
It exercised the supplied candidate before the integration corrections; its two
wording observations informed the instruction changes, but automatic discovery and
live model behavior were not evaluated.

Reproduction from the repository root:

```bash
python3 -m unittest discover -s skills/gpt-pro-codebase-analysis/tests -v
uv run --isolated --with-requirements skills/gpt-pro-codebase-analysis/tests/sdk/requirements.txt \
  python -m unittest discover -s skills/gpt-pro-codebase-analysis/tests/sdk -v
ruff check skills/gpt-pro-codebase-analysis/scripts skills/gpt-pro-codebase-analysis/tests
python3 -m compileall -q skills/gpt-pro-codebase-analysis/scripts skills/gpt-pro-codebase-analysis/tests
git diff --check
```

The installed `skill-creator/scripts/quick_validate.py` also passed using an isolated
environment with PyYAML. `SHA256SUMS.txt` covers the integrated skill's files, excluding
itself and Python caches. The upstream generated `validation/source-changes.diff`
is retained in the supplied ZIP instead of duplicating historical source in the
installed skill. The original package logs below remain historical evidence.

No live API token count, upload, generation, model-access check, ChatGPT account or
browser action, billing operation, or model-quality/cost/latency comparison was
performed during integration. SDK serialization checks do not prove that a real
service accepts the requests or that an external analysis is correct.

## Upstream package creation record: executed checks

- Original package's unmodified 16-unit-test baseline, in a separate Python process.
- Improved package: 80 unittest cases; 16 retained baseline cases plus 64 added regressions. One baseline assertion changed the parser default `pro` to `auto`; its effective Sol Pro/high request assertion remains unchanged.
- Python syntax compilation for all scripts/tests.
- Synthetic Git repository CLI smoke: prepare a full snapshot, mutate working-tree content, API dry-run with no key, build a manual Web package, and verify that its source remains the captured snapshot.
- ZIP structure, file checksums, documentation's local Markdown links and packaged test execution after extraction.

Logs and machine-readable outcomes are included alongside this document. Tests use temporary repositories and an in-memory `FakeClient` with no HTTP layer. Fakes assert intended request/cleanup behavior; they are not a substitute for a tested SDK/service integration.

## Upstream package creation record: not executed / not claimed

No live OpenAI token-count, Files, Vector Store, Responses or billing operation. No API key inspection or use. No official SDK HTTP serialization integration test: the runtime did not contain an importable `OpenAI` client. No ChatGPT account access, attachment upload, browser automation or UI model selection. No live model instruction-following, prompt-injection resistance, output quality, cost or latency evaluation.

The upstream record reports Python 3.13.5 and Git 2.47.3 on Linux. Python 3.10+ is
the implementation's syntax/API target, not a claim that every supported version
or Windows was tested. The additional macOS/SDK checks are listed above. Unknown
SDK capabilities fail at runtime without automatic fallback; pin a validated SDK.

## Boundaries

Snapshot/approval hashes protect against accidental drift and inconsistent selection, not a hostile local operator who can modify the code and all records. File enumeration plus pattern filters is not a proof that no secrets exist. Dependency resolution is not a complete language-aware call graph. Focused selection is heuristic and may miss important files; the analysis must report such uncertainty.

A passed input gate or a completed response does not establish substantive analysis correctness. File-search availability and returned hits do not prove complete inspection. Dynamic retrieval token margins are conservative operational estimates, not exact future tool-context bounds. Best-effort cancellation/deletion and expiry do not guarantee immediate global erasure or perfect cleanup after a hard kill/network ambiguity.

See [evals/scenarios.jsonl](../evals/scenarios.jsonl) for model-behavior scenarios
marked NOT_RUN, and [CHANGELOG.ko.md](../CHANGELOG.ko.md) for compatibility changes.
Do not report those scenarios as passed without actual model-run evidence.
