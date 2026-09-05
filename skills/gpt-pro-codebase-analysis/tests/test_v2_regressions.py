"""Offline invariant tests. FakeClient records requests in memory; never contacts OpenAI."""
from __future__ import annotations
import contextlib
import copy
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from types import SimpleNamespace as NS
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import api_resources as resources
import authorize_analysis as authorize
import context_integrity as integrity
import model_profiles as models
import prepare_analysis_context as prep
import run_chatgpt_web_assisted as web
import run_gpt_pro_analysis as api
from analysis_run import archive_active_run
from run_attempt import Attempt


class FakeClient:
    """Minimal SDK interface; intentionally no HTTP client, socket or credential use."""
    def __init__(self, token_count=1000, response_status='completed', fail_create=False,
                 fail_ingestion=False, fail_delete=False, interrupt=False):
        self.token_count = token_count
        self.response_status = response_status
        self.fail_create = fail_create
        self.fail_ingestion = fail_ingestion
        self.fail_delete = fail_delete
        self.interrupt = interrupt
        self.created_requests = []
        self.counted_requests = []
        self.file_data = {}
        self.file_create_args = []
        self.stores = {}
        self.deleted = []
        self.attachments = {}
        self.cancelled = []
        self.files = NS(create=self.create_file, delete=lambda x: self.delete('file', x),
                        content=lambda x: io.BytesIO(self.file_data[x]))
        self.vector_stores = NS(create=self.create_store, retrieve=lambda x: self.stores[x],
                               delete=lambda x: self.delete('vector_store', x),
                               files=NS(create=self.attach, retrieve=self.retrieve_member,
                                        list=lambda **kw: iter(self.attachments[kw['vector_store_id']].values())))
        self.responses = NS(input_tokens=NS(count=self.count), create=self.create_response,
                            retrieve=lambda x: NS(id=x, status='completed', output_text='Reviewed', output=[]),
                            cancel=self.cancel)

    def count(self, **kwargs):
        self.counted_requests.append(kwargs)
        return NS(input_tokens=self.token_count)

    def create_response(self, **kwargs):
        self.created_requests.append(kwargs)
        if self.interrupt:
            raise KeyboardInterrupt()
        if self.fail_create:
            raise ConnectionError('must-not-log-sensitive-request-body')
        return NS(id='resp-test', status=self.response_status, output_text='검토 결과: 근거 확인 필요', output=[])

    def create_file(self, **kwargs):
        ident = f'file-{len(self.file_data) + 1}'
        self.file_data[ident] = kwargs['file'][1]
        self.file_create_args.append(kwargs)
        return NS(id=ident)

    def create_store(self, **kwargs):
        ident = f'vs-{len(self.stores) + 1}'
        obj = NS(id=ident, status='completed', metadata=kwargs['metadata'])
        self.stores[ident] = obj
        self.attachments[ident] = {}
        return obj

    def attach(self, **kwargs):
        obj = NS(id=kwargs['file_id'], status='failed' if self.fail_ingestion else 'completed')
        self.attachments[kwargs['vector_store_id']][obj.id] = obj
        return obj

    def retrieve_member(self, **kwargs):
        return self.attachments[kwargs['vector_store_id']][kwargs['file_id']]

    def delete(self, kind, ident):
        if self.fail_delete:
            raise ConnectionError('unavailable')
        self.deleted.append((kind, ident))
        return NS(deleted=True)

    def cancel(self, ident):
        self.cancelled.append(ident)
        return NS(id=ident, status='cancelled')


