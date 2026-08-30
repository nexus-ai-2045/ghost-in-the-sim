# RESULTS

> この台帳は `web/data/comparison.json` の機械可読result cardから生成する。計画値や未実行の推測は含めない。

## 実験識別

| 項目 | 値 |
|---|---|
| シナリオ | `kagamishio-proteus-01` |
| seed集合 | `{17, 42, 99}` |
| run数 | `9` |
| コード版 | `deterministic-core-v2` |
| engine source revision | `e3eb6f3f19c40ed1` |
| artifact revision | `04c9fcac8df536b3` |
| result card | `result-card-v1` |
| 境界 | 合成仮説。現実予測・因果証明・政策推奨ではない |

## 複数seed感度

### seed 17

| 指標 | centralized | plural | autonomous |
|---|---:|---:|---:|
| `continuity` | 1.0 | 1.0 | 1.0 |
| `evidence_calibration` | 0.483437 | 0.685271 | 0.0 |
| `correction_turn` | 3.0 | 2.0 | 13.0 |
| `dissent_reach` | 0.083333 | 1.0 | 0.333333 |
| `coordination_dependence` | 0.146391 | 0.248278 | 0.275846 |
| `over_disclosure` | 8.0 | 0.0 | 0.0 |
| `public_trust` | 0.373871 | 0.805871 | 0.541871 |

### seed 42

| 指標 | centralized | plural | autonomous |
|---|---:|---:|---:|
| `continuity` | 1.0 | 1.0 | 1.0 |
| `evidence_calibration` | 0.468548 | 0.68555 | 0.0 |
| `correction_turn` | 3.0 | 2.0 | 13.0 |
| `dissent_reach` | 0.083333 | 1.0 | 0.333333 |
| `coordination_dependence` | 0.255878 | 0.250613 | 0.290316 |
| `over_disclosure` | 8.0 | 0.0 | 0.0 |
| `public_trust` | 0.394947 | 0.826947 | 0.562947 |

### seed 99

| 指標 | centralized | plural | autonomous |
|---|---:|---:|---:|
| `continuity` | 1.0 | 1.0 | 1.0 |
| `evidence_calibration` | 0.455342 | 0.681756 | 0.0 |
| `correction_turn` | 3.0 | 2.0 | 13.0 |
| `dissent_reach` | 0.083333 | 1.0 | 0.333333 |
| `coordination_dependence` | 0.22203 | 0.279441 | 0.301849 |
| `over_disclosure` | 8.0 | 0.0 | 0.0 |
| `public_trust` | 0.39875 | 0.83075 | 0.56675 |

plural対centralizedでseedにより符号反転した指標: `coordination_dependence`。
これは優劣の断定ではなく、seed感度の観測である。

## 失敗run・反証判定

失敗run: `0` 件。

| 反証チェック | 状態 |
|---|---|
| `plural_always_better_without_tradeoff` | `not_triggered` |
| `centralized_always_better_without_tradeoff` | `not_triggered` |

## actual AI replay証拠

| 項目 | 値 |
|---|---|
| replay run数 | `3` |
| decision source | `llm_generated_in_codex_session` |
| fallback | `0` |

## 限界

- `synthetic_scenario_not_real_world_prediction`
- `parameter_sweep_not_run`
- `model_and_prompt_sensitivity_not_observable_without_live_llm`
- `no_single_winner_score`

## 再現

```powershell
$env:PYTHONPATH = "src"
py -3.13 -m ghost_in_the_sim.batch_cli --output web/data/comparison.json --actual-ai-evidence-trace fixtures/actual-ai-trace-seed42.json
py -3.13 scripts/render_results.py --check
```

actual AI由来の型付き判断は `fixtures/actual-ai-trace-seed42.json` を独立fixtureとしてreplayし、上の機械可読証拠へ反映する。
比較本体はseed間の条件を揃えるためrule providerを使い、両者を混ぜない。
