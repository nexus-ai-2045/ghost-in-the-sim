# ハッカソン提出チェックリスト

2026-08-30に[公式サイト](https://hackathon.automata-lab.jp/)を再確認した。提出締切は2026-08-30 23:59。提出操作、YouTubeへのアップロード、公開・告知は人間レビュー後に行う。

## 公式提出物と現在地

| 公式提出物 | 公式要件 | このrepoの候補 | 状態 |
|---|---|---|---|
| GitHubリポジトリ | public、ソース、環境構築から実行までのREADME、実行スクリプト、生ログ、解析用データ | `nexus-ai-2045/ghost-in-the-sim`、`README.md`、`src/`、`scripts/`、`fixtures/actual-ai-trace-seed42.json`、`web/data/comparison.json`、`RESULTS.md` | ローカル候補検証済み。candidate branchのpush・PR・mergeは人間確認待ち |
| 説明スライド | 10枚以下 | `artifacts/submission/submission-slides.pptx` / `.pdf`（8枚、Git非追跡）、正本sourceは`scripts/generate_submission_slides.js` | 構造検証・全ページ目視済み。名称・説明の人間レビュー待ち |
| デモ動画 | シミュレーターの動作画面、YouTube限定公開 | `docs/demo-script.md` | 録画・YouTubeアップロード・URL取得は未実施 |

## 機械確認済み

- `152 passed / 1 skipped`
- public、design、IP、experience contractがPASS
- repo-preflight、consistency gate、ai-ratchet-gateがPASS
- desktopとmobile相当で開始、12ターン、第8ターン停止要求、結果まで完走
- 12ターンの逐次agent sessionが`meta-security-run-bundle/v1`を生成し`replay-match`
- スライド8枚をPPTX validatorで検証し、PDF全ページを目視

スライドを再生成する場合は、bundled Node.jsから次を実行する。通常のruntime依存には含めない。

```powershell
$env:NODE_PATH = "<Codex workspace dependenciesのnode_modules>"
node scripts/generate_submission_slides.js artifacts/submission/submission-slides.pptx
```

## 人間が入力・確認するもの

1. 参加者番号、提出者名、最終タイトルを確認する。
2. ファイル名を公式指定の半角英数字 `参加者番号_氏名_タイトル_種別` へ変更する。
3. ローカルデモを録画し、YouTubeへ限定公開でアップロードする。
4. README、画面、スライド、動画、commit履歴、第三者権利境界を目視する。
5. candidate branchのPRを同一HEADのCI・レビュー後にmergeする。
6. GitHub、スライド、YouTube URLを提出フォームへ入力する。

## 断定しないこと

- 合成シナリオの結果を現実予測・因果証明・政策推奨として扱わない。
- 計算規模だけを創発性の証拠にしない。
- 外部AIの応答を未検証のまま採用しない。
- 名称オマージュを公式提携・許諾・同一世界と表示しない。
- CIや機械ゲートを人間の公開・提出承認の代わりにしない。