class Fixture(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.repo = self.base / 'repo'
        self.repo.mkdir()
        subprocess.run(['git', 'init', '-q', str(self.repo)], check=True)
        self.put('main.py', 'def answer():\n    return 42\n')
        self.out = self.base / 'prepared'

    def put(self, path, text):
        p = self.repo / path
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(text if isinstance(text, bytes) else text.encode('utf-8'))
        return p

    def prepare(self, *extra, out=None):
        out = out or self.out
        argv = ['prepare', '--root', str(self.repo), '--out-dir', str(out),
                '--goal', '검증 목표', *extra]
        with mock.patch.object(sys, 'argv', argv), contextlib.redirect_stdout(io.StringIO()):
            code = prep.main()
        path = out / 'manifest.json'
        return code, integrity.read_manifest(path), path

    def arguments(self, path, *extra):
        return api.build_parser().parse_args(['--manifest', str(path), '--out-dir', str(self.base / 'run'), *extra])

    def approve(self, args, manifest):
        _, key = api.resolve_run(args, manifest)
        value = {'schema_version': 1, 'approved': True, 'selection_reviewed': True,
                 'transport': 'responses_api', 'binding': integrity.binding(manifest, key),
                 'execution_options': integrity.execution_options(args)}
        target = self.base / 'approval.json'
        integrity.write_json(target, value)
        args.approval = str(target)
        return value

    def execute(self, args, client):
        factory = mock.Mock(return_value=client)
        with mock.patch.dict(os.environ, {'OPENAI_API_KEY': 'offline-test-not-a-real-key'}), contextlib.redirect_stdout(io.StringIO()):
            value = api.execute(args, client_factory=factory)
        return value, factory

    def meta(self):
        return json.loads((self.base / 'run' / 'run_meta.json').read_text())


class SnapshotRegressionTests(Fixture):
    def test_read_error_blocks_full_preparation_instead_of_skipping_as_binary(self):
        unreadable = self.put('unreadable.py', 'important_source = True\n')
        self.put('asset.bin', b'\x00\xff')
        original_read = Path.read_bytes

        def read_bytes(path):
            if path.resolve() == unreadable.resolve():
                raise PermissionError('synthetic unreadable fixture')
            return original_read(path)

        with mock.patch.object(Path, 'read_bytes', read_bytes):
            code, manifest, _ = self.prepare('--mode', 'full')

        self.assertEqual(code, 1)
        records = {record['path']: record for record in manifest['files']}
        self.assertEqual(records['unreadable.py']['safety_status'], 'unreadable')
        self.assertEqual(records['asset.bin']['safety_status'], 'binary')
        with self.assertRaisesRegex(ValueError, 'blocking issues'):
            integrity.verify_manifest(manifest)

    def test_large_full_selection_stays_full_in_api_and_web(self):
        for i in range(2001):
            self.put(f'src/m{i:04d}.py', 'x=1\n')
        code, manifest, path = self.prepare('--mode', 'full')
        self.assertEqual(code, 0)
        self.assertEqual(manifest['mode_recommendation'], 'file_search_full')
        self.assertEqual(api.resolve_run(self.arguments(path), manifest), ('file_search_full', 'full'))
        selected, _ = web.choose_selection(manifest, self.out / 'snapshot/files', self.base / 'web', 'auto', 100_000_000)
        self.assertEqual(selected.file_count, 2002)

    def test_git_quoted_korean_space_and_quote_paths_are_preserved(self):
        names = ['결제.py', 'my file.py', 'quote"name.py']
        for name in names:
            self.put(name, '# 한글\n')
        subprocess.run(['git', '-C', str(self.repo), 'config', 'core.quotepath', 'true'], check=True)
        _, manifest, _ = self.prepare()
        contents = integrity.verify_manifest(manifest)
        self.assertTrue(set(names).issubset(contents))

    def test_root_and_nested_secret_folders_never_selected(self):
        for name in ['secrets/token.json', 'src/secrets/token.json', '.aws/config', 'credentials/key.py']:
            self.put(name, '{}')
        _, manifest, _ = self.prepare()
        self.assertEqual(set(integrity.verify_manifest(manifest)), {'main.py'})

    def test_content_secret_scan_logs_only_rule_not_value(self):
        secret = 'sk-' + 'a' * 50
        self.put('ordinary.py', f'key = "{secret}"\n')
        _, manifest, _ = self.prepare()
        self.assertNotIn('ordinary.py', integrity.verify_manifest(manifest))
        self.assertNotIn(secret, json.dumps(manifest))
        self.assertNotIn(secret, (self.out / 'selection-report.md').read_text())

    def test_live_edit_and_delete_do_not_change_snapshot_upload_bytes(self):
        _, manifest, _ = self.prepare()
        original = integrity.verify_manifest(manifest)['main.py']
        self.put('main.py', 'CHANGED')
        self.assertEqual(integrity.verify_manifest(manifest)['main.py'], original)
        (self.repo / 'main.py').unlink()
        self.assertEqual(integrity.verify_manifest(manifest)['main.py'], original)

    def test_snapshot_hash_mutation_is_rejected(self):
        _, manifest, _ = self.prepare()
        (self.out / 'snapshot/files/main.py').write_text('tampered')
        with self.assertRaisesRegex(ValueError, 'hash mismatch'):
            integrity.verify_manifest(manifest)

    def test_missing_snapshot_is_rejected(self):
        _, manifest, _ = self.prepare()
        (self.out / 'snapshot/files/main.py').unlink()
        with self.assertRaisesRegex(ValueError, 'missing or unsafe'):
            integrity.verify_manifest(manifest)

    def test_selection_missing_record_is_rejected(self):
        _, manifest, _ = self.prepare()
        manifest['selections']['full_files'].append('missing.py')
        with self.assertRaisesRegex(ValueError, 'exactly match'):
            integrity.verify_manifest(manifest)

    def test_manifest_legacy_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'v2 snapshot'):
            integrity.verify_manifest({'schema_version': 1})

    def test_explicit_scope_is_data_boundary_not_substring(self):
        self.put('src/core/a.py', 'a=1')
        self.put('other/src/core/a.py', 'not_authorized=1')
        _, manifest, _ = self.prepare('--scope', 'src/core')
        self.assertEqual(set(integrity.verify_manifest(manifest)), {'src/core/a.py'})

    def test_unknown_scope_blocks_preparation(self):
        code, manifest, _ = self.prepare('--scope', 'not-found')
        self.assertEqual(code, 1)
        with self.assertRaisesRegex(ValueError, 'blocking issues'):
            integrity.verify_manifest(manifest)

    def test_tracked_git_ignored_file_is_excluded(self):
        self.put('tracked.py', 'private=1')
        subprocess.run(['git', '-C', str(self.repo), 'add', 'tracked.py'], check=True)
        self.put('.gitignore', 'tracked.py\n')
        _, manifest, _ = self.prepare()
        self.assertNotIn('tracked.py', integrity.verify_manifest(manifest))

    def test_symlink_source_does_not_upload_target(self):
        external = self.base / 'external.py'
        external.write_text('not-authorized')
        (self.repo / 'link.py').symlink_to(external)
        code, manifest, _ = self.prepare()
        self.assertEqual(code, 1)
        self.assertNotIn('link.py', manifest['selections']['full_files'])

    def test_reusing_nonempty_custom_context_dir_is_rejected(self):
        self.prepare()
        with self.assertRaisesRegex(ValueError, 'not empty'):
            self.prepare()

    def test_moved_context_preserves_hashes_and_rehydrates_paths(self):
        _, before, path = self.prepare()
        dest = self.base / 'history' / 'context'
        dest.parent.mkdir()
        shutil.move(self.out, dest)
        after = integrity.read_manifest(dest / 'manifest.json')
        self.assertEqual(after['snapshot_id'], before['snapshot_id'])
        self.assertEqual(set(integrity.verify_manifest(after)), {'main.py'})

    def test_empty_and_crlf_sources_preserve_raw_bytes(self):
        self.put('empty.py', '')
        self.put('windows.py', b'x=1\r\ny=2\r\n')
        _, manifest, _ = self.prepare()
        contents = integrity.verify_manifest(manifest)
        self.assertEqual(contents['empty.py'], b'')
        self.assertEqual(contents['windows.py'], b'x=1\r\ny=2\r\n')

    def test_korean_goal_keywords_are_not_empty(self):
        self.assertTrue(prep.goal_keywords('결제 인증 흐름 검토'))

    def test_control_character_paths_fail_closed(self):
        self.put('bad\nname.py', 'x=1')
        code, manifest, _ = self.prepare()
        self.assertEqual(code, 1)
        self.assertTrue(manifest['blocking_issues'])

    def test_archive_active_run_refuses_locked_attempt(self):
        root = self.base / '.codex-analysis'
        (root / 'gpt-pro').mkdir(parents=True)
        (root / 'gpt-pro/.run.lock').write_text('pid')
        with self.assertRaisesRegex(ValueError, 'run lock'):
            archive_active_run(root)


