# RESULTS

> この台帳は、実際に実行したrunだけを記録する。計画値・期待値・未実行の推測を結果として書かない。

## 実験識別

| 項目 | 値 |
|---|---|
| 記録日 | `2026-08-29` |
| 実行実装commit | （このPRの指標実装コミット。下記 `source_revision` / `model_config_hash` で再照合） |
| コード版 | `deterministic-core-v2` |
| モデル版 | `0.2.0` |
| `model_config_hash` | `73600b9ad2e89d17` |
| `source_revision` | `cbdd4ed3a193d8ff` |
| シナリオ | `poseidon-public-infrastructure-01` |
| seed集合 | `{42}`（代表1 seed。複数seedの正式実験は未実行） |
| 比較条件 | A=`centralized` / B=`plural` / C=`overconnected` |
| ターン上限 | `12` |
| モデル設定 | 標準ライブラリによるルールベース。LLMなし |
| 指標定義 | `docs/architecture/evaluation.md` の MVP運用定義 |
| Python | `3.12.3` |
| 実行環境 | Linux / `PYTHONPATH=src` |

## 測定物と評価契約

本記録の数値は `engine._metrics()` が **evaluation.md のMVP運用定義どおり** に集計した契約指標である。最終 `WorldState` スカラーの代用ではない。

| 記録キー | 契約上の意味 | 本runでの算出 |
|---|---|---|
| `continuity` | 生活継続（維持ターン比率） | 各ターン後 `continuity >= 0.5` の比率（早期終了後は非維持） |
| `evidence_calibration` | 証拠校正（確信度と後続検証の整合） | 後続 `issue_correction` / `request_cross_check` に対する `1 - \|confidence - 実現値\|` の平均 |
| `correction_turn` | 訂正時間 | 訂正前の情報共有から `issue_correction` までのターン差（共有が無ければ訂正ターン番号） |
| `dissent_reach` | 異議到達率 | `dissent_delivered / dissent_raised` |
| `coordination_dependence` | 調整依存（単一ノード停止損失） | 協調量の leave-one-out 最大相対損失 |
| `over_disclosure` | 過剰開示 | 必要性超過の共有**回数** |
| `public_trust` | 契約表外の補助 | 最終 `WorldState.public_trust` |

## 実行コマンド

ローカル出力は `artifacts/`（追跡しない）。再実行で同じ出力になることを確認済み。

```bash
export PYTHONPATH=src
python3 -m ghost_in_the_sim.cli --condition centralized --seed 42 --output-dir artifacts/run-42-centralized
python3 -m ghost_in_the_sim.cli --condition plural --seed 42 --output-dir artifacts/run-42-plural
python3 -m ghost_in_the_sim.cli --condition overconnected --seed 42 --output-dir artifacts/run-42-overconnected
python3 -m ghost_in_the_sim.compare_cli --baseline centralized --candidate plural --seed 42 --output artifacts/compare-42-centralized-plural.json
```

## run識別子

| 条件 | run_id | 終了理由 | 完了ターン |
|---|---|---|---:|
| A centralized | `run-779260b38191` | `turn_limit_reached` | 12 |
| B plural | `run-c51a074b4c52` | `turn_limit_reached` | 12 |
| C overconnected | `run-d2844dd50ea2` | `turn_limit_reached` | 12 |

## 結果（契約指標・seed 42 実測）

総合点は作らない。設計契約検査用に `| 過剰開示 |` 行を残す。

| 指標 | 条件A centralized | 条件B plural | 条件C overconnected | 読み（仮定下・断定しない） |
|---|---:|---:|---:|---|
| 生活継続 (`continuity`) | 1.0 | 1.0 | 1.0 | 閾値0.5のもと、3条件とも全ターン維持 |
| 証拠校正 (`evidence_calibration`) | 0.444964 | 0.636714 | 0.482653 | Bが最も高い |
| 訂正時間 (`correction_turn`) | 3.0 | 2.0 | 5.0 | 低いほど速い。Bが最短 |
| 異議到達率 (`dissent_reach`) | 0.083333 | 1.0 | 0.083333 | Bのみ全件配信 |
| 調整依存 (`coordination_dependence`) | 0.246895 | 0.259159 | 0.30005 | 単一ノード停止の最大相対損失。Cが最大 |
| 過剰開示 | 7.0 | 0.0 | 11.0 | 共有回数。Cが最多、Bは0 |
| 公共信頼（補助 `public_trust`） | 0.31973 | 0.73973 | 0.07973 | 契約表外の最終状態 |

### centralized → plural（seed 42, CRN・契約指標差分）

| 差分キー | candidate − baseline |
|---|---:|
| continuity | 0.0 |
| evidence_calibration | +0.19175 |
| correction_turn | -1.0 |
| dissent_reach | +0.916667 |
| coordination_dependence | +0.012264 |
| over_disclosure | -7.0 |
| public_trust | +0.42 |

同一seedの外生擾乱列は条件間で一致した（CRN）。これは政策優劣の断定ではなく、仮定下の契約指標差の観測である。

## 反証・限界

- **単一seed**: この記録は seed `42` のみ。順位の安定性は未確認。複数seed集合の正式実験は未実行。
- **生活継続が飽和**: 本seed・閾値0.5では3条件とも比率1.0。条件差は他指標に出る。閾値やシナリオ強度を変えた感度は未実施。
- **勝者なし**: 方向は一様でない（例: pluralは証拠校正・異議・過剰開示で良く、調整依存の leave-one-out 損失は centralized と近い）。総合点による「最強の統治」は主張しない。
- **失敗run**: 本seedでは3条件とも `turn_limit_reached`。吸収状態（継続0）による早期終了は未観測。
- **感度未実施**: 遷移パラメータや主体バイアスの掃引は未実施。
- **境界**: 仮定とseedのもとでの比較であり、現実予測・政策推奨・実在組織の評価ではない。
- **再現**: 同一入力で再実行し、上記値とrun_idが一致することを確認した。エンジン変更後は `source_revision` / `model_config_hash` が変わり得る。
