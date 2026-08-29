# 設計判断

| ID | 判断 | 状態 | 根拠 |
|---|---|---|---|
| ADR-001 | 原作IPではなくオリジナル主体モデルを使う | accepted | 権利境界と再現可能性 |
| ADR-002 | 単一最適解でなく条件比較と反証を中心にする | accepted | メタ安全保障の連鎖観測 |
| ADR-003 | 主体に部分観測・留保・関係・履歴を持たせる | accepted | 単純な役職エージェントを避ける |
| ADR-004 | 先に決定論的コアとログ契約を作る | accepted | 再現性とLLM代替 |
| ADR-005 | Web UIは実験台として設計する | accepted | 実データ接続とデスクトップ目視を完了 |
| ADR-006 | scenario / experiment / run manifest / result cardを分離する | proposed | 比較・replay・反証を混同しないため |
| ADR-007 | 外部ABM frameworkは初期MVPへ導入せず、決定論コア完了後に評価する | proposed | 依存を増やす前に契約とfixtureを確立するため |
| ADR-008 | 便益だけでなく、離脱・格差・目的外利用・訂正可能性を観測する | proposed | リスクと人間監督を測定系へ入れるため |
| ADR-009 | 別PRIVATE SSOTの知識は抽象化した設計原則だけを参照する | accepted | 原典・会話・実装・公開候補を分離するため |
