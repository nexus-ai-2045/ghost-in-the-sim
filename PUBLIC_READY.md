# PUBLIC_READY

## 状態

`public_visibility_confirmed` — 機械確認済みの公開状態記録。公開承認・merge承認・release承認ではない。

## live read-back（2026-08-28）

| 項目 | 値 |
|---|---|
| repository | `nexus-ai-2045/ghost-in-the-sim` |
| visibility | `PUBLIC`（変更しない。この文書は状態の正本化のみ） |
| default branch | `main` |
| 基準commit（実測記録時点） | `48542c9b02bfd8dcfab85c8a612dac3cfce24278` |

## 今回の公開対象

- Nexus作成のREADME、運用文書、オリジナル実装（決定論コア）
- ハッカソン公式サイトへのリンク
- `RESULTS.md` に記録した架空シナリオの仮定下比較（現実予測ではない）

## 公開対象外

- 片山氏のコンセプトペーパー本文
- 創作作品の画像、本文、台詞、OCR、アーカイブ、再現素材
- 個人情報、会話ログ、認証情報、非公開リンク
- `artifacts/` 配下のローカル実験出力（追跡しない）

## 確認済み（機械）

- [x] GitHub visibility を read-back し `PUBLIC` であることを確認した
- [x] 可視性変更（`gh repo edit ... --visibility public`）は不要。既に公開済みのため実行しない

## 確認待ち（人間）

- 片山氏コンセプトペーパーの公開URL、正式な版番号、引用条件
- 人間による表示・履歴レビュー
- merge / release / 告知の明示承認（このファイルだけでは承認されない）
