# 情報源と優先順位

| 優先 | source_id | 種別 | 用途 | 状態 |
|---:|---|---|---|---|
| 1 | automata-hackathon-vol2 | [公式サイト](https://hackathon.automata-lab.jp/) | 提出要件・テーマの一次確認 | verified-2026-08-24 |
| 2 | katayama-meta-security-v1 | 公式サイトから参照される構想ペーパー Version 1.0 | メタ安全保障の概念原典 | link-only |
| 3 | nexus-design | このrepoのADR・設計文書 | 実装上の仮説 | proposed |
| 4 | creative-inspiration | 創作作品から得た抽象的な着想 | 複数性・ネットワーク化の発想 | non-reproducible |
| 5 | internal-meta-security-ssot | `nexus-ai-2045/meta-security-sim` の内部知識索引・契約 | 因果連鎖、比較、反証の抽象のみ | internal-link-only |
| 6 | odd-protocol-2020 | [ODD Protocol](https://www.jasss.org/23/2/7.html) | モデル記述と再現可能性の確認枠 | verified-2026-08-24 |
| 7 | netlogo-behaviorspace | [NetLogo BehaviorSpace](https://docs.netlogo.org/behaviorspace) | parameter sweep、seed、反復実行の先例 | verified-2026-08-24 |
| 8 | mesa-framework | [Mesa](https://github.com/mesa/mesa) / [Docs](https://mesa.readthedocs.io/stable/overview.html) | Python ABM、batch run、将来の可視化候補 | verified-2026-08-24 |
| 9 | nist-ai-rmf | [NIST AI RMF](https://doi.org/10.6028/NIST.AI.100-1) | 利益・損失・人間監督を分けるリスク確認枠 | verified-2026-08-24 |

`creative-inspiration` は、固有名詞、本文、画像、台詞、設定の再利用を許可しない。設計上の主張は必ず、このrepo固有の言葉と比較可能な契約へ翻訳する。

`internal-meta-security-ssot` はPRIVATEな別SSOTであり、このrepoへ本文・非公開資料・ローカルパスを複製しない。参照するのは抽象化した設計原則だけである。外部資料もコード・データ・結果を転載せず、採用時にライセンスと版を再確認する。
