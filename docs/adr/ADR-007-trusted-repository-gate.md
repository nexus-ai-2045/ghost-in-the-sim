# ADR-007: PR候補と独立したbase側リポジトリゲート

- Status: accepted
- Date: 2026-08-24

## Context

`pull_request`で候補headのworkflowを実行するだけでは、同じPRがworkflow、検査器、設定を同時に弱められる。候補側検査は素早いフィードバックには使えるが、信頼境界にはならない。

一方、`pull_request_target`で候補のコードやスクリプトを実行すると、未信頼入力をbase権限で実行する危険がある。また、このworkflowがbaseへまだ存在しない初回導入では、自動検査だけで導入自身を承認できない。

## Decision

1. 候補側`repository-contract.yml`は補助検査として残す。
2. `repository-contract-trusted.yml`はread-only権限でbaseと候補を別ディレクトリへ取得し、候補コードを実行しない。
3. verifier、両workflow、consistency設定はbaseとbyte単位で一致する場合だけ通常PRとして受け入れる。変更は別のbootstrap PRとして人間レビューする。
4. repo-preflightとai-ratchet-gateはbase側workflowに固定したrevision・digestから実行し、候補treeをデータとして検査する。
   repo-preflightの差分基準には生SHAを直接渡さず、照合済みbase SHAを候補clone内の専用remote-tracking refへ固定して渡す。
5. trusted runは**advisory**であり、required check、merge許可、公開承認を意味しない。

## Consequences

- このADRを含む初回導入は、base側workflowがまだないため人間レビューが必須になる。
- 導入後の通常PRは、自身のゲートを置換して通過できない。
- ゲート更新は意図的に別PRへ分離されるため手間は増えるが、検査対象と検査器の自己承認を防げる。
