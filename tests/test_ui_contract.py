"""依存なしデモUIの公開契約を静的に検査する。"""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import unittest


ROOT = Path(__file__).resolve().parents[1]


class DemoUiContractTest(unittest.TestCase):
    def test_required_assets_and_accessibility_contract(self) -> None:
        index = (ROOT / "web/index.html").read_text(encoding="utf-8")
        script = (ROOT / "web/app.js").read_text(encoding="utf-8")
        contract = (ROOT / "web/result-card-contract.js").read_text(encoding="utf-8")
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
        self.assertIn("ResultCardContract.validate(payload)", script)
        self.assertIn("nonNegativeInteger(card.run_count)", contract)
        self.assertIn("card.run_count === runs.length", contract)
        self.assertIn("replay.run_count === evidenceRuns.length", contract)
        self.assertIn("結果カード不正", script)
        self.assertIn('src="result-card-contract.js"', index)

    def test_verified_experience_is_fail_closed_and_accessible(self) -> None:
        index = (ROOT / "web/index.html").read_text(encoding="utf-8")
        script = (ROOT / "web/app.js").read_text(encoding="utf-8")
        contract = (ROOT / "web/experience-contract.js").read_text(encoding="utf-8")
        style = (ROOT / "web/styles.css").read_text(encoding="utf-8")

        self.assertIn('id="operation-console"', index)
        self.assertIn('id="experience-unavailable"', index)
        self.assertIn('src="experience-contract.js"', index)
        self.assertLess(index.index('src="experience-contract.js"'), index.index('src="app.js"'))
        self.assertIn('src="narrative-contract.js"', index)
        self.assertLess(index.index('src="narrative-contract.js"'), index.index('src="app.js"'))
        self.assertIn("NarrativeContract.project(event", script)
        self.assertIn("決定論的に投影", script)
        self.assertIn("ExperienceContract.validate(payload)", script)
        self.assertIn("experience.available", script)
        self.assertIn("request_pause", script)
        self.assertIn("attention", script)
        self.assertIn("cost_codes", script)
        self.assertIn("ArrowRight", script)
        self.assertIn("ArrowLeft", script)
        self.assertIn("Home", script)
        self.assertIn("End", script)
        self.assertIn("Escape", script)
        self.assertIn("min-height: 44px", style)
        self.assertIn("meta-security-run-bundle/v1", contract)
        self.assertIn("replay-match", contract)
        self.assertIn("renderer_mode", contract)
        self.assertNotIn("Math.random", script)
        for phrase in ("作戦開始", "前のターン", "次のターン", "最初から再開", "病院を守る", "港湾を守る"):
            self.assertIn(phrase, index)
        for phrase in ("状況", "御影の行動", "真壁の応答", "成功見込み", "代償"):
            self.assertIn(phrase, script)
        self.assertIn("playableIdForSelection", script)
        self.assertIn("experience.byId", script)
        self.assertIn("operative_state_before.cognitive_integrity", script)
        self.assertNotIn("attention_remaining", script)
        self.assertIn("producerがreplay-matchと記録", index)
        self.assertIn("generated artifact contract error", script)
        self.assertNotIn('render(await response.json(), "generated comparison.json")', script)
        self.assertIn("renderEmergenceObservation(trajectory", script)
        self.assertNotIn("appliedThisTurn", script)
        self.assertIn("meta-security-json-c14n/v1", contract)
        self.assertIn("run_request_sha256", contract)
        self.assertIn("event_stream_sha256", contract)
        self.assertIn("replay_sha256", contract)
        self.assertIn("AI創発観測", script)
        self.assertIn("proposal_conflict_count", script)
        self.assertIn("unresolved_interaction_count", script)
        self.assertIn("現在ターンの検証済み記録を個別表示", script)
        self.assertEqual(script.count("ExperienceContract.validate(payload)"), 1)
        self.assertIn(".emergence-observation", style)

    def test_operation_reads_as_japanese_game_not_dashboard(self) -> None:
        index = (ROOT / "web/index.html").read_text(encoding="utf-8")
        script = (ROOT / "web/app.js").read_text(encoding="utf-8")

        # プレイヤーには研究条件の直積ではなく、存在する4経路だけを段階的に提示する。
        for phrase in ("病院を守る", "港湾を守る", "真壁と共同確認する", "御影が単一正本で進める"):
            self.assertIn(phrase, index)
        self.assertIn("hospital-joint-hold", script)
        self.assertIn("port-joint-hold", script)
        self.assertIn("hospital-joint-proceed", script)
        self.assertIn("hospital-single-proceed", script)
        # 内部scenario IDをそのまま表示しない。
        self.assertIn("SCENARIO_COPY", script)
        self.assertNotIn('textContent = model.scenario_id', script)
        # 完了と再挑戦の一巡。
        self.assertIn("作戦完了", script)
        self.assertIn("別の方針で再挑戦", index)
        self.assertIn("resetToSelection", script)
        for phrase in ("守った", "失った", "訂正可能", "責任未確定"):
            self.assertIn(phrase, script)
        # 真壁の停止要求はターン進行トラックと詳細の両方で強調される。
        self.assertIn("pause-banner", script)
        self.assertIn("legend-pause", index)
        # 注意配分は数値表だけでなく日本語の説明文を持つ。
        self.assertIn("renderAttentionBrief", script)
        self.assertIn("注意配分の内訳", index)
        # seedと証拠の状態は折り畳んだ監査ビュー側に置く。
        self.assertLess(index.index('id="audit-view"'), index.index('id="seed-select"'))
        self.assertLess(index.index('id="audit-view"'), index.index('id="source-status"'))
        # 最初の画面は事件・御影・真壁・最初の操作へ絞る。
        self.assertIn("現場収束官", index)
        self.assertIn("persona-list", index)

    def test_experience_contract_rejects_unverified_or_incomplete_artifacts(self) -> None:
        script = ROOT / "tests/check_experience_contract.mjs"
        completed = subprocess.run(
            ["node", str(script)],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        self.assertIn("experience-contract: PASS", completed.stdout)

    def test_narrative_contract_is_deterministic_and_fail_closed(self) -> None:
        script = ROOT / "tests/check_narrative_contract.mjs"
        completed = subprocess.run(
            ["node", str(script)], cwd=ROOT, check=True, capture_output=True, text=True
        )
        self.assertIn("narrative-contract: PASS", completed.stdout)

    def test_start_operation_explains_missing_choices_instead_of_being_disabled(self) -> None:
        script = (ROOT / "web/app.js").read_text(encoding="utf-8")
        self.assertNotIn("start.disabled = !trajectory", script)
        self.assertIn("まず「病院を守る」か「港湾を守る」を選んでください。", script)
        self.assertIn("病院の確認方法を選んでください。", script)
        self.assertIn('activeTurn = 7;\n      pauseDecisionPending = true;', script)

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
        self.assertEqual(
            [item["trajectory_id"] for item in payload["playable_trajectories"]],
            ["hospital-joint-hold", "port-joint-hold", "hospital-joint-proceed", "hospital-single-proceed"],
        )


if __name__ == "__main__":
    unittest.main()
