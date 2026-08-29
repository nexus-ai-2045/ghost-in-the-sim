# 未解決事項

| 問い | owner | 次の判断 | 完了条件 |
|---|---|---|---|
| MVPの最初の条件A/B/Cは十分に区別できるか | ねく | シナリオレビュー | 3条件の差分表を承認 |
| seed 42 で centralized / plural / autonomous を実測し RESULTS に残すか | ねく | 代表runの記録 | `RESULTS.md` にAI判断反映後の実測値・run_id・限界を記録（2026-08-29 完了） |
| 評価契約どおりの指標算出（ターン比率・検証整合・ノード停止損失・開示回数） | 実装フェーズ | `_metrics()` を契約実装へ置換 | evaluation.md の定義で再計測し RESULTS を差し替え（2026-08-29 完了） |
| 複数seed集合での順位安定性 | 実装フェーズ | seed集合を固定して再実行 | 複数seedの指標分布と反転有無を RESULTS へ追記 |
| live LLM adapterとaction別deltaを入れるか | ねく | replay MVPとの比較 | モデル設定・コスト・再現性・安全境界を記録 |
| UIコンセプトのトーン | ねく | デザインレビュー | デスクトップ目視完了。モバイル実機を確認 |
| 提出用実行環境 | 実装フェーズ | ローカル動作確認 | batch生成とviewer起動をREADMEどおり再現（Windows完了） |
| GitHub Actions の遠隔回帰 | ねく / GitHub Billing | アカウントの支払い・利用上限を確認後に同一HEADで再実行 | `verify` のジョブが開始され、同一HEADで成功する |
| 公式要件の最終確認 | ねく | 提出直前に公式を再確認 | README・結果・資料の整合 |
| 鏡潮事案のscenario schema | 実装フェーズ | 現行MVPを型付きmanifestへ移行 | 事件固有例外なしで御影・真壁・反証・代償を再現 |
| 名称・配色・HUD・宣伝文の束レビュー | ねく | 応募・release前に人間が目視 | `PUBLIC_READY.md` の残務を解消 |
