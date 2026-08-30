# Agent Turn 外部 runner 引き継ぎ契約

## 位置づけ

`ghost-in-the-sim` の既存runtime、シナリオ、4主体、世界状態遷移、`meta-security-run-bundle/v1` が正本です。Google Cloudなどの外部クラウドは、正本を置き換える実行環境ではなく、`ghost-agent-turn/v1` のrequestを受け取りproposalを返すadapter／runnerです。

この境界ではネットワーク通信を行いません。canonical JSONファイルをexportし、外部runnerの出力をingestし、ローカルruntimeでexact replayします。クラウド固有SDKや依存は追加しません。

## Trust boundary

外部proposalは未信頼入力です。次をすべて満たすまで世界状態へ適用しません。

- request束、proposal束、recorded fixtureのfieldがexact schemaと一致する
- 全bundle digestが既存canonical JSON規則で一致する
- `request_bundle_digest`がexportしたrequest束と一致する
- すべてのrequestにproposalがちょうど1件あり、欠落・重複がない
- `AgentProposal.from_dict`がrequest digest、run ref、agent、authority、action、evidence、provenanceを検証する
- seed、mode、scenario、turn、agent順にcross-run混入がない
- recorded proposalだけを使った再実行が`replay-match`になる

requestには公開mandate、部分観測、許可action、digestだけを含めます。secret、API key、raw environment、filesystem path、prompt本文、private memoryを入れてはいけません。`private_goal_digest`は目標本文ではなくdigestです。proposalにもsecretやraw provider responseを入れません。

## 実行コマンド

PowerShellでrepository rootから実行します。

```powershell
$env:PYTHONPATH='src'
python -m ghost_in_the_sim.agent_turn_cli export --seed 42 --mode plural --turn-limit 12 --output artifacts/cloud-handoff/requests.json
```

外部runnerは`requests.json`の各requestに対して、同じ`ghost-agent-turn/v1`の`AgentProposal`を1件だけ作ります。返却ファイルのtop-levelは次のexact schemaです。

```json
{
  "protocol_version": "ghost-agent-turn/v1",
  "kind": "agent_proposal_bundle",
  "request_bundle_digest": "sha256:...",
  "proposals": [],
  "bundle_digest": "sha256:..."
}
```

`bundle_digest`は自身のfieldを除いたtop-level objectのcanonical digestです。proposal内部の`proposal_digest`も同じ規則で計算します。外部runnerから`proposals.json`が戻ったら、strict ingestします。

```powershell
python -m ghost_in_the_sim.agent_turn_cli ingest --requests artifacts/cloud-handoff/requests.json --proposals artifacts/cloud-handoff/proposals.json --output artifacts/cloud-handoff/recorded-fixture.json
python -m ghost_in_the_sim.agent_turn_cli verify --fixture artifacts/cloud-handoff/recorded-fixture.json --output artifacts/cloud-handoff/run-bundle.json
```

最後の出力は既存の`meta-security-run-bundle/v1`です。run request、event stream、replay、evidenceは同じ`run_id`で結ばれ、evidenceが`verification: replay-match`でなければ完了扱いにしません。

## 次の1時間で行う外部実行

1. ローカルでrequest束をexportし、digestと件数（`4主体 x turn_limit`）を記録する。
2. request束だけを外部runnerの入力artifactへ渡す。credentialやローカル環境を同梱しない。
3. runnerは各requestを独立処理し、proposal束だけをartifactとして返す。応答到着順に意味を持たせない。
4. ローカルへ戻してingestする。1件でも欠落、重複、未知field、digest不一致なら全体を拒否する。
5. verifyでrecorded proposalをexact replayし、`meta-security-run-bundle/v1`を生成する。
6. rule providerのbaselineと外部proposal runを、run_idを混ぜずに比較する。

外部APIの直接呼び出し、credential管理、Cloud Build／Cloud Run設定はこのCLIの責務外です。runner側のdeployや課金、auth、公開は別gateとして人間確認を維持します。

## 撤退・fallback

外部runnerが失敗または期限超過した場合、proposalを捏造せずingestを中止します。既存のrule providerによる決定論的baselineと、その`meta-security-run-bundle/v1`は引き続き実行できます。外部provider固有コードをruntimeへ入れていないため、この3ファイルを利用しなければ従来動作へそのまま戻れます。
