# 公開前チェック

<!-- repo-preflight:review-record -->

このリポジトリを公開・共有・提出する前に、次を確認する。

## 内容

- [ ] READMEの目的、できること、限界が現在の実装と一致する。
- [ ] 状態・主体造形・シナリオ・アセットは新規作成され、名称オマージュはADR-011の帰属・禁止境界に従っている。
- [ ] 片山氏のコンセプトペーパーは本文転載せず、版と公開URLを確認した。
- [ ] 公式情報は [公式サイト](https://hackathon.automata-lab.jp/) と再照合した。
- [ ] 創作作品の画像、台詞、OCR、アーカイブ、固有の再現素材がない。

## 安全

- [ ] secret scan と personal path scan が通過した。
- [ ] `ai-ratchet-gate` が通過した。
- [ ] 実運用の攻撃・監視・標的化を助長する内容がない。

## GitHub

- [ ] README、LICENSE、SECURITY.md、CONTRIBUTING.md を人間が読んだ。
- [ ] commit履歴とGitHub上のファイル一覧を人間が確認した。
- [ ] 何がWeb全体に見えるかを確認した。
- [ ] 可視性変更は、対象repoと操作を明示して人間承認した。

## ローカルでの名義検査

許可名義は `.repo-preflight/public-identities.json`、非公開型検査の許可設定は
`.repo-preflight/identity-policy.json` に置く。公開用 noreply 名義と依存更新 bot だけを許可する。
共同作者行は許可しない。ローカルフックも同じ名簿を指定する。

```sh
export REPO_PREFLIGHT_HOME=/path/to/repo-preflight
export PREFLIGHT_PRIVATE_PATTERNS_FILE="$PWD/.repo-preflight/identity-policy.json"
export PATH="/path/to/gitleaks-bin:$PATH"
python3 "$REPO_PREFLIGHT_HOME/scripts/readiness_scan.py" --repo . \
  --allowed-identities .repo-preflight/public-identities.json
```
