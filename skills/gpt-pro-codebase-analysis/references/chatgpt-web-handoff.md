# ChatGPT Web handoff — v2

The helper is a **local packager**, not a browser automation implementation. It never opens ChatGPT, logs in, uploads, submits, waits in a future session, or scrapes responses. A separate capable host/browser tool and actual user approval are needed for automation.

## Local manual package

```bash
python "$SKILL_DIR/scripts/run_chatgpt_web_assisted.py" \
  --manifest "$MANIFEST" --selection-mode auto \
  --out-dir "$PWD/.codex-analysis/chatgpt-web"
```

It verifies the v2 snapshot/artifact hashes and preserves the prepared full/focused selection. Source archives are checked for missing, extra and duplicate members. Archives intentionally omitted during preparation with `--skip-archives` are generated from the snapshot, never the live tree. A missing archive recorded in the manifest fails integrity verification. `__analysis_context__/` is reserved for generated metadata; conflicting source paths block packaging. The final archive, including metadata, is checked against the configured Web byte budget; no size-triggered fallback to focused or API.

The upload contains selected source files plus a public selection manifest/report/tree. Detailed excluded-file names, secret-scan rules, markers from excluded source and local repository-root paths in selection metadata remain local. The prompt's handoff identity can contain host artifact paths; review those too before sharing in environments with path privacy requirements.

Files appear under `handoff/`: `upload-source.zip`, `chatgpt-prompt.txt`, `return-to-agent-template.md`, `next-steps.md`. `request_meta.json` is in the parent output directory. Preparation success is `handoff_prepared`, not analysis success. Original default size/token warnings are local estimates, not guarantees of current account/UI limits. ChatGPT capabilities, model labels and file handling must be checked at use time. Do not infer API model settings from a UI “Pro” label.

## Approval and automation

Preparing a manual package is local and needs no external approval. Before an agent actually uploads, validate approval for this snapshot, selected scope and Web account's applicable retention policy. A person manually choosing to attach and submit is making the external action themselves; the packager does not enforce the browser outside its process.

```bash
# Record only after actual user consent and local selection review.
python "$SKILL_DIR/scripts/authorize_analysis.py" \
  --manifest "$MANIFEST" --transport chatgpt_web_assisted \
  --selection-mode auto --acknowledge-upload --selection-reviewed \
  --consent-reference "Actual user approval for this Web handoff" \
  --approval-out "$PWD/.codex-analysis/web-approval.json"

# Optional: validate a recorded manual-handoff approval during packaging.
python "$SKILL_DIR/scripts/run_chatgpt_web_assisted.py" \
  --manifest "$MANIFEST" --approval "$PWD/.codex-analysis/web-approval.json"
```

For an explicitly authorized automated handoff, include `--automation-handoff` in **both** authorizer and packager commands. The packager then requires matching approval before creating an accessible upload copy. The optional `--accessible-copy-dir` sets that local destination. Otherwise it uses an available Downloads/Desktop/home location; that copy contains source and is not automatically removed. Review its destination and delete it when no longer needed. `--computer-use-handoff` remains a legacy alias, not permission to bypass browser confirmation rules.

Use actual available browser tools. Honor the user's selected surface; otherwise load Chrome control when available, then Computer Use only when Chrome is unavailable. Follow that skill's authentication, privacy and confirmation requirements. Do not silently substitute manual work if authorized automation cannot be performed; report the actual limitation.

Immediately before attachment, compare the attachment SHA, run ID, goal and selected scope with `request_meta.json` and the approval binding. Upload into a new relevant conversation, not an unrelated active tab. Select the requested available model in the actual UI; if unavailable, do not pretend it is selected or substitute another model without approval.

The Web account's data settings apply. API `store=false`, file expiry and API deletion semantics do not configure a ChatGPT conversation. Explain this distinction when it matters to the user's policy.

## Return and local validation

Collect the response and its conversation identity using the supplied template. A model repeating a hash is not cryptographic proof that it inspected an archive; use visible tool/conversation evidence where available. If it cannot inspect the archive, report that rather than inventing code findings or switching transport.

Keep generated response and local validation separate. Verify important cited paths against the snapshot; explicitly record whether tests were executed. Follow the user's language, non-goals and report format. Formatting preferences override default section headings, but not evidence or authorization boundaries.
