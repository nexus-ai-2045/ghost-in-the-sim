# PUBLIC_READY

## 状態

`public_visibility_confirmed` — 機械確認済みの公開状態記録。公開承認・merge承認・release承認ではない。

## 提出済みベースライン（2026-08-30）

| 項目 | 値 |
|---|---|
| repository | `nexus-ai-2045/ghost-in-the-sim` |
| visibility | `PUBLIC`（変更しない。この文書は状態の正本化のみ） |
| default branch | `main` |
| submitted release | `v0.1.2` |
| submitted commit | `c00183fbd8d79a5df018283b0dcde53ac73790cd` |
| `main` / tag整合 | 同一commitを確認済み |

## 今回の公開対象

- Nexus作成のREADME、運用文書、オリジナル実装（決定論コア、判断replay、比較UI）
- この開発セッションでAIが生成した9件の型付き判断fixtureと、そこから生成した比較JSON
- ハッカソン公式サイトへのリンク
- `RESULTS.md` に記録した架空シナリオの仮定下比較（現実予測ではない）
- ポセイドン、御影冴、接界機動班、人物、神話命名、10事件候補を記述した世界設定文書とADR。設定採用はruntime実装・応募・release承認を意味しない

## 公開対象外

- 片山氏のコンセプトペーパー本文
- 創作作品の画像、本文、台詞、OCR、アーカイブ、再現素材
- 個人情報、会話ログ、認証情報、非公開リンク
- `artifacts/` 配下のローカル実験出力（追跡しない）。`web/data/comparison.json` はデモ再現用の追跡済み生成物として公開対象

## 確認済み（機械）

- [x] GitHub visibility を read-back し `PUBLIC` であることを確認した
- [x] 可視性変更（`gh repo edit ... --visibility public`）は不要。既に公開済みのため実行しない

## 確認待ち（人間）

- 片山氏コンセプトペーパーの公開URL、正式な版番号、引用条件
- 人間による表示・履歴レビュー
- 次回のpush / PR作成 / merge / release / 告知の明示承認（このファイルだけでは承認されない）
- リポジトリ名・package名・配色・HUD・キービジュアル・宣伝文を束で見た商標および総合的類似性レビュー
- 画像・動画・音声を追加する場合のcreator、license、source、hashを含むprovenance確認

## 今回の人間決定（2026-08-29）

- 都市名「ポセイドン」と御影冴を中心とする設定を採用する。
- 境界を「名称オマージュを明示する非公式の二次創作的プロジェクト」とする。
- この決定は設定とPR作業の承認であり、応募、release、告知、画像・音声追加の承認ではない。

## 提出後の境界（2026-08-30）

- `v0.1.2`は提出済みベースラインとして保全する。
- 提出後の継続開発は新しい差分として扱い、public repoへのpush、PR作成、merge、release、告知は対象と検証証拠を示して人間レビューへ戻す。
- 応募フォーム編集URL、非公開URL、参加者情報はrepoへ保存しない。
