"""Official SDK wire-format checks using only synthetic data and MockTransport.

Run separately with tests/sdk/requirements.txt installed. No real API connection,
credential, account operation, model generation, or billing takes place.
"""
from __future__ import annotations

import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from email.parser import BytesParser
from email.policy import default
from pathlib import Path
from unittest import mock

import httpx
from openai import APIStatusError, OpenAI

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts'))
import context_integrity as integrity  # noqa: E402
import prepare_analysis_context as prep  # noqa: E402
import run_gpt_pro_analysis as api  # noqa: E402


class WireFixture:
    def __init__(self, fail_generation=False):
        self.calls = []
        self.json_bodies = {}
        self.uploaded = []
        self.fail_generation = fail_generation

    def handle(self, request):
        route = (request.method, request.url.path)
        self.calls.append(route)
        body = request.read()
        if body and request.headers.get('content-type', '').startswith('application/json'):
            self.json_bodies[route] = json.loads(body)
        path = request.url.path
        if request.method == 'DELETE':
            return httpx.Response(200, json={'id': path.rsplit('/', 1)[-1], 'deleted': True})
        if path == '/v1/responses/input_tokens':
            return httpx.Response(200, json={'object': 'response.input_tokens', 'input_tokens': 1000})
        if path == '/v1/responses':
            if self.fail_generation:
                return httpx.Response(500, json={'error': {'message': 'Synthetic failure', 'type': 'server_error'}})
            output = [{'id': 'msg-test', 'type': 'message', 'status': 'completed', 'role': 'assistant',
                       'content': [{'type': 'output_text', 'text': '검토 결과', 'annotations': []}]}]
            return httpx.Response(200, json={'id': 'resp-test', 'object': 'response', 'status': 'completed',
                                            'created_at': 0, 'model': 'gpt-5.6-sol', 'output': output})
        if path == '/v1/vector_stores':
            return httpx.Response(200, json={'id': 'vs-test', 'object': 'vector_store', 'status': 'completed'})
        if path == '/v1/files':
            header = ('Content-Type: ' + request.headers['content-type'] + '\r\n\r\n').encode()
            message = BytesParser(policy=default).parsebytes(header + body)
            parts = {part.get_param('name', header='content-disposition'): part for part in message.iter_parts()}
            self.uploaded.append(parts)
            return httpx.Response(200, json={'id': 'file-test', 'object': 'file', 'bytes': 100,
                                            'created_at': 0, 'filename': parts['file'].get_filename(),
                                            'purpose': 'assistants'})
        if path in {'/v1/vector_stores/vs-test/files', '/v1/vector_stores/vs-test/files/file-test'}:
            return httpx.Response(200, json={'id': 'file-test', 'object': 'vector_store.file',
                                            'status': 'completed', 'vector_store_id': 'vs-test'})
        raise AssertionError(f'Unexpected SDK request: {route}')


class SDKTransportTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name)
        repo = self.base / 'repo'
        repo.mkdir()
        subprocess.run(['git', 'init', '-q', str(repo)], check=True)
        (repo / '결제.py').write_text('def pay():\n    return "결제"\n', encoding='utf-8')
        context = self.base / 'context'
        with mock.patch.object(sys, 'argv', ['prepare', '--root', str(repo), '--out-dir', str(context),
                                            '--mode', 'full', '--goal', '결제 흐름 검토']), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(prep.main(), 0)
        self.manifest_path = context / 'manifest.json'
        self.manifest = integrity.read_manifest(self.manifest_path)

    def run_fixture(self, mode, wire, *extra):
        args = api.build_parser().parse_args(['--manifest', str(self.manifest_path), '--mode', mode,
                                             '--out-dir', str(self.base / 'run'), *extra])
        _, key = api.resolve_run(args, self.manifest)
        approval_path = self.base / 'synthetic-approval.json'
        integrity.write_json(approval_path, {'schema_version': 1, 'approved': True, 'selection_reviewed': True,
            'transport': 'responses_api', 'binding': integrity.binding(self.manifest, key),
            'execution_options': integrity.execution_options(args)})
        args.approval = str(approval_path)
        http_client = httpx.Client(transport=httpx.MockTransport(wire.handle))
        self.addCleanup(http_client.close)

        def client_factory(**kwargs):
            self.assertEqual(kwargs['max_retries'], 0)
            client = OpenAI(api_key='offline-synthetic-key', http_client=http_client, **kwargs)
            self.addCleanup(client.close)
            return client

        with mock.patch.dict(os.environ, {'OPENAI_API_KEY': 'offline-synthetic-key'}), contextlib.redirect_stdout(io.StringIO()):
            return api.execute(args, client_factory=client_factory)

    def test_direct_count_and_generation_preserve_sdk_payload_for_each_model(self):
        for model, expected in [('gpt-5.6-sol', {'effort': 'high', 'mode': 'pro', 'context': 'all_turns'}),
                                ('gpt-6-astra', {'effort': 'high'})]:
            with self.subTest(model=model):
                wire = WireFixture()
                extra = ['--reasoning-context', 'all_turns'] if model == 'gpt-5.6-sol' else []
                self.assertEqual(self.run_fixture('direct', wire, '--model', model, *extra), 0)
                self.assertEqual(wire.calls, [('POST', '/v1/responses/input_tokens'), ('POST', '/v1/responses')])
                counted = wire.json_bodies[wire.calls[0]]
                generated = wire.json_bodies[wire.calls[1]]
                for field in ('model', 'input', 'instructions', 'reasoning'):
                    self.assertEqual(counted[field], generated[field])
                self.assertEqual(generated['reasoning'], expected)
                self.assertFalse(generated['store'])
                self.assertFalse(generated['background'])
                self.assertIn('결제', generated['input'][0]['content'][0]['text'])
                self.assertEqual((self.base / 'run/analysis_report.md').read_text(), '검토 결과')

    def test_retrieval_serializes_multipart_expiry_ingestion_and_cleanup(self):
        wire = WireFixture()
        self.assertEqual(self.run_fixture('file_search_full', wire), 0)
        self.assertEqual(len(wire.uploaded), 1)
        upload = wire.uploaded[0]
        self.assertEqual(upload['expires_after[anchor]'].get_payload(decode=True), b'created_at')
        self.assertEqual(upload['expires_after[seconds]'].get_payload(decode=True), b'86400')
        self.assertEqual(upload['purpose'].get_payload(decode=True), b'assistants')
        self.assertTrue(upload['file'].get_filename().endswith('.txt'))
        source = upload['file'].get_payload(decode=True).decode('utf-8')
        self.assertEqual(json.loads(source.splitlines()[0])['original_path'], '결제.py')
        self.assertIn('000001: def pay():', source)
        attached = wire.json_bodies[('POST', '/v1/vector_stores/vs-test/files')]
        self.assertEqual(attached['file_id'], 'file-test')
        self.assertEqual(attached['chunking_strategy']['static']['max_chunk_size_tokens'], 800)
        generated = wire.json_bodies[('POST', '/v1/responses')]
        self.assertEqual(generated['tools'][0]['vector_store_ids'], ['vs-test'])
        self.assertEqual(wire.calls[-2:], [('DELETE', '/v1/vector_stores/vs-test'), ('DELETE', '/v1/files/file-test')])
        meta = json.loads((self.base / 'run/run_meta.json').read_text())
        self.assertEqual(meta['status'], 'response_completed')
        self.assertEqual(meta['analysis_validation'], 'pending')

    def test_sdk_http_error_cleans_owned_resources_without_retry(self):
        wire = WireFixture(fail_generation=True)
        with self.assertRaises(APIStatusError):
            self.run_fixture('file_search_full', wire)
        self.assertEqual(wire.calls.count(('POST', '/v1/responses')), 1)
        self.assertEqual(wire.calls[-2:], [('DELETE', '/v1/vector_stores/vs-test'), ('DELETE', '/v1/files/file-test')])
        self.assertFalse((self.base / 'run/analysis_report.md').exists())
        meta = json.loads((self.base / 'run/run_meta.json').read_text())
        self.assertEqual(meta['status'], 'failed')
        self.assertEqual(meta['cleanup_status'], 'completed')


if __name__ == '__main__':
    unittest.main()
