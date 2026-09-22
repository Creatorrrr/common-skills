"""Coverage assertions for optional plan rules; no live agent evaluation."""
import json
import unittest
from pathlib import Path

from test_skill_contracts import contract_blocks

ROOT=Path(__file__).resolve().parents[1]

class EvolutionContractTests(unittest.TestCase):
    def test_seven_blocks_only(self):
        self.assertEqual(len(contract_blocks()),7)

    def test_core_does_not_require_portfolio(self):
        text=contract_blocks()['CORE_CONTRACT']
        self.assertNotIn('research_portfolio.py',text)
        self.assertNotIn('MAP-Elites',text)

    def test_expensive_evaluation_rules_are_portable(self):
        text=contract_blocks()['EXPERIMENT_CONTRACT_IF_NEEDED']
        for phrase in ('명백히 잘못된 대조','보호 데이터','단계별 측정','pilot 수치를 confirm으로','관측과 해석을 분리'):
            self.assertIn(phrase,text)

    def test_diversity_does_not_mandate_one_algorithm(self):
        text=contract_blocks()['DIRECTION_CONTRACT_IF_NEEDED']
        self.assertIn('특정 진화 알고리즘이나 추가 에이전트를 의무화하지',text)
        self.assertIn('Pareto',text)

    def test_plateau_is_not_silent_budget_reset(self):
        text=contract_blocks()['PROGRAM_CONTRACT_IF_ENABLED']
        self.assertIn('자동 추가 비용',text)
        self.assertIn('정체 판단 지점을 사전에',text)

    def test_new_behavior_scenarios_are_not_run(self):
        data=json.loads((ROOT/'tests/behavioral-evolution.json').read_text())
        self.assertEqual(data['evaluation_status'],'not_run')
        self.assertEqual(len(data['cases']),16)
        self.assertEqual(len({c['id'] for c in data['cases']}),16)
        for c in data['cases']:
            self.assertEqual(c['status'],'not_run')
            for key in ('setup','user_prompt','must','must_not'):self.assertTrue(c[key])

    def test_guide_review_does_not_claim_live_eval(self):
        text=(ROOT/'MODEL_GUIDE_REVIEW.md').read_text()
        self.assertIn('2026-09-22',text)
        self.assertIn('not_measured',text)
        self.assertIn('not_run',text)

    def test_new_scripts_have_no_dynamic_eval_or_network_dependencies(self):
        import ast
        for filename in ('research_portfolio.py','build_handoff.py'):
            tree=ast.parse((ROOT/'scripts'/filename).read_text())
            for node in ast.walk(tree):
                if isinstance(node,ast.Call) and isinstance(node.func,ast.Name):
                    self.assertNotIn(node.func.id,('eval','exec','compile','__import__'))
                if isinstance(node,(ast.Import,ast.ImportFrom)):
                    modules=[a.name for a in node.names] if isinstance(node,ast.Import) else [node.module or '']
                    for module in modules:
                        self.assertNotIn(module.split('.')[0],('requests','openai','httpx','subprocess','socket'))

if __name__=='__main__':unittest.main()