class NormalizationTests(unittest.TestCase):
    def test_fragments_reconstruct_entire_source_without_truncation(self):
        text = '한글\r\n' + ('x' * 43) + '\n끝\u2028문장\n'
        docs = resources.normalized_documents({'src/test.tsx': text.encode()}, ['src/test.tsx'], chunk_chars=11)
        recovered = []
        for d in docs:
            body = d['data'].decode().split('\nBEGIN UNTRUSTED SOURCE\n', 1)[1].rsplit('\nEND UNTRUSTED SOURCE\n', 1)[0]
            recovered.append(re.sub(r'(?m)^\d{6,}: ', '', body))
            self.assertTrue(d['filename'].endswith('.txt'))
        self.assertEqual(''.join(recovered), text)
        self.assertTrue(any(d['column_start'] > 1 for d in docs))

    def test_utf16_and_empty_sources_are_represented(self):
        data = {'a.toml': '설정=1\n'.encode('utf-16'), 'empty.rs': b''}
        docs = resources.normalized_documents(data, list(data))
        self.assertEqual(len(docs), 2)
        self.assertIn('설정', docs[0]['data'].decode())

    def test_missing_selected_file_prevents_any_resource_creation(self):
        fake = FakeClient()
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, 'exists.py').write_text('x=1')
            with self.assertRaises(ValueError):
                api.upload_vector_store_files(fake, 'test', Path(tmp), ['exists.py', 'missing.py'])
        self.assertFalse(fake.stores)
        self.assertFalse(fake.file_data)

    def test_partial_ingestion_is_cleaned_and_rejected(self):
        fake = FakeClient(fail_ingestion=True)
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, 'a.py').write_text('x=1')
            with self.assertRaisesRegex(RuntimeError, 'partial analysis'):
                api.upload_vector_store_files(fake, 'test', Path(tmp), ['a.py'])
        self.assertEqual(set(fake.deleted), {('vector_store', 'vs-1'), ('file', 'file-1')})

    def test_reuse_verifies_remote_membership_and_content(self):
        fake = FakeClient()
        docs = resources.normalized_documents({'a.py': b'a=1'}, ['a.py'])
        owned = resources.OwnedResources(fake)
        vs, entries = resources.upload_documents(fake, 'test', docs, owned=owned, snapshot_id='s', selection_hash='h')
        receipt = {'vector_store_id': vs.id, 'binding': vs.metadata, 'files': entries}
        self.assertIs(resources.verify_reused_store(fake, vs.id, receipt, docs, 's', 'h'), vs)
        self.assertFalse(fake.deleted)
        fake.file_data[entries[0]['file_id']] = b'tampered'
        with self.assertRaisesRegex(ValueError, 'Remote file bytes'):
            resources.verify_reused_store(fake, vs.id, receipt, docs, 's', 'h')

    def test_reuse_rejects_extra_remote_members(self):
        fake = FakeClient()
        docs = resources.normalized_documents({'a.py': b'a=1'}, ['a.py'])
        vs, entries = resources.upload_documents(fake, 'test', docs, owned=resources.OwnedResources(fake), snapshot_id='s', selection_hash='h')
        receipt = {'vector_store_id': vs.id, 'binding': vs.metadata, 'files': entries}
        fake.attachments[vs.id]['extra'] = NS(id='extra', status='completed')
        with self.assertRaisesRegex(ValueError, 'membership'):
            resources.verify_reused_store(fake, vs.id, receipt, docs, 's', 'h')

    def test_ingestion_polling_is_bounded(self):
        fake = FakeClient()
        fake.retrieve_member = lambda **kw: NS(status='in_progress')
        fake.vector_stores.files.retrieve = fake.retrieve_member
        docs = resources.normalized_documents({'a.py': b'a=1'}, ['a.py'])
        with mock.patch.object(resources, 'monotonic', side_effect=[0, 2]):
            with self.assertRaises(TimeoutError):
                resources.upload_documents(fake, 'test', docs, owned=resources.OwnedResources(fake), snapshot_id='s', selection_hash='h', timeout_seconds=1)


