from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import subprocess

import pytest

from ghost_in_the_sim.evidence_contract import project_evidence, validate_derived_evidence


ROOT = Path(__file__).resolve().parents[1]


def _design_module():
    spec = importlib.util.spec_from_file_location("check_design_contract", ROOT / "tests/check_design_contract.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(module)
    return module


def test_verify_workflow_exposes_src_package_to_every_python_gate() -> None:
    workflow = (ROOT / ".github/workflows/verify.yml").read_text(encoding="utf-8")
    job_header = "  deterministic-core:\n    runs-on: ubuntu-latest\n    env:\n      PYTHONPATH: src\n"
    assert job_header in workflow


def test_mvp_completion_sync_detects_drift_on_every_status_surface() -> None:
    module = _design_module()
    roadmap = (ROOT / "docs/roadmap.md").read_text(encoding="utf-8")
    artifacts = (ROOT / "docs/knowledge/artifacts.md").read_text(encoding="utf-8")
    questions = (ROOT / "docs/knowledge/open-questions.md").read_text(encoding="utf-8")
    payload = json.loads((ROOT / "web/data/comparison.json").read_text(encoding="utf-8"))
    module._validate_mvp_completion_sync(roadmap, artifacts, questions, payload)
    mutations = (
        (roadmap.replace("- [x] 複数seedの代表結果と提出資料を同期", "- [ ] 複数seedの代表結果と提出資料を同期"), artifacts, questions, payload),
        (roadmap, artifacts.replace("seed 17/42/99・符号反転・actual AI replayを実測", "複数seedは未実施"), questions, payload),
        (roadmap, artifacts, questions + "\n| 複数seed集合での順位安定性 | owner | next | done |\n", payload),
        (roadmap, artifacts, questions, {**payload, "seeds": [42]}),
    )
    for mutation in mutations:
        with pytest.raises(ValueError):
            module._validate_mvp_completion_sync(*mutation)
    missing_replay = json.loads(json.dumps(payload))
    missing_replay["result_card"].pop("ai_replay_evidence")
    empty_reversal = json.loads(json.dumps(payload))
    empty_reversal["result_card"]["seed_sensitivity"]["plural_vs_centralized_sign_reversals"] = []
    for candidate in (missing_replay, empty_reversal):
        with pytest.raises(ValueError):
            module._validate_mvp_completion_sync(roadmap, artifacts, questions, candidate)


def _validate_in_node(payload: dict) -> dict:
    contract = ROOT / "web/result-card-contract.js"
    script = "const c=require(process.argv[1]);let s='';process.stdin.on('data',d=>s+=d);process.stdin.on('end',()=>console.log(JSON.stringify(c.validate(JSON.parse(s)))));"
    completed = subprocess.run(
        ["node", "-e", script, str(contract)],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        check=True,
    )
    return json.loads(completed.stdout)


def test_result_card_contract_accepts_optional_replay_and_rejects_nested_drift() -> None:
    payload = json.loads((ROOT / "web/data/comparison.json").read_text(encoding="utf-8"))
    assert _validate_in_node(payload)["invalid"] is False
    without_replay = json.loads(json.dumps(payload))
    without_replay.pop("ai_evidence_runs")
    without_replay["result_card"].pop("ai_replay_evidence")
    without_replay["evidence_summary"] = project_evidence(without_replay)
    assert _validate_in_node(without_replay)["invalid"] is False
    malformed = []
    failure_null = json.loads(json.dumps(payload))
    failure_null["result_card"]["failure_runs"] = [None]
    malformed.append(failure_null)
    mismatch = json.loads(json.dumps(payload))
    mismatch["result_card"]["runs"][0]["failed_run"] = True
    malformed.append(mismatch)
    replay_half = json.loads(json.dumps(payload))
    replay_half.pop("ai_evidence_runs")
    malformed.append(replay_half)
    raw_run = json.loads(json.dumps(payload))
    raw_run["runs"][0] = None
    malformed.append(raw_run)
    fabricated_failure = json.loads(json.dumps(payload))
    fabricated_failure["result_card"]["runs"][0]["failed_run"] = True
    fabricated_failure["result_card"]["failure_runs"] = [fabricated_failure["result_card"]["runs"][0]]
    malformed.append(fabricated_failure)
    replay_summary = json.loads(json.dumps(payload))
    replay_summary["result_card"]["ai_replay_evidence"]["fallback_count"] = 1
    malformed.append(replay_summary)
    replay_source = json.loads(json.dumps(payload))
    replay_source["result_card"]["ai_replay_evidence"]["decision_sources"] = ["fabricated"]
    malformed.append(replay_source)
    refutation = json.loads(json.dumps(payload))
    refutation["result_card"]["refutation_checks"][0]["status"] = "triggered"
    refutation["result_card"]["refutation_checks"][0]["evidence"] = {"fabricated": True}
    malformed.append(refutation)
    duplicate_seed = json.loads(json.dumps(payload))
    duplicate_seed["seeds"].append(duplicate_seed["seeds"][0])
    malformed.append(duplicate_seed)
    for candidate in malformed:
        assert _validate_in_node(candidate) == {"card": None, "invalid": True}


def test_canonical_evidence_projection_rejects_refutation_mutation() -> None:
    payload = json.loads((ROOT / "web/data/comparison.json").read_text(encoding="utf-8"))
    candidate = json.loads(json.dumps(payload))
    candidate["result_card"]["refutation_checks"][0]["status"] = "triggered"
    candidate["result_card"]["refutation_checks"][0]["evidence"] = {"fabricated": True}
    with pytest.raises(ValueError, match="refutation checks"):
        validate_derived_evidence(candidate)

    duplicate_seed = json.loads(json.dumps(payload))
    duplicate_seed["seeds"].append(duplicate_seed["seeds"][0])
    with pytest.raises(ValueError, match="seeds must be unique"):
        validate_derived_evidence(duplicate_seed)

    boolean_seed = json.loads(json.dumps(payload))
    boolean_seed["seeds"][0] = True
    with pytest.raises(ValueError, match="seeds must be unique"):
        validate_derived_evidence(boolean_seed)
