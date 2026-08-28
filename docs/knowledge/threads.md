# 判断履歴の参照

この表は会話の本文を複製せず、設計判断の由来を辿るためのポインターだけを保持する。

| reference_id | 種別 | 使った判断 | 状態 |
|---|---|---|---|
| application-theme-submission | 通常参加表明 | 応募時テーマ文。個別の参加者番号は公開索引に保持しない | recorded |
| ghost-in-the-sim-design-2026-08-24 | Codex設計作業 | MVP、主体モデル、比較実験、ADR | reflected |
| ghost-in-the-sim-seed42-results-2026-08-28 | Cloud Agent実測 | seed 42 の A/B/C 実測を RESULTS へ記録、PUBLIC_READY を PUBLIC に整合 | reflected |

個人情報、Discordやメールの本文、認証情報、ローカル絶対パスをここへ保存しない。