class ExecutionTests(Fixture):
    def test_dry_run_needs_neither_key_nor_approval(self):
        _, _, path = self.prepare()
        args = self.arguments(path, '--dry-run')
        factory = mock.Mock(side_effect=AssertionError('no client in dry-run'))
        with mock.patch.dict(os.environ, {}, clear=True), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(api.execute(args, client_factory=factory), 0)
        factory.assert_not_called()
        self.assertEqual(self.meta()['status'], 'dry_run_completed')

    def test_missing_approval_prevents_client_creation(self):
        _, _, path = self.prepare()
        factory = mock.Mock()
        with self.assertRaisesRegex(ValueError, '--approval'):
            api.execute(self.arguments(path), client_factory=factory)
        factory.assert_not_called()
        self.assertEqual(self.meta()['status'], 'failed')

    def test_exact_counted_payload_is_sent_and_verification_stays_pending(self):
        _, manifest, path = self.prepare()
        args = self.arguments(path, '--mode', 'direct')
        self.approve(args, manifest)
        fake = FakeClient()
        code, factory = self.execute(args, fake)
        self.assertEqual(code, 0)
        self.assertEqual(fake.counted_requests[0]['input'], fake.created_requests[0]['input'])
        self.assertEqual(fake.counted_requests[0]['instructions'], fake.created_requests[0]['instructions'])
        self.assertEqual(self.meta()['analysis_validation'], 'pending')
        self.assertEqual(self.meta()['local_verification'], 'pending')
        self.assertFalse(fake.created_requests[0]['store'])
        self.assertFalse(fake.created_requests[0]['background'])
        self.assertEqual(factory.call_args.kwargs['max_retries'], 0)
        self.assertEqual(factory.call_args.kwargs['base_url'], 'https://api.openai.com/v1')
        self.assertFalse(fake.file_data)

    def test_overbudget_count_blocks_response_submission(self):
        _, manifest, path = self.prepare()
        args = self.arguments(path)
        self.approve(args, manifest)
        fake = FakeClient(token_count=5_000_000)
        with self.assertRaises(ValueError):
            self.execute(args, fake)
        self.assertFalse(fake.created_requests)
        self.assertEqual(self.meta()['status'], 'failed')

    def test_unusable_token_count_blocks_submission(self):
        _, manifest, path = self.prepare()
        args = self.arguments(path)
        self.approve(args, manifest)
        fake = FakeClient(token_count=None)
        with self.assertRaisesRegex(ValueError, 'usable count'):
            self.execute(args, fake)
        self.assertFalse(fake.created_requests)

    def test_changed_retention_invalidates_approval(self):
        _, manifest, path = self.prepare()
        args = self.arguments(path)
        self.approve(args, manifest)
        args.store = True
        with self.assertRaisesRegex(ValueError, 'settings differ'):
            self.execute(args, FakeClient())

    def test_changed_user_contract_invalidates_approval(self):
        _, manifest, _ = self.prepare()
        args = self.arguments(self.out / 'manifest.json')
        approval = self.approve(args, manifest)
        manifest['request_contract']['output_language'] = 'English'
        with self.assertRaisesRegex(ValueError, 'request contract'):
            integrity.validate_approval(approval, manifest, 'full', 'responses_api', integrity.execution_options(args))

    def test_transport_fallback_is_rejected(self):
        _, manifest, path = self.prepare()
        args = self.arguments(path)
        approval = self.approve(args, manifest)
        with self.assertRaisesRegex(ValueError, 'different transport'):
            integrity.validate_approval(approval, manifest, 'full', 'chatgpt_web_assisted', {})

    def test_exception_archives_stale_success_without_logging_request_body(self):
        _, manifest, path = self.prepare()
        args = self.arguments(path)
        self.approve(args, manifest)
        self.execute(args, FakeClient())
        with self.assertRaises(ConnectionError):
            self.execute(args, FakeClient(fail_create=True))
        self.assertFalse((self.base / 'run/analysis_report.md').exists())
        self.assertEqual(self.meta()['status'], 'failed')
        self.assertTrue(list((self.base / 'run/attempts').rglob('analysis_report.md')))
        self.assertNotIn('must-not-log-sensitive-request-body', json.dumps(self.meta()))
        self.assertFalse((self.base / 'run/.run.lock').exists())

    def test_retrieval_success_cleans_owned_files_and_store(self):
        _, manifest, path = self.prepare('--mode', 'full')
        args = self.arguments(path, '--mode', 'file_search_full')
        self.approve(args, manifest)
        fake = FakeClient()
        code, _ = self.execute(args, fake)
        self.assertEqual(code, 0)
        self.assertEqual(set(fake.deleted), {('file', 'file-1'), ('vector_store', 'vs-1')})
        self.assertEqual(fake.file_create_args[0]['expires_after']['seconds'], 86400)

    def test_retrieval_overbudget_cleans_already_created_resources(self):
        _, manifest, path = self.prepare()
        args = self.arguments(path, '--mode', 'file_search_full')
        self.approve(args, manifest)
        fake = FakeClient(token_count=5_000_000)
        with self.assertRaises(ValueError):
            self.execute(args, fake)
        self.assertFalse(fake.created_requests)
        self.assertEqual(len(fake.deleted), 2)

    def test_cleanup_failure_has_distinct_nonzero_exit(self):
        _, manifest, path = self.prepare()
        args = self.arguments(path, '--mode', 'file_search_full')
        self.approve(args, manifest)
        code, _ = self.execute(args, FakeClient(fail_delete=True))
        self.assertEqual(code, 2)
        self.assertEqual(self.meta()['status'], 'response_completed_cleanup_incomplete')
        self.assertEqual(self.meta()['cleanup_status'], 'incomplete')

    def test_explicit_retention_keeps_owned_resources(self):
        _, manifest, path = self.prepare()
        args = self.arguments(path, '--mode', 'file_search_full', '--resource-retention', 'retain')
        self.approve(args, manifest)
        fake = FakeClient()
        self.execute(args, fake)
        self.assertFalse(fake.deleted)
        self.assertEqual(self.meta()['cleanup_status'], 'retained_by_approval')

    def test_keyboard_interrupt_cleans_owned_resources_and_unlocks(self):
        _, manifest, path = self.prepare()
        args = self.arguments(path, '--mode', 'file_search_full')
        self.approve(args, manifest)
        fake = FakeClient(interrupt=True)
        with self.assertRaises(KeyboardInterrupt):
            self.execute(args, fake)
        self.assertEqual(len(fake.deleted), 2)
        self.assertEqual(self.meta()['status'], 'failed')
        self.assertFalse((self.base / 'run/.run.lock').exists())

    def test_noncompleted_response_has_no_success_report(self):
        _, manifest, path = self.prepare()
        args = self.arguments(path)
        self.approve(args, manifest)
        with self.assertRaisesRegex(ValueError, 'response_status=incomplete'):
            self.execute(args, FakeClient(response_status='incomplete'))
        self.assertFalse((self.base / 'run/analysis_report.md').exists())

    def test_active_attempt_cannot_be_overwritten(self):
        target = self.base / 'locked'
        with Attempt(target, {}):
            with self.assertRaises(FileExistsError):
                with Attempt(target, {}):
                    self.fail('second attempt must not enter')

    def test_authorizer_records_real_consent_flags_and_rejects_overwrite(self):
        _, _, path = self.prepare()
        output = self.base / 'consent.json'
        args = authorize.build_parser().parse_args([
            '--manifest', str(path), '--transport', 'responses_api', '--approval-out', str(output),
            '--consent-reference', 'Test fixture consent, not a user approval', '--acknowledge-upload', '--selection-reviewed'])
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(authorize.execute(args), 0)
        self.assertTrue(json.loads(output.read_text())['approved'])
        with self.assertRaisesRegex(ValueError, 'already exists'):
            authorize.execute(args)

    def test_authorizer_without_consent_does_not_write_record(self):
        _, _, path = self.prepare()
        output = self.base / 'consent.json'
        args = authorize.build_parser().parse_args([
            '--manifest', str(path), '--transport', 'responses_api', '--approval-out', str(output),
            '--consent-reference', 'not approved'])
        with self.assertRaisesRegex(ValueError, 'Actual user consent'):
            authorize.execute(args)
        self.assertFalse(output.exists())


