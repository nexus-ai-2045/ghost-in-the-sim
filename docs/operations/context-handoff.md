# 再開コンテキスト契約

この文書は進捗の正本ではない。チャット履歴を持たない次の担当が、リポジトリ内の正本と実測だけから作業を再開するための入口である。現在のbranch、HEAD、worktree絶対パス、テスト件数は固定せず、必ず下記コマンドで再測定する。

## 正本の読み順

| 順番 | 正本 | 所有する内容 |
|---:|---|---|
| 1 | [`docs/product/repository-goal.md`](../product/repository-goal.md) | リポジトリゴール、完了条件、非ゴール、成果物の所有 |
| 2 | [`docs/architecture/ai-replica-mvp.md`](../architecture/ai-replica-mvp.md) | AI複製主体MVPと今日の受入条件 |
| 3 | [`docs/architecture/simulation-contract.md`](../architecture/simulation-contract.md) | ターン、状態遷移、再現性、`meta-security-run-bundle/v1` |
| 4 | [`docs/architecture/agent-contract.md`](../architecture/agent-contract.md) | 主体の観測・目的・権限と提案検証 |
| 5 | [`docs/roadmap.md`](../roadmap.md) | phase、実装順、受入条件。チェック済みだけを実測済みとして扱う |
| 6 | [`docs/knowledge/artifacts.md`](../knowledge/artifacts.md) | 成果物ごとの設定・契約・実装・実測状態 |
| 7 | [`docs/operations/repository-gates.md`](repository-gates.md) | ローカル検証、PR、公開、人間レビューの境界 |

意味が衝突した場合は、上位文書を何でも優先するのではなく、上表の「所有する内容」で責務を分ける。設定が存在すること、コードが存在すること、テストが通ること、目視確認済みであること、公開承認済みであることを相互に代用しない。

## いま閉じるゴール

最終ゴールは `repository-goal.md` の再現可能な意思決定シミュレーターである。現在の実装焦点は、決定論的なポセイドン世界の上で、異なる部分観測・目的・権限を持つ複数のAI主体が提案、質問、異議、保留を相互に生じさせ、その過程を安全に記録・再生できる **AI創発シミュレーターMVP** にすること。

この焦点は次をすべて満たした時だけ完了候補になる。

1. 世界状態、外生事象、seed、event順序は既存runtimeが正本であり、AI出力が直接書き換えない。
2. 複数主体は、`agent-contract.md` に従う異なる観測、目的、権限、留保を持つ。
3. 観測、提案、構造検証、採否、適用した状態遷移を別の証拠として残し、未登録actionや根拠欠落をfail closedで拒否する。
4. 相互作用は有界なturn schedulerで終了し、停止理由と未解決の異議を記録する。
5. run request、event stream、replay、evidenceを同じ`run_id`の`meta-security-run-bundle/v1`へ結ぶ。
6. live AIの非決定的な提案を決定論と偽らず、一度記録したrunは外部AIなしでexact replayできる。
7. 主体間の提案差、協力、異議、見かけの合意、未解決相互作用を、単一の勝敗スコアへ潰さず観測できる。
8. ローカルUIでプレイヤーの判断とAI主体間の相互作用を区別して目視でき、既存のアクセシビリティとゲーム経路を壊さない。

この節は完了自己申告ではない。実装状態は `artifacts.md`、phaseは `roadmap.md`、成立証拠は該当テストと生成bundleから導出する。未チェック項目、未登録artifact、失敗・未実行の検証は残務である。

## 境界

- 実装正本はこのrepoの既存runtimeとドメインロジックであり、`meta-security-sim`へ移さない。
- 外部model、Google Cloud、別rendererはadapterであり、状態遷移やevent順序を再計算しない。
- 現実の公安・警察・軍・自治体の再現、実用的な攻撃手順、外部システムの自律操作は非ゴールである。
- push、PR、merge、release、公開、visibility、settings、auth、secret、削除は、実装完了とは別の承認境界である。
- 一時worktree、ローカル絶対パス、会話、未追跡fileを正本にしない。

## 再開時の実測

PowerShellでリポジトリルートから実行する。

```powershell
git status --short --branch
git log -1 --oneline
git worktree list
$env:PYTHONPATH = "src"
py -3.13 -m pytest -q
py -3.13 tests/check_design_contract.py
py -3.13 -m compileall -q src
py -3.13 -m ghost_in_the_sim.batch_cli --output web/data/comparison.json --actual-ai-evidence-trace fixtures/actual-ai-trace-seed42.json
py -3.13 scripts/serve_demo.py
```

最後のserverを起動したら、表示されたURLを内部ブラウザで開き、desktopとmobile相当で開始、主要な分岐、AI主体間の相互作用、最終結果、監査表示を目視する。生成コマンドの正本はREADMEと`RESULTS.md`の「再現」節であり、この文書との差は `tests/test_context_contract.py` が検知する。

## phaseと残務の導出

1. `docs/roadmap.md` の最初の未チェック項目を現在phaseの候補にする。
2. `docs/knowledge/artifacts.md` で対象が `concept`、`contracted`、`implemented`、`measured` のどこにあるか照合する。
3. 変更予定fileを列挙し、`git status --short` の既存WIPと交差するなら並列編集せずHOLDする。
4. 該当する失敗経路テスト、全pytest、設計contract、compile、生成bundle、目視を順に確認する。
5. 残務は `owner / next_action / resume_condition / evidence` を持たせ、`resolved / transferred / rejected` のいずれかまで消さない。

`roadmap.md` と `artifacts.md` が矛盾する、AI創発MVPの受入条件を満たすartifactが台帳にない、生成物とruntime replayが一致しない、または目視未確認なら「完了」ではなくdriftまたは残務として返す。

## 完了receipt

次の担当は終了時に、少なくとも以下を返す。

- candidate SHAと、予定file／実diffの一致
- 実行したtest、contract、compile、bundle生成、目視の結果
- `meta-security-run-bundle/v1`の同一`run_id`とreplay証拠
- 採用した根因修正と、棄却した未信頼review指摘
- Git／remote状態、実施した外部操作
- unknown、人間判断、残務と次のowner

