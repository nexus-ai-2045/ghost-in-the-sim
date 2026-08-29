"""comparison.json から追跡可能な RESULTS.md を決定論的に生成する。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
METRICS = ("continuity", "evidence_calibration", "correction_turn", "dissent_reach", "coordination_dependence", "over_disclosure", "public_trust")
MODES = ("centralized", "plural", "autonomous")


def render(payload: dict) -> str:
    card = payload["result_card"]
    runs = payload["runs"]
    first = runs[0]
    lines = [
        "# RESULTS",
        "",
        "> この台帳は `web/data/comparison.json` の機械可読result cardから生成する。計画値や未実行の推測は含めない。",
        "",
        "## 実験識別",
        "",
        "| 項目 | 値 |",
        "|---|---|",
        f"| シナリオ | `{first['manifest']['scenario_id']}` |",
        f"| seed集合 | `{{{', '.join(map(str, payload['seeds']))}}}` |",
        f"| run数 | `{card['run_count']}` |",
        f"| コード版 | `{first['manifest']['code_version']}` |",
        f"| source revision | `{first['manifest']['source_revision']}` |",
        f"| result card | `{card['schema_version']}` |",
        "| 境界 | 合成仮説。現実予測・因果証明・政策推奨ではない |",
        "",
        "## 複数seed感度",
        "",
    ]
    for seed in payload["seeds"]:
        selected = {run["requested_mode"]: run for run in runs if run["seed"] == seed}
        lines += [f"### seed {seed}", "", "| 指標 | centralized | plural | autonomous |", "|---|---:|---:|---:|"]
        for metric in METRICS:
            values = [selected[mode]["metrics"][metric] for mode in MODES]
            lines.append(f"| `{metric}` | " + " | ".join(str(value) for value in values) + " |")
        lines.append("")
    reversals = card["seed_sensitivity"]["plural_vs_centralized_sign_reversals"]
    lines += [
        f"plural対centralizedでseedにより符号反転した指標: `{', '.join(reversals) if reversals else 'なし'}`。",
        "これは優劣の断定ではなく、seed感度の観測である。",
        "",
        "## 失敗run・反証判定",
        "",
        f"失敗run: `{len(card['failure_runs'])}` 件。",
        "",
        "| 反証チェック | 状態 |",
        "|---|---|",
    ]
    for check in card["refutation_checks"]:
        lines.append(f"| `{check['check_id']}` | `{check['status']}` |")
    ai_replay = card.get("ai_replay_evidence")
    lines += ["", "## actual AI replay証拠", ""]
    if ai_replay:
        lines += [
            "| 項目 | 値 |",
            "|---|---|",
            f"| replay run数 | `{ai_replay['run_count']}` |",
            f"| decision source | `{', '.join(ai_replay['decision_sources'])}` |",
            f"| fallback | `{ai_replay['fallback_count']}` |",
        ]
    else:
        lines.append("未記録。")
    lines += ["", "## 限界", ""] + [f"- `{item}`" for item in card["limitations"]]
    lines += [
        "",
        "## 再現",
        "",
        "```powershell",
        "$env:PYTHONPATH = \"src\"",
        "py -3.13 -m ghost_in_the_sim.batch_cli --output web/data/comparison.json --actual-ai-evidence-trace fixtures/actual-ai-trace-seed42.json",
        "py -3.13 scripts/render_results.py --check",
        "```",
        "",
        "actual AI由来の型付き判断は `fixtures/actual-ai-trace-seed42.json` を独立fixtureとしてreplayし、上の機械可読証拠へ反映する。",
        "比較本体はseed間の条件を揃えるためrule providerを使い、両者を混ぜない。",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=ROOT / "web/data/comparison.json")
    parser.add_argument("--output", type=Path, default=ROOT / "RESULTS.md")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    expected = render(json.loads(args.input.read_text(encoding="utf-8")))
    if args.check:
        if not args.output.is_file() or args.output.read_text(encoding="utf-8") != expected:
            raise SystemExit("RESULTS.md is stale; run scripts/render_results.py")
        print("results-artifact: PASS")
        return 0
    args.output.write_text(expected, encoding="utf-8")
    print(f"wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
