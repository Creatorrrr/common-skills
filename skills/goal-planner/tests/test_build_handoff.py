"""Compiler integrity/size tests, not live model instruction-following tests."""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
SPEC=importlib.util.spec_from_file_location('handoff_under_test',ROOT/'scripts/build_handoff.py')
h=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(h)

class HandoffTests(unittest.TestCase):
    def setUp(self):
        self.raw=h.CONTRACT.read_text();self.blocks=h.parse_blocks(self.raw)

    def test_default_light_contract(self):
        text,stats=h.compile_handoff('Draft only.',self.blocks,['Core'])
        self.assertEqual(stats['selected_blocks'],['Core'])
        self.assertNotIn(self.blocks['Persistence'],text)
        self.assertNotIn(self.blocks['Experiment'],text)

    def test_all_blocks_once(self):
        text,stats=h.compile_handoff('Authorized goal and constraints.',self.blocks,list(h.ORDER))
        for body in self.blocks.values():self.assertEqual(text.count(body),1)
        self.assertEqual(stats['block_count'],7)

    def test_canonical_order(self):
        _,stats=h.compile_handoff('Draft only.',self.blocks,['Experiment','Core'])
        self.assertEqual(stats['selected_blocks'],['Core','Experiment'])

    def test_core_required(self):
        with self.assertRaises(h.HandoffError):h.compile_handoff('Draft',self.blocks,['Experiment'])

    def test_duplicates_rejected(self):
        with self.assertRaises(h.HandoffError):h.compile_handoff('Draft',self.blocks,['Core','Core'])

    def test_unknown_block_rejected(self):
        with self.assertRaises(h.HandoffError):h.compile_handoff('Draft',self.blocks,['Core','AutoRun'])

    def test_marker_not_silently_removed(self):
        with self.assertRaises(h.HandoffError):h.compile_handoff('{{UNRESOLVED}}',self.blocks,['Core'])

    def test_blank_goal_rejected(self):
        with self.assertRaises(h.HandoffError):h.compile_handoff('  ',self.blocks,['Core'])

    def test_duplicate_existing_goal_contract_rejected(self):
        with self.assertRaises(h.HandoffError):h.compile_handoff(self.blocks['Core'],self.blocks,['Core'])

    def test_cap_refuses_truncation(self):
        with self.assertRaisesRegex(h.HandoffError,'no content emitted or truncated'):
            h.compile_handoff('Draft',self.blocks,['Core'],50)

    def test_exact_byte_cap_and_unicode_size(self):
        text,stats=h.compile_handoff('계획만 작성',self.blocks,['Core'])
        self.assertEqual(stats['utf8_bytes'],len(text.encode()))
        self.assertGreater(stats['utf8_bytes'],stats['characters'])
        again,_=h.compile_handoff('계획만 작성',self.blocks,['Core'],stats['utf8_bytes'])
        self.assertEqual(text,again);self.assertEqual(stats['token_count'],'not_measured')

    def test_invalid_cap(self):
        with self.assertRaises(h.HandoffError):h.compile_handoff('Draft',self.blocks,['Core'],0)

    def test_broken_contract_not_accepted(self):
        with self.assertRaises(h.HandoffError):h.parse_blocks(self.raw.replace('## Core\n','## Another\n'))

    def test_duplicate_contract_not_accepted(self):
        with self.assertRaises(h.HandoffError):h.parse_blocks(self.raw+'\n## Core\n\n```text\nduplicate\n```')

    def test_compile_never_infers_permission(self):
        _,stats=h.compile_handoff('Execute in my approved workspace.',self.blocks,['Core','Persistence'])
        self.assertFalse(stats['execution_authorized'])

    def test_cli_outputs_selected_once_and_exact_stats(self):
        proc=subprocess.run([sys.executable,'-B',str(ROOT/'scripts/build_handoff.py'),
                             '--goal-file',str(ROOT/'examples/portfolio/goal.md'),'--stats'],
                             capture_output=True,text=True,timeout=15,check=False)
        self.assertEqual(proc.returncode,0,proc.stderr)
        stats=json.loads(proc.stderr)
        self.assertEqual(stats['utf8_bytes'],len(proc.stdout.encode()))
        self.assertEqual(proc.stdout.count(self.blocks['Core']),1)

    def test_cli_too_small_no_partial_output(self):
        proc=subprocess.run([sys.executable,'-B',str(ROOT/'scripts/build_handoff.py'),
                             '--goal-file',str(ROOT/'examples/portfolio/goal.md'),'--max-bytes','1'],
                             capture_output=True,text=True,timeout=15,check=False)
        self.assertEqual(proc.returncode,2);self.assertEqual(proc.stdout,'')

if __name__=='__main__':unittest.main()
