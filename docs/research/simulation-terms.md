# シミュレーション設計の用語と採用範囲

このプロジェクトの最小実装は、未来を当てる予測器ではなく、仮定を変えたときに何が変わるかを再実行・検討できる**仮説実験器**である。

| 用語 | このMVPでの意味 | 採用範囲 |
|---|---|---|
| Agent-based model (ABM) | 状態と相互作用を持つ複数主体を時間順に進めるモデル | 架空の6主体と抽象状態だけを扱う |
| ODD | 目的、主体・状態・尺度、プロセス、初期化、入力、下位モデルを分けて記述する方式 | `model.odd.md` で最小記述を固定 |
| Counterfactual comparison | 初期条件をそろえ、条件だけ変えた差を見る比較 | `condition` 以外を固定する |
| Common random numbers (CRN) | 比較対象へ同じ乱数列を与え、差分のばらつきを抑える実験設計 | 同じ `seed` で比較する。優劣の保証ではない |
| Event sourcing | 状態の最終値だけでなく、状態遷移イベントを時系列で残すこと | `events.jsonl` を監査・再読用に出力 |
| Falsification / sensitivity | 仮定を変えると結論が崩れるかを確かめること | seed・条件・将来のパラメータ掃引で扱う |

## 既存手法から借りるもの

- Grimm et al. の [ODD protocol](https://www.jasss.org/23/2/7.html) から、再実装に必要なモデル記述の粒度を借りる。
- NetLogo の [BehaviorSpace](https://docs.netlogo.org/behaviorspace) から、seed・モデル版・実験条件・出力を一組で残す実験運用を借りる。
- Wright and Ramsay の [Common Random Numbers](https://doi.org/10.1287/mnsc.25.7.649) から、同一乱数で比較する発想を借りる。ただし、CRNが常に比較精度を改善するとは仮定しない。
- CoMSES Net の [FAQ](https://www.comses.net/about/faq/) が推奨する、説明・メタデータ・再実行手順の分離を将来のポータブル化の目安にする。

## 採用しないもの

- 現実の組織、人物、事件、脆弱性、攻撃手順をモデルの変数や行動として扱わない。
- 一回の出力を真実・予測・政策提言として扱わない。
- 物語作品の固有名詞・台詞・画像・設定をシナリオ本体へ持ち込まない。
