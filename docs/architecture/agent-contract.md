# エージェント契約

## 設計原則

主体を「行政」「市民」のような単純な役職に縮めない。各主体は、同じ出来事を異なる履歴と関係のもとで受け取り、確信と留保を分けて表明する。

## 最小プロファイル

```yaml
id: evidence_verifier
mission: 根拠の来歴と反証条件を残す
values:
  - 訂正可能性
  - 生活継続
relationships:
  coordination_room: cooperative_but_independent
  information_broker: skeptical
private_context:
  - 過去の誤報で地域の信頼を損ねた経験
observation_scope:
  - 公開観測
  - 匿名化された技術メタデータ
authority:
  can_request_verification: true
  can_issue_public_notice: false
constraints:
  - 未検証情報を確証として発信しない
  - 個人情報を扱わない
beliefs:
  disruption_cause: {value: "unknown", confidence: 0.28}
reservations:
  - 独立確認がない
refutation_conditions:
  - 独立した二経路が同じ原因を示した場合は原因仮説を更新する
```

## 必須の状態

| 状態 | 意味 | 例 |
|---|---|---|
| 目的 | 何を守ろうとするか | 生活継続、説明責任、地域の信頼 |
| 価値 | 衝突時に何を優先するか | 迅速性、訂正可能性、最小開示 |
| 私的文脈 | 同じ情報でも反応を変える履歴 | 過去の失敗、現場の事情 |
| 関係 | 協力・緊張・依存の構造 | 信頼、疑念、情報非対称 |
| 観測範囲 | 見える情報と見えない情報 | 現場報告、公開投稿、集計値 |
| 権限 | できること／できないこと | 検証依頼、説明更新、決定不可 |
| 信念 | 命題ごとの値・確信・根拠 | 原因不明、信頼度0.28 |
| 留保 | 知らないこと・反証条件 | 独立確認がない |

## 発話・行動スキーマ

各ターンでエージェントは、次の構造を返す。

```json
{
  "interpretation": "観測から言える範囲",
  "confidence": 0.42,
  "reservation": "不足している情報または反証条件",
  "question": "他主体へ確認する一点",
  "proposal": {
    "action_type": "request_verification",
    "arguments": {"observation_id": "obs-01"},
    "explanation": "独立確認が不足しているため"
  },
  "reversibility": "high|medium|low",
  "evidence_refs": ["obs-01"]
}
```

`confidence` は `0.0` 以上 `1.0` 以下の有限数とし、`reservation` とともに必須にする。`proposal.action_type` と `proposal.arguments` は許可済みポリシーへ照合し、自由文の説明だけで行動を許可しない。スキーマ違反、範囲外の確信度、未登録の行動は棄却して監査ログへ残す。

## 相互作用

- 主体は、他主体の提案を採用、質問、保留、反対できる。
- 反対は失敗ではない。理由と反証条件が残るなら、システムの観測対象である。
- 同じ情報を全主体へ配らない。共有は経路と遅延を持つ。
- 友情・対立・依存を固定的な性格付けにせず、行動履歴で更新可能にする。

## LLM利用時のガード

- モデルには架空設定と許可行動だけを渡す。
- 実在組織への指示、個人情報、技術的攻撃手順を要求しない。
- 出力は構造化検証を通し、スキーマ違反・根拠欠落・禁止行動を棄却する。
- LLM障害時は、ルールベースの安全なフォールバックを使い、失敗をログに残す。
