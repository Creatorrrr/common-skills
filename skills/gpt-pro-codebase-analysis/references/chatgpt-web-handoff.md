# ChatGPT Web handoff

## Contents

1. Authorization boundary
2. Prepare the handoff
3. Manual handoff
4. Computer Use exception
5. Identity verification
6. Failure behavior
7. Archived runs

## Authorization boundary

`chatgpt_web_assisted` is a manual handoff by default. Without an explicit current-turn request to use Computer Use, do not:

- open ChatGPT Web
- automate a browser
- attach or submit files
- scrape or ingest the answer
- use Playwright, shell browser control, or another automation fallback

Computer Use availability is not authorization. It becomes usable only when the current request explicitly opts into Computer Use for this handoff.

For ChatGPT Web Pro, select Extended reasoning unless the user requests another level. State before submission that the analysis may take more than 30 minutes.

## Prepare the handoff

Run the manual preparation helper:

```bash
python <skill-dir>/scripts/run_chatgpt_web_assisted.py \
  --manifest .codex-analysis/context/manifest.json \
  --goal "<user goal>" \
  --selection-mode auto
```

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

Validate that every selected file appears in the archive before returning it.

## Manual handoff

For the default manual path:

1. Return the canonical archive, prompt, metadata, and next-step paths.
2. Tell the user to upload `handoff/upload-source.zip` in ChatGPT Web.
3. Tell the user to select Pro with Extended reasoning unless they requested another level.
4. Tell the user to paste all of `chatgpt-prompt.txt`.
5. Do not create a duplicate upload copy under Downloads or Desktop.
6. Do not operate ChatGPT Web on the user's behalf.

## Computer Use exception

Only after explicit opt-in, prepare with:

```bash
python <skill-dir>/scripts/run_chatgpt_web_assisted.py \
  --manifest .codex-analysis/context/manifest.json \
  --goal "<user goal>" \
  --selection-mode auto \
  --computer-use-handoff
```

This creates a run-id-named accessible copy such as `~/Downloads/upload-source-<run_id>.zip` and records it in `request_meta.json`.

Then:

1. Open a new browser window for `chatgpt.com`; do not reuse an unrelated active ChatGPT tab.
2. If authentication is required, pause and ask the user to authenticate.
3. Record the immutable handoff identity before submission.
4. Select Pro with Extended reasoning unless directed otherwise.
5. Attach the recorded `attachment_path` through ChatGPT's attach button and the OS file picker.
6. Paste the complete generated prompt and submit.
7. Wait for completion.
8. Verify the visible conversation against the immutable identity before collecting the answer.

Never substitute Playwright or another automation method if Computer Use fails.

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

If several tabs or sessions exist and the match is uncertain, stop and ask the user to identify the correct tab or rerun in a fresh window.

## Failure behavior

If preparation fails:

- do not switch to Responses API
- do not change full or focused selection silently
- report the exact validation or upload-size blocker

If Computer Use fails after preparation:

- stop browser automation
- return the canonical handoff paths and partial browser state
- do not use another browser-control mechanism

If ChatGPT reports that it cannot inspect the archive reliably, return that result and ask the user how to proceed. Do not convert it into file-specific findings.

## Archived runs

To prepare a handoff from an older immutable context:

```bash
python <skill-dir>/scripts/run_chatgpt_web_assisted.py \
  --manifest .codex-analysis/history/<run_id>/context/manifest.json \
  --goal "Continue the archived analysis" \
  --selection-mode auto
```

Write the handoff beside the archived run. Preserve prepared identity and use current paths only for file lookup.
