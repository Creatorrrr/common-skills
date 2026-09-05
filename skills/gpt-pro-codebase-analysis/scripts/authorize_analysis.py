#!/usr/bin/env python3
"""Record already-obtained user consent; this command does not grant consent or send data.
This is a local audit guard, not a cryptographic authorization system.
"""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from context_integrity import (read_manifest, verify_manifest, resolve_selection,
                               binding, execution_options, write_json)
from run_gpt_pro_analysis import build_parser as api_parser, resolve_run


def build_parser():
    p = api_parser()
    p.description = __doc__
    p.add_argument('--transport', choices=['responses_api', 'chatgpt_web_assisted'], required=True)
    p.add_argument('--selection-mode', choices=['auto', 'full', 'focused'], default='auto')
    p.add_argument('--automation-handoff', action='store_true')
    p.add_argument('--acknowledge-upload', action='store_true', help='Use ONLY after actual user consent to the target, scope and applicable retention settings.')
    p.add_argument('--selection-reviewed', action='store_true', help='The included/excluded list has actually been checked.')
    p.add_argument('--consent-reference', required=True, help='Nonsecret reference/summary of the actual consent; never fabricate approval.')
    p.add_argument('--approval-out', required=True)
    return p


def execute(args: Any) -> int:
    if not args.acknowledge_upload or not args.selection_reviewed or not args.consent_reference.strip():
        raise ValueError('Actual user consent and selection review must precede recording approval.')
    path = Path(args.approval_out).resolve()
    if path.exists():
        raise ValueError('Approval destination already exists; choose a new file instead of overwriting audit evidence.')
    manifest = read_manifest(Path(args.manifest).resolve())
    verify_manifest(manifest)
    if path.is_relative_to(Path(manifest['context_root'])):
        raise ValueError('Store approval outside the immutable prepared context.')
    if args.transport == 'responses_api':
        _, key = resolve_run(args, manifest)
        options = execution_options(args)
    else:
        from run_chatgpt_web_assisted import web_options
        key = resolve_selection(manifest, args.selection_mode)
        options = web_options(args.automation_handoff)
    value = {'schema_version': 1, 'approved': True, 'selection_reviewed': True,
             'transport': args.transport, 'binding': binding(manifest, key),
             'execution_options': options, 'consent_reference': args.consent_reference,
             'recorded_at': datetime.now(timezone.utc).isoformat(),
             'notice': 'Records existing consent only; writable local files are not a security boundary.'}
    write_json(path, value)
    print(json.dumps({'approval_record': str(path), 'transport': args.transport,
                      'selection': key, 'external_calls': 0}))
    return 0


def main() -> int:
    try:
        return execute(build_parser().parse_args())
    except Exception as exc:
        print(f'Approval record not created ({type(exc).__name__}): {exc}')
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
