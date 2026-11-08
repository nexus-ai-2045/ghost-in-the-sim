# リポジトリ運用ゲート

## 目的

このrepoは、実験の設計・実装・結果・公開判断を混ぜない。以下のゲートは品質や公開可否を一つで保証するものではなく、それぞれ異なる失敗を早く検出する。

| 資産 | このrepoでの役割 | 導入状態 |
|---|---|---|
| `repo-preflight` | PR前のsecret・個人path・README／docs／変更連鎖の確認 | consistency設定は`shadow`、候補側補助workflowとbase側trusted workflowで実行 |
| `ai-ratchet-gate` | trackedかつignoredの新規矛盾を停止 | baseline済み、PR workflowで`v0.2.0`のRelease wheel（SHA-256固定）により再検証 |
| `github-ops-skills` | private PRの事前確認、readback、レビューとmergeを分離 | 運用手順として使用 |
| `worktree-lifecycle-control` | branchごとの隔離、他の作業中変更の保護 | worktree運用として使用 |
| `engineering-brain` | 原典・設計・結果・未解決事項を分離した知識索引 | `docs/knowledge/`へ反映 |
| FDE | 目的、反証、判断境界を先に固定する考え方 | 原則のみ参照。コードや文言を流用しない |

## 実行順

1. 専用branchとworktreeで変更する。
2. ローカルで設計契約・公開境界・ユニットテストを実行する。
3. `repo-preflight` を対象差分で実行する。
4. `ai-ratchet-gate` をbaseline更新なしで実行する。
5. PRへpushし、同一HEADのCI・レビュー・差分をreadbackする。公開repoへのpushは事前の人間確認を必須にする。
6. human review後にのみmergeを検討する。

## `shadow` からの昇格

`.repo-preflight-consistency.json` は最初から`enforce`にしない。通常PRで所見が妥当かを確認し、誤検知を除去してから`ratchet`、最後に空のbaselineを人間レビューしたうえで`enforce`へ上げる。

baselineの更新、workflowの弱体化、CIのskip、公開・merge・releaseは自動で行わない。

## trusted gateの境界

候補側の`repository-contract.yml`は、PR自身が変更できるため補助検査である。信頼境界は`pull_request_target`で動く`repository-contract-trusted.yml`が担い、信頼済みbaseの検査器だけで候補treeをデータとして読む。候補のスクリプトは実行しない。

trusted workflow、候補側workflow、検査器、consistency設定を変更するPRは自動承認しない。初回導入と更新はbootstrap扱いの人間レビューを必要とする。詳細は[ADR-007](../adr/ADR-007-trusted-repository-gate.md)を参照する。

trusted workflowが差分基準を渡す際は、イベントで確定したbase SHAを候補clone内の専用remote-tracking refへ固定し、readbackしてから使う。`origin/main`のような可動refや生SHAを直接渡さず、実行中のbase driftと検査器契約の不一致を同時に防ぐ。

## deterministic coreのruntime契約

`verify.yml` は `pull_request` と `main` への `push` で実行する。PR作成後の作業branchへのpushではPRの同期イベントで検査し、push起点との重複を避ける。PR未作成の `codex/**` branchへのpushでは製品CIを実行しないため、共有前のローカル検査とPR上の検査を必須の運用経路とする。

`verify.yml` の `deterministic-core` jobは、`src` layoutのpackageをpytestだけでなく設計・公開・IPの各検証スクリプトからも同じ条件でimportできるよう、job全体へ `PYTHONPATH=src` を設定する。検証stepごとにruntime設定を重複させず、新しいPython gateを追加したときも同じpackage境界を継承させる。

このruntime契約はローカル検証でも再現し、`PYTHONPATH=src python -c "import tests.test_design_contract_guard, tests.test_ip_boundary"`、`PYTHONPATH=src python tests/check_design_contract.py`、全pytestを実行する。`tests` は明示packageとして補助moduleを `tests.<module>` から参照し、pytestの収集時path注入やOS固有の区切り文字へ依存しない。CIだけでimport経路を特別扱いせず、Linux runnerとWindows worktreeの環境差を検知可能に保つ。

## repo-preflightの固定先

通常の `preflight.yml` は、base-guard廃止後の統合版 `fe2e90f91615a5e5ed3f9b2b497c99f5786e5847` に固定する。専用base-guard workflowは廃止し、通常のpreflightと製品検査を維持する。

補助の `repository-contract.yml`、`repository-contract-trusted.yml` と `.repo-preflight-consistency.json` は独立した信頼境界で、固定版を維持する。CI入口の修復はbase-guard廃止と分け、専用bootstrap PRで人間レビューする。

## 補助CIの入口とbootstrap

補助workflowは、operator用の `readiness_scan --intent open_pr` から、既存のCI入口 `preflight_ratchet.py` と固定版同梱の公開名義一覧へ切り替える。候補headとイベントbaseをSHAで固定し、baselineの信頼基準はイベントbaseとする。consistencyの変更比較だけは、そのbaseとauthored headの一意なmerge-baseを使う。mainが分岐後に進んだ場合も受け入れ、baselineを古い分岐点へ戻さない。runnerの参照はこの二つの専用remote refへ限定する。ratchetのbaseline拡大とtrusted checkerの変更は行わない。

保護workflow自体を変更するPRは旧baseのadvisory監査が拒否する。checkerやbaselineを変えず、本人のbootstrapレビューで採用を判断する。統合後は新しいmainをbaseとする通常PRで監査する。マージ済みPRのAPI `base.sha` は統合前の値を保持するため、同じPRの再実行を新baseの検証として使わない。再実行が必要な場合は、その通常PRを指定して既存workflow_dispatchを使う。

配布物の404を解消するため、既存PR #1のURL・wheel名・SHA-256固定の修正を取り込む。`v0.2.0`の公開Release assetのdigestを照合し、取得と実行を確認する。

補助CIの修復は[PR #13](https://github.com/nexus-ai-2045/ghost-in-the-sim/pull/13)で統合した。専用bootstrapで保護ファイル照合の拒否を人間承認し、必須preflight・製品検査・候補側の補助検査が通ったHEADを採用した。新baseからの通常PR監査は、このbootstrapの承認とは別に成功を確認する。

## PR #3の採否（2026-11-09）

[原案PR #3](https://github.com/nexus-ai-2045/ghost-in-the-sim/pull/3)のheadは `bab3432a79f406f7ba65b87391448a27047fc801`。現main `0bda6c59101d62c52900e509c05c6f2a3e46b87b` と比較して以下のように扱う。

| 原案 | 採否 | 理由 |
|---|---|---|
| 候補側とtrusted側のworkflowを1ファイルに統合 | 見送り | 実行job数は減らず、保護ファイル照合と回帰検査の再編を要する。修復済みの2経路を維持する。 |
| `verify`の`codex/**` pushを除き、PRとmain pushを維持 | 採用 | PR作成後の重複起動を避ける。PR未作成branchのpush検査は行わないという範囲変更を明示する。 |
| 統合に付随するchecker・配布検査・ADRの変更 | 見送り | workflow統合を採用しないため不要。既存の保護境界と2経路の検査を維持する。 |

原案の本文・diff・commitはPR履歴とarchiveタグで保全し、代替PRの検査・統合後に原案PRをsupersededとして閉じる。原案の旧operator入口・古い固定先・取得不能なwheelへ戻す変更は採用しない。検査内容、Python 3.13、必須preflightの定義は変えない。
