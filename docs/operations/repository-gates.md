# リポジトリ運用ゲート

## 目的

このrepoは、実験の設計・実装・結果・公開判断を混ぜない。以下のゲートは品質や公開可否を一つで保証するものではなく、それぞれ異なる失敗を早く検出する。

| 資産 | このrepoでの役割 | 導入状態 |
|---|---|---|
| `repo-preflight` | PR前のsecret・個人path・README／docs／変更連鎖の確認 | consistency設定は`shadow`、候補側補助workflowとbase側trusted workflowで実行 |
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

`verify.yml` の `deterministic-core` jobは、`src` layoutのpackageをpytestだけでなく設計・公開・IPの各検証スクリプトからも同じ条件でimportできるよう、job全体へ `PYTHONPATH=src` を設定する。検証stepごとにruntime設定を重複させず、新しいPython gateを追加したときも同じpackage境界を継承させる。

このruntime契約はローカル検証でも再現し、`PYTHONPATH=src python tests/check_design_contract.py` と全pytestを実行する。CIだけでimport経路を特別扱いせず、Linux runnerとWindows worktreeの環境差を検知可能に保つ。
