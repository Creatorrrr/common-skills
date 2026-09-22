"""Deterministic helper tests. Not LLM behavior or scientific outcome tests."""
from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("portfolio_under_test", ROOT / "scripts/research_portfolio.py")
p = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(p)


def fixture():
    return json.loads((ROOT / "examples/portfolio/snapshot.json").read_text())


class PortfolioTests(unittest.TestCase):
    def setUp(self):
        self.s = fixture()
        self.c = self.s['candidates'][0]

    def test_pareto_mixed_directions(self):
        result=p.analyze(self.s, 'pilot')
        self.assertEqual(result['pareto_ids'], ['fast','quality'])
        self.assertIn('baseline', result['reference_ids'])

    def test_no_execution_or_adoption_claim(self):
        out=p.analyze(self.s,'pilot')
        self.assertFalse(out['execution_authorized'])
        self.assertEqual(out['adoption'],'not_decided')
        self.assertEqual(out['assessment_basis'],'supplied_records_only')
        self.assertIn('not independently verified',out['limitations'][0])

    def test_invalid_best_score_excluded(self):
        out=p.analyze(self.s,'pilot')
        self.assertNotIn('invalid',out['eligible_ids'])
        self.assertNotIn('invalid',out['declared_confirmed_ids'])

    def test_pending_not_valid(self):
        self.c['validity']='pending'
        self.assertIn('run_validity_pending',p.analyze(self.s,'pilot')['excluded']['baseline'])

    def test_mixed_evaluator_cohort(self):
        self.c['comparison']['evaluator']='eval-v0'
        self.assertIn('different_comparison_cohort',p.analyze(self.s,'pilot')['excluded']['baseline'])

    def test_all_cohort_dimensions_guarded(self):
        for key in p.COHORT_KEYS:
            s=fixture();s['candidates'][0]['comparison'][key]='other'
            with self.subTest(key=key):
                self.assertNotIn('baseline',p.analyze(s,'pilot')['eligible_ids'])

    def test_failed_smoke_cannot_skip_to_confirmation(self):
        self.c['stages']['smoke']='fail'
        out=p.analyze(self.s,'confirm')
        self.assertNotIn('baseline',out['declared_confirmed_ids'])
        self.assertIn('stage:smoke:fail',out['confirmation_blockers']['baseline'])

    def test_missing_stage_not_implicitly_passed(self):
        del self.c['stages']['pilot']
        self.assertIn('stage:pilot:not_run',p.analyze(self.s,'pilot')['excluded']['baseline'])

    def test_missing_objective_not_zero(self):
        del self.c['measurements']['pilot']['quality']
        self.assertIn('missing_objective:quality',p.analyze(self.s,'pilot')['excluded']['baseline'])

    def test_null_constraint_blocks(self):
        self.c['measurements']['pilot']['memory_mb']=None
        self.assertIn('missing_constraint:memory_mb',p.analyze(self.s,'pilot')['excluded']['baseline'])

    def test_constraint_violation_blocks(self):
        self.c['measurements']['pilot']['memory_mb']=201
        self.assertIn('violated_constraint:memory_mb',p.analyze(self.s,'pilot')['excluded']['baseline'])

    def test_lower_bound_constraint(self):
        self.s['constraints'][0]={'name':'memory_mb','operator':'>=','limit':101}
        self.assertNotIn('baseline',p.analyze(self.s,'pilot')['eligible_ids'])

    def test_confirmation_requires_all_fields_and_pass(self):
        for change in ({'status':'not_run'}, {'status':'fail'}, {'artifact_sha256':'f'*64},
                       {'evaluator':'old'}, {'evidence_refs':[]}):
            s=fixture();s['candidates'][0]['confirmation'].update(change)
            with self.subTest(change=change):
                self.assertNotIn('baseline',p.analyze(s,'pilot')['declared_confirmed_ids'])

    def test_terminal_stage_not_optional(self):
        self.c['stages']['confirm']='not_run'
        self.assertNotIn('baseline',p.analyze(self.s,'pilot')['declared_confirmed_ids'])

    def test_confirmed_ids_are_declarations_not_winner_selection(self):
        out=p.analyze(self.s,'pilot')
        self.assertEqual(out['declared_confirmed_ids'],['baseline','fast'])
        self.assertEqual(out['adoption'],'not_decided')

    def test_duplicate_code_not_new_independent_candidate(self):
        c=copy.deepcopy(self.c);c['id']='copy';c['family']='pretend-novel'
        self.s['candidates'].append(c)
        out=p.analyze(self.s,'pilot')
        self.assertEqual(len(out['duplicate_groups']),1)
        self.assertNotIn('copy',out['eligible_ids'])
        self.assertFalse(out['duplicate_groups'][0]['conflicting_records'])

    def test_conflicting_replicates_need_reconciliation(self):
        c=copy.deepcopy(self.c);c['id']='replicate';c['measurements']['pilot']['quality']=.95
        self.s['candidates'].append(c)
        out=p.analyze(self.s,'pilot')
        self.assertTrue(out['duplicate_groups'][0]['conflicting_records'])
        self.assertNotIn('baseline',out['declared_confirmed_ids'])
        self.assertNotIn('replicate',out['eligible_ids'])

    def test_conflicting_confirmation_verdicts_require_reconciliation(self):
        for status in ("fail", "inconclusive"):
            snapshot = fixture()
            replica = copy.deepcopy(snapshot["candidates"][0])
            replica["id"] = "replicate"
            replica["confirmation"]["status"] = status
            snapshot["candidates"].append(replica)
            with self.subTest(status=status):
                out = p.analyze(snapshot, "confirm")
                self.assertTrue(out["duplicate_groups"][0]["conflicting_records"])
                self.assertIsNone(out["duplicate_groups"][0]["canonical_reference"])
                for cid in ("baseline", "replicate"):
                    self.assertNotIn(cid, out["eligible_ids"])
                    self.assertNotIn(cid, out["declared_confirmed_ids"])
                    self.assertIn("duplicate_conflict_requires_reconciliation", out["confirmation_blockers"][cid])

    def test_conflicting_confirmation_bindings_require_reconciliation(self):
        for key, value in (("artifact_sha256", "f" * 64), ("evaluator", "other-evaluator")):
            snapshot = fixture()
            replica = copy.deepcopy(snapshot["candidates"][0])
            replica["id"] = "replicate"
            replica["confirmation"][key] = value
            snapshot["candidates"].append(replica)
            with self.subTest(key=key):
                out = p.analyze(snapshot, "confirm")
                self.assertTrue(out["duplicate_groups"][0]["conflicting_records"])
                self.assertNotIn("baseline", out["declared_confirmed_ids"])
                self.assertNotIn("replicate", out["declared_confirmed_ids"])

    def test_unrun_confirmation_copy_preserves_completed_reference(self):
        replica = copy.deepcopy(self.c)
        replica["id"] = "aaa-unrun-copy"
        replica["confirmation"] = {"status": "not_run"}
        self.s["candidates"].append(replica)
        out = p.analyze(self.s, "confirm")
        self.assertFalse(out["duplicate_groups"][0]["conflicting_records"])
        self.assertEqual(out["duplicate_groups"][0]["canonical_reference"], "baseline")
        self.assertIn("baseline", out["declared_confirmed_ids"])
        self.assertNotIn("aaa-unrun-copy", out["declared_confirmed_ids"])

    def test_consistent_confirmation_with_distinct_evidence_refs_is_not_conflict(self):
        replica = copy.deepcopy(self.c)
        replica["id"] = "replicate"
        replica["confirmation"]["evidence_refs"] = ["synthetic://another-confirmation-record"]
        self.s["candidates"].append(replica)
        out = p.analyze(self.s, "confirm")
        self.assertFalse(out["duplicate_groups"][0]["conflicting_records"])
        self.assertIn("baseline", out["declared_confirmed_ids"])
        self.assertNotIn("replicate", out["declared_confirmed_ids"])

    def test_unknown_usage_not_zero(self):
        row=p.analyze(self.s,'pilot')['resources']['api_tokens']
        self.assertEqual(row['state'],'unknown');self.assertIsNone(row['remaining'])

    def test_reserved_resources_counted(self):
        self.assertEqual(p.analyze(self.s,'pilot')['resources']['cpu_seconds']['remaining'],50)

    def test_exhausted_and_exceeded_no_new_permission(self):
        for used,status in ((80,'exhausted'),(81,'exceeded')):
            self.s['resources']['cpu_seconds']['used']=used
            out=p.analyze(self.s,'pilot')
            self.assertEqual(out['resources']['cpu_seconds']['state'],status)
            self.assertFalse(out['execution_authorized'])

    def test_readonly_analysis(self):
        before=copy.deepcopy(self.s);p.analyze(self.s,'pilot')
        self.assertEqual(before,self.s)

    def test_record_order_does_not_change_references(self):
        expected=p.analyze(self.s,'pilot')['reference_ids']
        self.s['candidates'].reverse()
        self.assertEqual(p.analyze(self.s,'pilot')['reference_ids'],expected)

    def test_family_coverage_before_second_frontier_same_family(self):
        c=copy.deepcopy(self.s['candidates'][2]);c['id']='aaa';c['fingerprint']='a'*64
        c['measurements']['pilot'].update(quality=.75,latency_ms=7)
        self.s['candidates'].append(c)
        out=p.analyze(self.s,'pilot',2)
        self.assertEqual(out['reference_ids'],['aaa','quality'])

    def test_reference_limit_not_experiment_budget(self):
        self.assertEqual(len(p.analyze(self.s,'pilot',1)['reference_ids']),1)
        for value in (0,51,True):
            with self.assertRaises(p.InputError):p.analyze(self.s,'pilot',value)

    def test_unknown_stage_rejected(self):
        with self.assertRaises(p.InputError):p.analyze(self.s,'imaginary')

    def test_stage_list_order_defines_confirmation(self):
        self.s['promotion_stage']='pilot'
        with self.assertRaises(p.InputError):p.analyze(self.s,'pilot')

    def test_boolean_nan_inf_numeric_values_rejected(self):
        for value in (True,float('nan'),float('inf'),float('-inf'),10**1000):
            self.c['measurements']['pilot']['quality']=value
            with self.subTest(value=str(value)[:20]), self.assertRaises(p.InputError):
                p.validate(self.s)

    def test_bool_schema_version_rejected(self):
        self.s['schema_version']=True
        with self.assertRaises(p.InputError):p.validate(self.s)

    def test_unknown_fields_rejected(self):
        self.s['autorun']=True
        with self.assertRaises(p.InputError):p.validate(self.s)

    def test_duplicate_identifiers_rejected(self):
        self.s['candidates'].append(copy.deepcopy(self.c))
        with self.assertRaises(p.InputError):p.validate(self.s)

    def test_lineage_cycle_rejected(self):
        self.c['parent_ids']=['fast'];self.s['candidates'][2]['parent_ids']=['baseline']
        with self.assertRaises(p.InputError):p.validate(self.s)

    def test_external_parent_reference_allowed(self):
        self.c['parent_ids']=['archived-not-in-snapshot']
        p.validate(self.s)

    def test_invalid_hash_rejected(self):
        self.c['fingerprint']='whatever'
        with self.assertRaises(p.InputError):p.validate(self.s)

    def test_empty_population_is_explicit_empty_not_success(self):
        self.s['candidates']=[]
        out=p.analyze(self.s,'pilot')
        self.assertEqual(out['eligible_ids'],[]);self.assertEqual(out['adoption'],'not_decided')

    def test_strict_json_duplicate_key_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'x.json';path.write_text('{"schema_version":1,"schema_version":1}')
            with self.assertRaises(p.InputError):p.load_snapshot(path)

    def test_json_nonfinite_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'x.json';path.write_text('{"value": NaN}')
            with self.assertRaises(p.InputError):p.load_snapshot(path)

    def test_oversized_input_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'x.json';path.write_bytes(b' '*(p.MAX_BYTES+1))
            with self.assertRaises(p.InputError):p.load_snapshot(path)

    def test_stage_measurements_are_not_interchangeable(self):
        self.c['measurements']['confirm']['quality']=1.0
        self.c['measurements']['confirm']['latency_ms']=0.1
        pilot=p.analyze(self.s,'pilot')
        confirmed=p.analyze(self.s,'confirm')
        self.assertNotIn('baseline',pilot['pareto_ids'])
        self.assertIn('baseline',confirmed['pareto_ids'])

    def test_confirmation_cannot_reuse_pilot_metrics(self):
        del self.c['measurements']['confirm']
        self.assertNotIn('baseline',p.analyze(self.s,'pilot')['declared_confirmed_ids'])

    def test_structural_stage_value_rejected_cleanly(self):
        self.c['stages']['smoke']={}
        with self.assertRaises(p.InputError):p.validate(self.s)

    def test_cli_is_read_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'s.json';path.write_text(json.dumps(self.s))
            before=hashlib.sha256(path.read_bytes()).hexdigest()
            proc=subprocess.run([sys.executable,'-B',str(ROOT/'scripts/research_portfolio.py'),
                                 '--input',str(path),'--stage','pilot'],capture_output=True,text=True,timeout=15,check=False)
            self.assertEqual(proc.returncode,0,proc.stderr)
            self.assertEqual(before,hashlib.sha256(path.read_bytes()).hexdigest())
            self.assertEqual(list(Path(tmp).iterdir()),[path])
            self.assertFalse(json.loads(proc.stdout)['execution_authorized'])

    def test_bad_cli_input_fails_without_stdout(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'s.json';path.write_text('{}')
            proc=subprocess.run([sys.executable,'-B',str(ROOT/'scripts/research_portfolio.py'),
                                 '--input',str(path),'--stage','pilot'],capture_output=True,text=True,timeout=15,check=False)
            self.assertEqual(proc.returncode,2);self.assertEqual(proc.stdout,'')

    def test_native_json_and_encoding_errors_return_cli_error(self):
        malformed = fixture()
        malformed["notes"] = "\ud800"
        for content in ('{"value":' + "1" * 5000 + "}", json.dumps(malformed)):
            with self.subTest(size=len(content)), tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp) / "input.json"
                path.write_text(content)
                proc = subprocess.run([sys.executable, "-B", str(ROOT / "scripts/research_portfolio.py"),
                                       "--input", str(path), "--stage", "pilot"], capture_output=True,
                                      text=True, timeout=15, check=False)
                self.assertEqual(proc.returncode, 2)
                self.assertEqual(proc.stdout, "")
                self.assertIn("error", json.loads(proc.stderr))
                self.assertFalse(json.loads(proc.stderr)["execution_authorized"])
                self.assertEqual(path.read_text(), content)

if __name__=='__main__':unittest.main()
