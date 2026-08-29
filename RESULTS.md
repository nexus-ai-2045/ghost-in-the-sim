# RESULTS

> この台帳は `web/data/comparison.json` の機械可読result cardから生成する。計画値や未実行の推測は含めない。

## 実験識別

| 項目 | 値 |
|---|---|
| シナリオ | `poseidon-replica-crisis-01` |
| seed集合 | `{17, 42, 99}` |
| run数 | `9` |
| コード版 | `deterministic-core-v2` |
| engine source revision | `1c81c9e92c0c0e80` |
| artifact revision | `49d253e132086b1e` |
| result card | `result-card-v1` |
| 境界 | 合成仮説。現実予測・因果証明・政策推奨ではない |

## 複数seed感度

### seed 17

| 指標 | centralized | plural | autonomous |
|---|---:|---:|---:|
| `continuity` | 1.0 | 1.0 | 1.0 |
| `evidence_calibration` | 0.497387 | 0.663078 | 0.0 |
| `correction_turn` | 3.0 | 2.0 | 13.0 |
| `dissent_reach` | 0.083333 | 1.0 | 0.333333 |
| `coordination_dependence` | 0.104989 | 0.243156 | 0.282677 |
| `over_disclosure` | 8.0 | 0.0 | 0.0 |
| `public_trust` | 0.372202 | 0.804202 | 0.540202 |

### seed 42

| 指標 | centralized | plural | autonomous |
|---|---:|---:|---:|
| `continuity` | 1.0 | 1.0 | 1.0 |
| `evidence_calibration` | 0.473154 | 0.653879 | 0.0 |
| `correction_turn` | 3.0 | 2.0 | 13.0 |
| `dissent_reach` | 0.083333 | 1.0 | 0.333333 |
| `coordination_dependence` | 0.29531 | 0.267399 | 0.292221 |
| `over_disclosure` | 8.0 | 0.0 | 0.0 |
| `public_trust` | 0.355494 | 0.787494 | 0.523494 |

### seed 99

| 指標 | centralized | plural | autonomous |
|---|---:|---:|---:|
| `continuity` | 1.0 | 1.0 | 1.0 |
| `evidence_calibration` | 0.465246 | 0.656422 | 0.0 |
| `correction_turn` | 3.0 | 2.0 | 13.0 |
| `dissent_reach` | 0.083333 | 1.0 | 0.333333 |
| `coordination_dependence` | 0.228112 | 0.233021 | 0.257492 |
| `over_disclosure` | 8.0 | 0.0 | 0.0 |
| `public_trust` | 0.354345 | 0.786345 | 0.522345 |

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
