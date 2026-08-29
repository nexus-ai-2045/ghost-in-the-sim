"""依存なしデモUIの公開契約を静的に検査する。"""

from __future__ import annotations

import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class DemoUiContractTest(unittest.TestCase):
    def test_required_assets_and_accessibility_contract(self) -> None:
        index = (ROOT / "web/index.html").read_text(encoding="utf-8")
        script = (ROOT / "web/app.js").read_text(encoding="utf-8")
        style = (ROOT / "web/styles.css").read_text(encoding="utf-8")
        for phrase in ("3つの統治条件", "比較指標", "タイムライン", "合成仮説", "因果効果"):
            self.assertIn(phrase, index)
        self.assertIn('aria-live="polite"', index)
        self.assertIn('prefers-reduced-motion', style)
        self.assertIn('data/sample-comparison.json', script)
        for contract_key in (
            "result_card",
            "failure_runs",
            "refutation_checks",
            "limitations",
            "fallback_applied",
            "decision_source",
            "ai_evidence_runs",
            "ai_replay_evidence",
            "termination_reason",
        ):
            self.assertIn(contract_key, script)
        self.assertIn('id="seed-select"', index)
        self.assertIn('id="result-card"', index)
        for escaped in ("&amp;", "&lt;", "&gt;", "&quot;", "&#39;"):
            self.assertIn(escaped, script)
        self.assertNotIn('function escapeText(value) { return String(value ?? "—"); }', script)
        self.assertIn("escapeText(event.turn)", script)
        self.assertNotIn("TURN ${event.turn}", script)
        self.assertIn("formatEvidence(check.evidence)", script)
        self.assertIn("Array.isArray(aiReplay?.decision_sources)", script)
        self.assertIn("Number.isFinite(Number(aiReplay?.run_count))", script)
        self.assertIn("validateResultCard(payload)", script)
        self.assertIn("isNonNegativeInteger(card.run_count)", script)
        self.assertIn("card.run_count === payload.runs.length", script)
        self.assertIn("replay.run_count === evidenceRuns.length", script)
        self.assertIn("結果カード不正", script)

    def test_fixture_has_three_distinct_conditions_and_required_metrics(self) -> None:
        fixture = json.loads((ROOT / "web/data/sample-comparison.json").read_text(encoding="utf-8"))
        self.assertEqual(fixture["seed"], 2045)
        self.assertIn("因果効果", fixture["interpretation_boundary"])
        conditions = fixture["conditions"]
        self.assertEqual([item["manifest"]["condition_id"] for item in conditions], ["centralized", "plural", "autonomous"])
        required = {"continuity", "evidence_calibration", "public_trust", "coordination_dependence", "over_disclosure", "correction_turn", "dissent_reach"}
        for item in conditions:
            self.assertTrue(required.issubset(item["metrics"]))
            self.assertGreater(len(item["events"]), 0)

    def test_generated_comparison_contains_multi_seed_result_card(self) -> None:
        payload = json.loads((ROOT / "web/data/comparison.json").read_text(encoding="utf-8"))
        self.assertEqual(payload["seeds"], [17, 42, 99])
        self.assertEqual(len(payload["runs"]), 9)
        card = payload["result_card"]
        self.assertEqual(card["run_count"], 9)
        self.assertIn("failure_runs", card)
        self.assertIn("refutation_checks", card)
        self.assertTrue(card["limitations"])
        self.assertEqual(card["ai_replay_evidence"]["run_count"], 3)
        self.assertEqual(card["ai_replay_evidence"]["fallback_count"], 0)
        self.assertEqual(card["ai_replay_evidence"]["decision_sources"], ["llm_generated_in_codex_session"])
        self.assertEqual(len(payload["ai_evidence_runs"]), 3)
        self.assertEqual(payload["artifact_revision"], card["artifact_revision"])


if __name__ == "__main__":
    unittest.main()
