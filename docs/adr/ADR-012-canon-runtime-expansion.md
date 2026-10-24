# ADR-012: 設定正本・実装・拡張の分離

- Status: Accepted
- Date: 2026-08-29

## Context

人物、神話名、10事件を一度に設定採用しても、それらがシミュレーターへ実装・実測されたことにはならない。設定、実装、公開を一つの完了状態にすると、ロードマップが嘘になり、事件ごとの例外で決定論コアが崩れる。

## Decision

- 状態を `concept / accepted-setting / contracted / implemented / measured / publication-reviewed` に分ける。
- 世界文書は意味を、architecture文書は機械契約を、コードは挙動を、RESULTSは実測だけを所有する。
- 最初に鏡潮事案で共通scenario schemaを固め、残り9事件は同じschemaへ段階投入する。
- live LLM、外部モデル、クラウド、3D、会話生成は決定論コア外の交換可能adapterにする。
- 新しい拡張は同じrun manifest、seed、trace、replay、反証条件を維持する。

## Consequences

設定を豊かにしつつ、現在のMVPを壊さず発展できる。反面、設定上存在してもUIや状態遷移に未接続な要素を明示し続ける必要がある。
