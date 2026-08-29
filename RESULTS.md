# RESULTS

> この台帳は、実際に実行したrunだけを記録する。計画値・期待値・未実行の推測を結果として書かない。

## 実験識別

| 項目 | 値 |
|---|---|
| 記録日 | `2026-08-28` |
| 実行実装commit | `48542c9b02bfd8dcfab85c8a612dac3cfce24278` |
| コード版 | `deterministic-core-v2` |
| モデル版 | `0.2.0` |
| `model_config_hash` | `74345ee9673ec2bf` |
| `source_revision` | `62a1c6cb5f5a4251` |
| シナリオ | `poseidon-public-infrastructure-01` |
| seed集合 | `{42}`（代表1 seed。複数seedの正式実験は未実行） |
| 比較条件 | A=`centralized` / B=`plural` / C=`overconnected` |
| ターン上限 | `12` |
| モデル設定 | 標準ライブラリによるルールベース。LLMなし |
| Python | `3.12.3` |
| 実行環境 | Linux / `PYTHONPATH=src` |

## 測定物と評価契約の境界

`docs/architecture/evaluation.md` の契約指標（ターン比率・整合・ノード停止損失・開示回数など）は、現行コアでは**未実装**である。

本記録の数値は `engine._metrics()` が返す**状態プロキシ／イベント派生値**であり、契約指標そのものではない。同名・類似名で並べても、契約どおりの算出ではない。契約実装後に再実行して差し替える。

| 記録キー | 実際の定義（現行コア） | 契約指標との関係 |
|---|---|---|
| `continuity` | 最終 `WorldState.continuity` | 生活継続（維持ターン比率）の**プロキシではない代替**。最終スカラーのみ |
| `evidence_calibration` | 最終 `WorldState.evidence_quality` | 証拠校正（確信度と後続検証の整合）の**未実装**。最終スカラーのみ |
| `correction_turn` | 最初の `issue_correction` ターン（なければ turn_limit+1） | 訂正時間に**近いイベント派生**。誤共有の訂正完了判定は未実装 |
| `dissent_reach` | `dissent_delivered / dissent_raised` | 異議到達率に**近いイベント派生** |
| `coordination_dependence` | 最終 `WorldState.coordination_dependence` | 調整依存（単一ノード停止損失）の**未実装**。最終スカラーのみ |
| `over_disclosure` | 最終 `WorldState.disclosure_pressure` | 過剰開示（必要性超過の共有回数）の**未実装**。最終スカラーのみ |
| `public_trust` | 最終 `WorldState.public_trust` | 契約表外の補助状態 |

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
| A centralized | `run-ebd1a6e388a7` | `turn_limit_reached` | 12 |
| B plural | `run-846792cc60bb` | `turn_limit_reached` | 12 |
| C overconnected | `run-46bb5ac9a8a3` | `turn_limit_reached` | 12 |

## 結果（状態プロキシ／イベント派生・契約指標ではない）

総合点は作らない。列名の日本語は参照用であり、契約指標の達成を意味しない。設計契約検査用に `| 過剰開示 |` 行を残す。

| 記録キー（日本語参照名） | 条件A centralized | 条件B plural | 条件C overconnected | 読み（仮定下・プロキシ比較） |
|---|---:|---:|---:|---|
| 生活継続プロキシ (`continuity`) | 0.97907 | 0.70307 | 0.78707 | Aの最終継続スカラーが最も高い |
| 証拠品質プロキシ (`evidence_calibration`) | 0.449538 | 1.0 | 0.341538 | Bが上限。校正整合の計測ではない |
| 初回訂正ターン (`correction_turn`) | 4.0 | 2.0 | 6.0 | イベント派生。低いほど初回訂正が早い |
| 異議配信比 (`dissent_reach`) | 0.083333 | 1.0 | 0.083333 | イベント派生。Bのみ全件配信 |
| 調整依存プロキシ (`coordination_dependence`) | 1.0 | 0.0 | 0.218753 | 最終スカラー。ノード停止損失ではない |
| 過剰開示 | 0.673283 | 0.205283 | 1.0 | 開示圧の最終スカラー（`over_disclosure`）。共有回数ではない |
| 公共信頼プロキシ (`public_trust`) | 0.31973 | 0.73973 | 0.07973 | 契約表外の補助状態 |

### centralized → plural（seed 42, CRN・プロキシ差分）

| 差分キー | candidate − baseline |
|---|---:|
| continuity | -0.276 |
| evidence_calibration | +0.550462 |
| correction_turn | -2.0 |
| dissent_reach | +0.916667 |
| coordination_dependence | -1.0 |
| over_disclosure | -0.468 |
| public_trust | +0.42 |

同一seedの外生擾乱列は条件間で一致した（CRN）。これは政策優劣の断定ではなく、仮定下のプロキシ差の観測である。

## 反証・限界

- **契約未達**: 評価設計の生活継続・証拠校正・調整依存・過剰開示は未実装。本表を契約指標の順位として読まない。
- **単一seed**: この記録は seed `42` のみ。順位の安定性は未確認。複数seed集合の正式実験は未実行。
- **勝者なし**: プロキシ上でも方向は一様でない（例: pluralは証拠品質・異議で高く、最終継続は centralized より低い）。総合点による「最強の統治」は主張しない。
- **失敗run**: 本seedでは3条件とも `turn_limit_reached`。吸収状態（継続0）による早期終了は未観測。
- **感度未実施**: 遷移パラメータや主体バイアスの掃引は未実施。
- **境界**: 仮定とseedのもとでの比較であり、現実予測・政策推奨・実在組織の評価ではない。
- **再現**: 同一入力で再実行し、上記値とrun_idが一致することを確認した。エンジン変更後は `source_revision` / `model_config_hash` が変わり得る。