class ModelTests(unittest.TestCase):
    def test_astra_native_reasoning_omits_mode(self):
        self.assertEqual(models.reasoning_config('gpt-6-astra', 'auto', 'high', 'auto'), {'effort': 'high'})

    def test_astra_none_rejected_before_api(self):
        with self.assertRaises(ValueError):
            models.reasoning_config('gpt-6-astra', 'standard', 'none', 'auto')

    def test_astra_unverified_pro_rejected(self):
        with self.assertRaises(ValueError):
            models.reasoning_config('gpt-6-astra', 'pro', 'high', 'auto')

    def test_unknown_model_rejected_instead_of_assumed_capabilities(self):
        with self.assertRaises(ValueError):
            models.reasoning_config('unverified-model', 'auto', 'high', 'auto')

    def test_output_tokens_reserved_with_input(self):
        with self.assertRaises(ValueError):
            models.enforce_token_budget('gpt-6-astra', 1_030_000, 32_000)


class WebTests(Fixture):
    def test_web_manual_package_is_snapshot_based_without_external_upload(self):
        _, manifest, path = self.prepare('--skip-archives', '--mode', 'full')
        original = integrity.verify_manifest(manifest)['main.py']
        self.put('main.py', 'changed-live-content')
        args = web.build_parser().parse_args(['--manifest', str(path), '--out-dir', str(self.base / 'web')])
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(web.execute(args), 0)
        with zipfile.ZipFile(self.base / 'web/handoff/upload-source.zip') as zf:
            self.assertEqual(zf.read('main.py'), original)
            public_manifest = json.loads(zf.read('__analysis_context__/selection-manifest.json'))
            self.assertNotIn('repo_root', public_manifest)
        meta = json.loads((self.base / 'web/run_meta.json').read_text())
        self.assertFalse(meta['external_upload_performed'])
        self.assertEqual(meta['status'], 'handoff_prepared')

    def test_web_oversize_does_not_fall_back_to_focused(self):
        _, manifest, _ = self.prepare('--mode', 'full')
        with self.assertRaises(ValueError):
            web.choose_selection(manifest, self.out / 'snapshot/files', self.base / 'web', 'auto', 1)

    def test_full_cannot_be_overridden_by_focused_flag(self):
        _, manifest, _ = self.prepare('--mode', 'full')
        with self.assertRaisesRegex(ValueError, 'cannot silently change'):
            integrity.resolve_selection(manifest, 'focused')

    def test_archive_extra_member_is_rejected(self):
        archive = self.base / 'extra.zip'
        with zipfile.ZipFile(archive, 'w') as z:
            z.writestr('main.py', 'x=1')
            z.writestr('not-approved.py', 'x=2')
        status, _, problems = web.validate_selected_members(archive, ['main.py'])
        self.assertEqual(status, 'selection_mismatch')
        self.assertIn('unexpected:not-approved.py', problems)

    def test_automation_copy_requires_approval(self):
        _, _, path = self.prepare()
        args = web.build_parser().parse_args(['--manifest', str(path), '--out-dir', str(self.base / 'web'), '--automation-handoff'])
        with self.assertRaisesRegex(ValueError, 'requires recorded'):
            web.execute(args)
        self.assertFalse((self.base / 'web/handoff').exists())

    def test_full_contract_reaches_api_and_web(self):
        value = {'objective': '검증 목표', 'scope': [], 'non_goals': ['스타일 변경 제외'],
                 'constraints': ['코드 수정 금지'], 'output_language': '한국어',
                 'output_format': '핵심 결론 세 문장', 'desired_depth': '간단하게'}
        f = self.base / 'contract.json'
        integrity.write_json(f, value)
        _, manifest, path = self.prepare('--contract', str(f))
        api_prompt = api.build_user_prompt('검증 목표', 'direct', [], 'direct', manifest)
        args = web.build_parser().parse_args(['--manifest', str(path), '--out-dir', str(self.base / 'web')])
        with contextlib.redirect_stdout(io.StringIO()):
            web.execute(args)
        web_prompt = (self.base / 'web/handoff/chatgpt-prompt.txt').read_text()
        for text in ['스타일 변경 제외', '코드 수정 금지', '한국어', '핵심 결론 세 문장']:
            self.assertIn(text, api_prompt)
            self.assertIn(text, web_prompt)
        self.assertEqual(web_prompt.count('검증 목표'), 1)
        self.assertIn('untrusted audit data', web_prompt)

    def test_final_archive_budget_includes_generated_context(self):
        _, manifest, path = self.prepare()
        original_size = Path(manifest['artifacts']['full_archive']).stat().st_size
        args = web.build_parser().parse_args(['--manifest', str(path), '--out-dir', str(self.base / 'web'),
                                             '--max-chatgpt-file-bytes', str(original_size + 10)])
        with self.assertRaisesRegex(ValueError, 'including context'):
            web.execute(args)


