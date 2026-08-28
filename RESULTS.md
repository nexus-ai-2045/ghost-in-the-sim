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

## 実行コマンド

ローカル出力は `artifacts/`（追跡しない）。再実行で同じ指標になることを確認済み。

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

## 結果

指標は最終状態とイベント列から算出した実測値。総合点は作らない。

| 指標 | 条件A centralized | 条件B plural | 条件C overconnected | 解釈（仮定下） |
|---|---:|---:|---:|---|
| 生活継続 | 0.97907 | 0.70307 | 0.78707 | Aが最も高い。Bは証拠・異議と引き換えに継続が下がる（`continuity`） |
| 証拠校正 | 0.449538 | 1.0 | 0.341538 | Bが上限。Cが最も低い（`evidence_calibration`） |
| 訂正時間 | 4.0 | 2.0 | 6.0 | 低いほど早い。Bが最速、Cが最遅（`correction_turn`） |
| 異議到達率 | 0.083333 | 1.0 | 0.083333 | Bのみ全異議が到達。A/Cは低い（`dissent_reach`） |
| 調整依存 | 1.0 | 0.0 | 0.218753 | Aが上限依存。Bは依存を消す方向（`coordination_dependence`） |
| 過剰開示 | 0.673283 | 0.205283 | 1.0 | Cが上限。Bが最も低い（`over_disclosure`） |
| 参考: 公共信頼 | 0.31973 | 0.73973 | 0.07973 | Bが高く、Cが最も低い（`public_trust`、評価表の補助指標） |

### centralized → plural（seed 42, CRN）

| 差分キー | candidate − baseline |
|---|---:|
| continuity | -0.276 |
| evidence_calibration | +0.550462 |
| correction_turn | -2.0 |
| dissent_reach | +0.916667 |
| coordination_dependence | -1.0 |
| over_disclosure | -0.468 |
| public_trust | +0.42 |

同一seedの外生擾乱列は条件間で一致した（CRN）。これは政策優劣の断定ではなく、仮定下のトレードオフ観測である。

## 反証・限界

- **単一seed**: この記録は seed `42` のみ。順位の安定性は未確認。複数seed集合の正式実験は未実行。
- **勝者なし**: pluralは証拠・異議・依存・開示で有利だが、生活継続では centralized より低い。overconnected は過剰開示と信頼で劣位。総合点による「最強の統治」は主張しない。
- **失敗run**: 本seedでは3条件とも `turn_limit_reached`。吸収状態（継続0）による早期終了は未観測。
- **感度未実施**: 遷移パラメータや主体バイアスの掃引は未実施。
- **境界**: 仮定とseedのもとでの比較であり、現実予測・政策推奨・実在組織の評価ではない。
- **再現**: 同一入力で再実行し、上記指標とrun_idが一致することを確認した。エンジン変更後は `source_revision` / `model_config_hash` が変わり得る。
