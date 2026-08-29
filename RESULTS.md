# RESULTS

> この台帳は、実際に実行したrunだけを記録する。計画値・期待値・未実行の推測を結果として書かない。

## 実験識別

| 項目 | 値 |
|---|---|
| 記録日 | `2026-08-29` |
| 実行実装commit | `pending-current-tree`（PR commit後に固定） |
| コード版 | `deterministic-core-v2` |
| モデル版 | `0.2.0` |
| `model_config_hash` | runごとにAI判断traceを含めて変化（下表のrun IDで固定） |
| `source_revision` | `db862c10651c97f1` |
| シナリオ | `poseidon-replica-crisis-01` |
| seed集合 | `{42}`（代表1 seed。複数seedの正式実験は未実行） |
| 比較条件 | A=`centralized` / B=`plural` / C=`autonomous` |
| ターン上限 | `12` |
| 判断設定 | この開発セッションでAIが生成した9判断をfixtureからreplay。外部モデルAPI呼出なし。状態deltaは方式別の決定論モデル |
| 指標定義 | `docs/architecture/evaluation.md` の MVP運用定義（claim↔検証は observation 参照で紐付け） |
| Python | `3.13` |
| 実行環境 | Linux / `PYTHONPATH=src` |

## 測定物と評価契約

本記録の数値は `engine._metrics()` が **evaluation.md のMVP運用定義どおり** に集計した契約指標である。最終 `WorldState` スカラーの代用ではない。

| 記録キー | 契約上の意味 | 本runでの算出 |
|---|---|---|
| `continuity` | 生活継続（維持ターン比率） | 各ターン後 `continuity >= 0.5` の比率（早期終了後は非維持） |
| `evidence_calibration` | 証拠校正（確信度と後続検証の整合） | 主張の `observation_ids` を `rationale_refs` で明示参照する後続検証だけを実現値に使う |
| `correction_turn` | 訂正時間 | 訂正前の情報共有から `issue_correction` までのターン差（共有が無ければ訂正ターン番号） |
| `dissent_reach` | 異議到達率 | `dissent_delivered / dissent_raised` |
| `coordination_dependence` | 調整依存（単一ノード停止損失） | 協調量の leave-one-out 最大相対損失（内部シミュレーション。公開 run_id には載せない） |
| `over_disclosure` | 過剰開示 | 必要性超過の共有**回数** |
| `public_trust` | 契約表外の補助 | 最終 `WorldState.public_trust` |

## 実行コマンド

ローカル出力は `artifacts/`（追跡しない）。再実行で同じ出力になることを確認済み。

```powershell
$env:PYTHONPATH = "src"
py -3.13 -m ghost_in_the_sim.batch_cli --output web/data/comparison.json --seed 42 --actual-ai-trace fixtures/actual-ai-trace-seed42.json
```

```bash
PYTHONPATH=src python3 -m ghost_in_the_sim.batch_cli --output web/data/comparison.json --seed 42 --actual-ai-trace fixtures/actual-ai-trace-seed42.json
```

## run識別子

| 条件 | run_id | 終了理由 | 完了ターン |
|---|---|---|---:|
| A centralized | `run-35bb553f8687` | `turn_limit_reached` | 12 |
| B plural | `run-2f3c6bf15ecf` | `turn_limit_reached` | 12 |
| C autonomous | `run-0e5b1ba37436` | `turn_limit_reached` | 12 |

## 結果（契約指標・seed 42 実測）

総合点は作らない。設計契約検査用に `| 過剰開示 |` 行を残す。

| 指標 | 条件A centralized | 条件B plural | 条件C autonomous | 読み（仮定下・断定しない） |
|---|---:|---:|---:|---|
| 生活継続 (`continuity`) | 1.0 | 1.0 | 1.0 | 閾値0.5のもと、3条件とも全ターン維持 |
| 証拠校正 (`evidence_calibration`) | 0.469122 | 0.640914 | 0.0 | 紐付け後。Bが最も高い |
| 訂正時間 (`correction_turn`) | 3.0 | 2.0 | 13.0 | 低いほど速い。Cは上限内に訂正なし |
| 異議到達率 (`dissent_reach`) | 0.083333 | 1.0 | 0.333333 | Bのみ全件配信 |
| 調整依存 (`coordination_dependence`) | 0.26458 | 0.282652 | 0.277786 | 単一ノード停止の最大相対損失 |
| 過剰開示 | 8.0 | 0.0 | 0.0 | 共有回数。Aのみ8回 |
| 公共信頼（補助 `public_trust`） | 0.368094 | 0.798254 | 0.502214 | 契約表外の最終状態 |

### centralized → plural（seed 42, CRN・契約指標差分）

| 差分キー | candidate − baseline |
|---|---:|
| continuity | 0.0 |
| evidence_calibration | +0.171792 |
| correction_turn | -1.0 |
| dissent_reach | +0.916667 |
| coordination_dependence | +0.018072 |
| over_disclosure | -8.0 |
| public_trust | +0.43016 |

同一seedの外生擾乱列は条件間で一致した（CRN）。これは政策優劣の断定ではなく、仮定下の契約指標差の観測である。

## 反証・限界

- **単一seed**: この記録は seed `42` のみ。順位の安定性は未確認。複数seed集合の正式実験は未実行。
- **生活継続が飽和**: 本seed・閾値0.5では3条件とも比率1.0。条件差は他指標に出る。閾値やシナリオ強度を変えた感度は未実施。
- **勝者なし**: 方向は一様でない（例: pluralは証拠校正・異議・過剰開示で良く、調整依存の leave-one-out 損失は centralized と近い）。総合点による「最強の統治」は主張しない。
- **失敗run**: 本seedでは3条件とも `turn_limit_reached`。吸収状態（継続0）による早期終了は未観測。
- **感度未実施**: 遷移パラメータや主体バイアスの掃引は未実施。
- **境界**: 仮定とseedのもとでの比較であり、現実予測・政策推奨・実在組織の評価ではない。
- **AI判断の効力**: AI生成actionとconfidenceは、許可済み6 actionの固定・有界deltaとして該当ターンへ反映する。任意コードや自由形式命令は実行しない。
- **再現**: 同一入力で再実行し、上記値とrun_idが一致することを確認した。エンジン変更後は `source_revision` / `model_config_hash` が変わり得る。
