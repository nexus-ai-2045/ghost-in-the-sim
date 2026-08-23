# リポジトリ運用ゲート

## 目的

このrepoは、実験の設計・実装・結果・公開判断を混ぜない。以下のゲートは品質や公開可否を一つで保証するものではなく、それぞれ異なる失敗を早く検出する。

| 資産 | このrepoでの役割 | 導入状態 |
|---|---|---|
| `repo-preflight` | PR前のsecret・個人path・README／docs／変更連鎖の確認 | consistency設定は`shadow`、PR workflowで実行 |
| `ai-ratchet-gate` | trackedかつignoredの新規矛盾を停止 | baseline済み、PR workflowで再検証 |
| `github-ops-skills` | private PRの事前確認、readback、レビューとmergeを分離 | 運用手順として使用 |
| `worktree-lifecycle-control` | branchごとの隔離、他の作業中変更の保護 | worktree運用として使用 |
| `engineering-brain` | 原典・設計・結果・未解決事項を分離した知識索引 | `docs/knowledge/`へ反映 |
| FDE | 目的、反証、判断境界を先に固定する考え方 | 原則のみ参照。コードや文言を流用しない |

## 実行順

1. 専用branchとworktreeで変更する。
2. ローカルで設計契約・公開境界・ユニットテストを実行する。
3. `repo-preflight` を対象差分で実行する。
4. `ai-ratchet-gate` をbaseline更新なしで実行する。
5. private PRへpushし、同一HEADのCI・レビュー・差分をreadbackする。
6. human review後にのみmergeを検討する。

## `shadow` からの昇格

`.repo-preflight-consistency.json` は最初から`enforce`にしない。通常PRで所見が妥当かを確認し、誤検知を除去してから`ratchet`、最後に空のbaselineを人間レビューしたうえで`enforce`へ上げる。

baselineの更新、workflowの弱体化、CIのskip、公開・merge・releaseは自動で行わない。
