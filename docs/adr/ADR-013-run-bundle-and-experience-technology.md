# ADR-013: run bundleを体験技術より先に固定する

- 状態: 採用
- 日付: 2026-08-30

## 文脈

このrepo固有の価値は、ポセイドン危機対応runの判断・訂正・異議・証拠を同じ実行として追跡できることにある。描画技術を先に増やすと、既存Python runtimeとブラウザ表示のどちらが正本か曖昧になる。

## 決定

既存の `ReplicaRun` を唯一の実行正本とし、portable出力を `meta-security-run-bundle/v1` とする。`run_request`、`event_stream`、`replay`、`evidence` は同一 `run_id` を持つ。eventはturn昇順とし、各区画のCanonical JSONをSHA-256で検証したうえで既存runtimeによる再実行一致も確認する。

cross-runtime digestは `meta-security-json-c14n/v1` を使う。run identityはrequestとdecision provenanceへ結合し、verified表明はruntime replay成功後にだけ生成する。

初期版ではThree.js、GSAP、Hyperframes、Godotを採用しない。現在の体験はテキスト中心の比較・時系列選択であり、DOM/CSS/標準JavaScriptでアクセシブルに成立しているためである。

鏡潮の初期プレイ体験は、検証済みtrajectoryから介入方針を選び、12ターンを順に再生するDOMベースの作戦ゲームとする。ブラウザは新しい結果を計算せず、Python runtimeが付与した `replay-match` を構造検査して表示する。暗号学的検証とruntime replayの正本は引き続きPython側に置く。

- Three.js: 3D空間または関係網が判断理解を改善すると実測できた場合だけ、該当画面でdynamic importする。WebGL不能時は既存DOM表へ戻す。
- GSAP: 状態遷移の補間が理解を改善し、`prefers-reduced-motion`のfallbackを維持できる場合だけdynamic importする。現段階ではクリック式replayを維持する。
- Hyperframes: 発表動画またはVisual QAの開発時toolに限定し、通常runtime bundleへ含めない。
- Godot: 操作可能なゲームloopがWeb viewerから独立して必要になった場合だけ、このrepo側でprojectを所有する。engine本体やbinaryはcommitせず、`meta-security-sim`へ移さない。

## dependencyとlicense

今回の追加dependencyはない。Python標準ライブラリと既存のHTML/CSS/JavaScriptだけを使い、repoのMIT Licenseと `THIRD_PARTY_NOTICES.md` の境界を変更しない。将来採用時はThree.js（MIT）、GSAP（GreenSock Standard License）、Hyperframes（Apache-2.0）、Godot（MITとexport templateの第三者notice）を個別に記録する。

## Nexus既存資産との境界

通常runtimeへ他repoの実装をコピーしない。`meta-security-run-bundle/v1` はこのrepoが所有する。

- `nexus-activity-log`: source identity、idempotent ingestion、append-only provenanceの原則を採用する。activity-event schema自体は混ぜない。
- `toc-engine`: bundle生成後の任意offline制約評価に使えるが、simulation runtimeへ依存させない。
- `runtime-process-guard`: 将来の外部runner起動時にprocess admission・lease・closeout wrapperとして使い、ブラウザbundleへ含めない。
- `engineering-brain`: 実装前の既存資産探索とPR closeout gateに利用し、domain schemaへ混ぜない。
- `nexus-management-os`、FDE: provenance、Goal→Evidence→Verify→Closureの設計原則だけを参照する。FDEのsource-available資産をコピーしない。
- `nexus_ai`、`ai-round-table`、`capability-atlas`、`zunda-voice-bot`: 今回のrun体験に直接必要なruntime機能がないため不採用とする。

## 撤退方法

bundle層は既存runtimeを変更せず追加される。撤退時は `run_bundle.py`、`run_bundle_cli.py`、対応test・文書だけを除去し、従来の `batch_cli` と `comparison.json`へ戻す。将来の描画技術もrenderer adapterとして隔離し、bundle生成へ依存を逆流させない。
