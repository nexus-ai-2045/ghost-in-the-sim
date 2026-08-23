# ODD: 決定論MVP

この文書は ODD（Overview, Design concepts, Details）を、再実装可能な最小単位へ縮約して適用する。物語上の着想は入力の説明に留め、モデル本体には特定作品・人物・実在組織を持ち込まない。

## Overview

- **目的**: 架空の公共デジタル基盤障害に対し、三つの調整条件が生活継続・根拠校正・異議・依存・開示圧へ及ぼすトレードオフを比較する。
- **主体・状態・尺度**: 6主体、1都市圏、6ターン（最大12）。主体は `service_steward` などの役割名ではなく、部分観測と留保を伴う抽象的な観測点である。
- **プロセス順序**: 初期状態 → turnごとの条件ルール → 疑似乱数の外乱 → 可逆行動イベント → 状態遷移 → 指標とログ。

## Design concepts

- **部分観測と留保**: 各イベントは `observation_id`、確信度、留保、根拠参照を必須にする。
- **比較可能性**: 条件間でseedを共通化する（common random numbers）。差分は仮定に対する比較であり、現実予測ではない。
- **監査可能性**: 行動は抽象・可逆に限定し、すべてJSON Linesで再読可能にする。

## Details

- **初期化**: `seed` から `random.Random` を作り、状態を一度だけ初期化する。
- **入力**: `condition`、`seed`、`turn_limit`。
- **出力**: `run_manifest.json`、`events.jsonl`、`metrics.json`、`final_state.json`。
- **非対象**: LLM、外部API、実在データ、攻撃・追跡・個人特定・政策最適化。

## 参照

- Grimm et al., [The ODD protocol for describing agent-based and other simulation models](https://www.jasss.org/23/2/7.html) (2020)
- NetLogo, [BehaviorSpace User Manual](https://docs.netlogo.org/behaviorspace)