# Additional lifecycle/state invariants discovered while integrating v2.
class FollowupAndLifecycleTests(Fixture):
    def test_malformed_manifest_replaces_stale_active_success(self):
        _, manifest, path = self.prepare()
        args = self.arguments(path)
        self.approve(args, manifest)
        self.execute(args, FakeClient())
        path.write_text('{invalid JSON')
        with self.assertRaises(json.JSONDecodeError):
            self.execute(args, FakeClient())
        self.assertEqual(self.meta()['status'], 'failed')
        self.assertFalse((self.base / 'run/analysis_report.md').exists())

    def test_previous_response_requires_same_contract_and_selection(self):
        _, manifest, path = self.prepare()
        args = self.arguments(path, '--store')
        self.approve(args, manifest)
        self.execute(args, FakeClient())
        prior_path = self.base / 'prior.json'
        integrity.write_json(prior_path, self.meta())
        follow = self.arguments(path, '--previous-response-id', 'resp-test', '--previous-run-meta', str(prior_path))
        self.assertEqual(api.resolve_run(follow, manifest), ('direct', 'full'))
        modified = copy.deepcopy(manifest)
        modified['request_contract']['non_goals'] = ['new non-goal']
        with self.assertRaisesRegex(ValueError, 'same snapshot'):
            api.resolve_run(follow, modified)

    def test_token_count_receives_reasoning_context_configuration(self):
        _, manifest, path = self.prepare()
        args = self.arguments(path, '--reasoning-context', 'current_turn')
        self.approve(args, manifest)
        fake = FakeClient()
        self.execute(args, fake)
        self.assertEqual(fake.counted_requests[0]['reasoning'], fake.created_requests[0]['reasoning'])

    def test_response_poll_timeout_cancels_known_background_response(self):
        _, manifest, path = self.prepare()
        args = self.arguments(path, '--background')
        self.approve(args, manifest)
        fake = FakeClient(response_status='in_progress')
        with mock.patch.object(api, 'poll_response', side_effect=TimeoutError('bounded timeout')):
            with self.assertRaises(TimeoutError):
                self.execute(args, fake)
        self.assertEqual(fake.cancelled, ['resp-test'])
        self.assertEqual(self.meta()['cancellation_status'], 'cancelled')

    def test_disabled_test_category_is_honored(self):
        self.put('tests/test_answer.py', 'assert True')
        config = self.base / 'config.json'
        config.write_text(json.dumps({'include_tests': False}))
        _, manifest, _ = self.prepare('--config', str(config))
        self.assertNotIn('tests/test_answer.py', integrity.verify_manifest(manifest))

    def test_non_git_scan_requires_explicit_opt_in(self):
        shutil.rmtree(self.repo / '.git')
        with self.assertRaisesRegex(ValueError, 'allow-non-git'):
            self.prepare()
        code, manifest, _ = self.prepare('--allow-non-git')
        self.assertEqual(code, 0)
        self.assertEqual(manifest['enumeration'], 'manual-unverified-ignore')

    def test_owned_cleanup_never_deletes_unowned_store(self):
        fake = FakeClient()
        fake.stores['external'] = NS(id='external')
        result = resources.OwnedResources(fake).cleanup()
        self.assertEqual(result['status'], 'completed')
        self.assertFalse(fake.deleted)

    def test_normalized_headers_never_include_host_root(self):
        docs = resources.normalized_documents({'app.tsx': b'export const x=1'}, ['app.tsx'])
        header = json.loads(docs[0]['data'].decode().splitlines()[0])
        self.assertEqual(header['original_path'], 'app.tsx')
        self.assertNotIn('repo_root', header)


if __name__ == '__main__':
    unittest.main()
