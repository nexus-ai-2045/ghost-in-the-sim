# 成果物台帳

| artifact_id | 内容 | 正本 | canonical_state | 実装・実測注記 |
|---|---|---|---|---|
| application-theme-memo | 応募時テーマの記録 | `docs/application-theme-memo.md` | concept | 応募・publication reviewは別gate |
| architecture-overview | MVPの一枚設計 | `docs/architecture/overview.md` | contracted | 実装範囲は個別artifactで管理 |
| simulation-contract | 実行・ログ・再現性契約 | `docs/architecture/simulation-contract.md` | contracted | 決定論コアへ適用済み |
| agent-contract | 主体モデルの契約 | `docs/architecture/agent-contract.md` | contracted | 6主体へ適用済み |
| ui-contract | 実験UIの情報設計 | `docs/design/ui-contract.md` | implemented | デスクトップviewerへ接続済み |
| ai-replica-mvp | 3方式・AI判断replayの実装契約 | `docs/architecture/ai-replica-mvp.md` | implemented | 3方式・seed 17/42/99とactual AI replay証拠を実装済み |
| demo-viewer | 生成比較JSONのローカルviewer | `web/index.html` | implemented | 追跡済み比較JSONを表示 |
| setting-bible | 2036年・ポセイドン・制度の物語正本 | `docs/world/setting-bible.md` | accepted-setting | 世界設定の意味を所有 |
| character-bible | 御影・真壁・班・上層部・対立主体 | `docs/world/characters.md` | accepted-setting | runtime状態へは未接続 |
| naming-taxonomy | 神話命名体系 | `docs/world/naming-taxonomy.md` | accepted-setting | 一部名称を設定・scenarioへ使用 |
| case-catalog | 10事件の企画正本 | `docs/world/cases.md` | concept | 鏡潮相当のみ機械的先行実装 |
| repository-goal | 完了条件・非ゴール・成果物所有 | `docs/product/repository-goal.md` | contracted | repo全体の完了契約 |
| operative-contract | 卓越した実働者を状態・行動・評価へ写像する目標契約 | `docs/architecture/operative-contract.md` | contracted | 実装写像は一部 |
| results-template | 実験結果の記録枠 | `RESULTS.md` | measured | seed 17/42/99・符号反転・actual AI replayを実測 |
| portable-run-bundle | 外部シミュレーターへ渡す再現可能なrun証拠 | `src/ghost_in_the_sim/run_bundle.py` | implemented | `meta-security-run-bundle/v1`、同一run_id、cross-runtime canonical digest、replay検証 |
| agent-turn-session | 外部AIと一手ずつ状態を確定するprovider非依存session | `src/ghost_in_the_sim/agent_session.py` | implemented | 未来requestを先行生成せず、各turnをstrict ingest後に進行し、最終的にportable-run-bundleを出力 |
| submission-demo-script | 追跡済みUI・結果・外部AI境界を3分で説明する発表台本 | `docs/demo-script.md` | implemented | runtimeの実測範囲だけを説明し、提出・公開は人間レビューを維持 |
| submission-slide-deck | 公式上限内の8枚説明スライドを作る正本source | `scripts/generate_submission_slides.js` | implemented | PPTX/PDFはignored `artifacts/submission/`へ生成し全ページ目視済み。提出ファイル名・公開は人間レビュー待ち |
| submission-checklist | 公式提出3点とローカル候補の対応表 | `docs/submission-checklist.md` | measured | 公式サイトを2026-08-30再確認。動画はローカル録画済み、YouTube・提出操作は未実施 |
| submission-demo-recorder | 病院・共同確認・停止要求保留・12ターン完走を録画する開発時script | `scripts/record_submission_demo.js` | implemented | WebM/MP4はignored `artifacts/submission/`へ生成・目視済み。YouTube送信は人間境界 |
