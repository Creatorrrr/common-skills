# ChatGPT Web handoff

## Contents

1. Authorization boundary
2. Prepare the handoff
3. Choose the interaction surface
4. Manual handoff
5. Chrome automation
6. Computer Use fallback
7. Identity verification
8. Failure behavior
9. Archived runs

## Authorization boundary

`chatgpt_web_assisted` is manual by default. Browser-control availability is not authorization. Without an explicit current-request instruction to automate this ChatGPT Web handoff, do not:

- open ChatGPT Web
- automate a browser
- attach or submit files
- collect the answer from the page
- use Playwright, shell browser control, or another automation fallback

An explicit request to automate `chatgpt_web_assisted`, made after the repository-upload warning and mode confirmation, authorizes attaching the prepared archive to ChatGPT. If the request does not clearly cover that upload, pause immediately before attaching the file and obtain confirmation.

For ChatGPT Web, select the `Pro` model unless the user requests another model. Do not require a separate reasoning-level selection. State before submission that the analysis may take more than 30 minutes.

## Prepare the handoff

For a manual handoff, run:

```bash
python <skill-dir>/scripts/run_chatgpt_web_assisted.py \
  --manifest .codex-analysis/context/manifest.json \
  --goal "<user goal>" \
  --selection-mode auto
```

For an explicitly automated handoff, add `--automation-handoff`:

```bash
python <skill-dir>/scripts/run_chatgpt_web_assisted.py \
  --manifest .codex-analysis/context/manifest.json \
  --goal "<user goal>" \
  --selection-mode auto \
  --automation-handoff
```

`--computer-use-handoff` remains a compatibility alias for `--automation-handoff`; do not use it in new instructions.

The active handoff lives under `.codex-analysis/chatgpt-web/`:

- `handoff/upload-source.zip`
- `handoff/chatgpt-prompt.txt`
- `handoff/next-steps.md`
- `handoff/return-to-agent-template.md`
- `request_meta.json`

The upload archive includes audit artifacts under `__analysis_context__/`:

- `selection-manifest.json`
- `selection-report.md`
- `repo_tree.txt` when available

Validate that every selected file appears in the archive before returning it. Automated preparation also creates a run-id-named accessible copy such as `~/Downloads/upload-source-<run_id>.zip` and records the exact attachment path and SHA-256 in `request_meta.json`.

## Choose the interaction surface

For an explicitly automated handoff, use this order:

1. Honor a browser-control surface explicitly required by the user.
2. Otherwise, if `$chrome:control-chrome` is available in the current session and its extension binding can initialize, use Chrome.
3. If Chrome control is unavailable, use `@Computer Use` when its skill and runtime are available.
4. If neither is available, stop automation and return the manual handoff files.

Do not treat an installed plugin alone as proof that its runtime is usable. Read the selected control skill completely before interaction and follow its current runtime, documentation, authentication, file-upload, and confirmation rules. Do not combine browser-control surfaces during a healthy run.

## Manual handoff

For the default manual path:

1. Return the canonical archive, prompt, metadata, and next-step paths.
2. Tell the user to upload `handoff/upload-source.zip` in ChatGPT Web.
3. Tell the user to select `Pro` in the model picker unless they requested another model.
4. Tell the user to paste all of `chatgpt-prompt.txt`.
5. Do not create a duplicate upload copy under Downloads or Desktop.
6. Do not operate ChatGPT Web on the user's behalf.

## Chrome automation

When Chrome is selected:

1. Read and follow `$chrome:control-chrome` completely.
2. Use the Chrome skill's browser-client runtime and extension browser binding. Read the full browser documentation required by that skill before the first interaction.
3. If setup or communication fails, follow the skill's `chrome-troubleshooting` procedure before declaring Chrome unavailable.
4. Open a fresh ChatGPT conversation in Chrome; do not reuse an unrelated active tab or conversation.
5. If ChatGPT authentication is required, pause and ask the user to sign in in Chrome. Do not expose credentials, cookies, or session tokens.
6. Record the immutable handoff identity before submission.
7. Select `Pro` in the model picker unless directed otherwise.
8. Attach the recorded `attachment_path`, paste the complete generated prompt, and submit.
9. Wait for completion while keeping the user informed during a long run.
10. Verify the visible conversation against the immutable identity before collecting the full answer.

Use only the interaction mechanisms authorized by the Chrome skill. Do not substitute Playwright, shell browser control, or raw Chrome debugging APIs.

## Computer Use fallback

Use Computer Use only when the user explicitly required it or a generic automation request cannot use Chrome control.

1. Read and follow the available Computer Use skill completely.
2. Use its plugin-owned client and persistent runtime rather than standalone UI automation.
3. Open a fresh ChatGPT conversation; do not reuse an unrelated active conversation.
4. If authentication is required, pause and ask the user to authenticate.
5. Record the immutable handoff identity before submission.
6. Select `Pro` in the model picker unless directed otherwise.
7. Attach the recorded `attachment_path` through ChatGPT's attach control and the OS file picker.
8. Paste the complete generated prompt, submit, and wait for completion.
9. Verify the visible conversation against the immutable identity before collecting the full answer.

Do not use Computer Use merely because it is installed. The current request must explicitly authorize automation, and the selected skill's confirmation rules still apply.

## Identity verification

Treat these fields as immutable submitted identity:

- `prepared_handoff_identity`
- `prompt_handoff_identity_block`
- `prompt_handoff_identity_sha256`
- run id
- user goal
- archive SHA-256
- actual attachment name and SHA-256

Use `current_artifact_paths` only to locate files after archival. Do not rewrite immutable identity when an active run moves into history.

Before importing a browser result, match:

- current goal
- run id
- prompt identity hash and visible identity block
- uploaded archive presence
- archive SHA when visible or inferable
- run-id-named attachment when visible or inferable

Do not identify the right answer merely by tab position, completion time, or displayed filename. ChatGPT may rename duplicate uploads.

If several tabs or sessions exist and the match is uncertain, stop and ask the user to identify the correct tab or rerun in a fresh conversation.

## Failure behavior

If preparation fails:

- do not switch to Responses API
- do not change full or focused selection silently
- report the exact validation or upload-size blocker

If Chrome control fails after its required troubleshooting:

- for a generic automation request, continue with Computer Use only when it is available and its skill permits the same upload
- for an explicit Chrome-only request, ask before switching surfaces
- preserve the prepared handoff and report the Chrome failure

If Computer Use fails, or neither automation surface is usable:

- stop browser automation
- return the canonical handoff paths and any partial browser state
- do not use another browser-control mechanism

Falling back from browser automation to manual handoff does not authorize switching to Responses API. If ChatGPT reports that it cannot inspect the archive reliably, return that result and ask the user how to proceed. Do not convert it into file-specific findings.

## Archived runs

To prepare a handoff from an older immutable context:

```bash
python <skill-dir>/scripts/run_chatgpt_web_assisted.py \
  --manifest .codex-analysis/history/<run_id>/context/manifest.json \
  --goal "Continue the archived analysis" \
  --selection-mode auto
```

Write the handoff beside the archived run. Preserve prepared identity and use current paths only for file lookup. Add `--automation-handoff` only when the current request explicitly authorizes automation of that archived handoff.
