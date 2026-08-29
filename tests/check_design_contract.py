"""設計リポジトリの入口・契約文書が欠けないことを検査する。"""

from __future__ import annotations

from hashlib import sha256
from pathlib import Path
import re
from urllib.parse import unquote, urlsplit


CANONICAL_LIFECYCLE_STATES = {
    "concept",
    "accepted-setting",
    "contracted",
    "implemented",
    "measured",
    "publication-reviewed",
}


def _section(document: str, heading: str) -> str:
    marker = f"## {heading}"
    if document.splitlines().count(marker) != 1:
        raise ValueError(f"section must occur exactly once: {heading}")
    body = document.split(marker, 1)[1]
    return body.split("\n## ", 1)[0]


def _table_rows(section: str, header: tuple[str, ...]) -> list[dict[str, str]]:
    lines = section.splitlines()
    expected = "| " + " | ".join(header) + " |"
    if lines.count(expected) != 1:
        raise ValueError(f"table header must occur exactly once: {expected}")
    start = lines.index(expected)
    rows: list[dict[str, str]] = []
    for line in lines[start + 2 :]:
        if not line.startswith("|"):
            break
        cells = tuple(cell.strip() for cell in line.strip().strip("|").split("|"))
        if len(cells) != len(header):
            raise ValueError(f"table row width mismatch: {line}")
        rows.append(dict(zip(header, cells, strict=True)))
    return rows


def _validate_artifact_registry(document: str) -> None:
    rows = _table_rows(document, ("artifact_id", "内容", "正本", "canonical_state", "実装・実測注記"))
    identifiers = [row["artifact_id"] for row in rows]
    if not identifiers or len(identifiers) != len(set(identifiers)):
        raise ValueError("artifact_id must be present and unique")
    invalid = [row for row in rows if row["canonical_state"] not in CANONICAL_LIFECYCLE_STATES]
    if invalid:
        raise ValueError("artifact canonical_state must be exactly one ADR-012 state")


REQUIRED = (
    "README.md",
    "RESULTS.md",
    "docs/architecture/overview.md",
    "docs/architecture/simulation-contract.md",
    "docs/architecture/agent-contract.md",
    "docs/architecture/ai-replica-mvp.md",
    "docs/architecture/operative-contract.md",
    "docs/architecture/evaluation.md",
    "docs/architecture/model.odd.md",
    "docs/research/simulation-terms.md",
    "docs/design/ui-contract.md",
    "docs/knowledge/README.md",
    "docs/knowledge/sources.md",
    "docs/knowledge/decisions.md",
    "docs/knowledge/artifacts.md",
    "docs/knowledge/threads.md",
    "docs/knowledge/open-questions.md",
    "docs/pr-self-review.md",
    "THIRD_PARTY_NOTICES.md",
    "docs/adr/ADR-001-original-agent-model.md",
    "docs/adr/ADR-002-counterfactual-evaluation.md",
    "docs/adr/ADR-003-agent-depth.md",
    "docs/adr/ADR-004-deterministic-core.md",
    "docs/adr/ADR-005-ui-as-lab.md",
    "docs/adr/ADR-006-replayable-experiment-loop.md",
    "docs/adr/ADR-007-source-and-name-boundary.md",
    "docs/adr/ADR-010-elite-operative-perspective.md",
    "docs/adr/ADR-011-named-homage-boundary.md",
    "docs/adr/ADR-012-canon-runtime-expansion.md",
    "docs/world/setting-bible.md",
    "docs/world/characters.md",
    "docs/world/naming-taxonomy.md",
    "docs/world/cases.md",
    "docs/product/repository-goal.md",
    "docs/roadmap.md",
)


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    missing = [relative for relative in REQUIRED if not (root / relative).is_file()]
    if missing:
        raise SystemExit("design-contract: FAIL\n" + "\n".join(missing))

    readme = (root / "README.md").read_text(encoding="utf-8")
    required_links = (
        "docs/architecture/overview.md",
        "docs/architecture/simulation-contract.md",
        "docs/architecture/agent-contract.md",
        "docs/architecture/ai-replica-mvp.md",
        "docs/architecture/operative-contract.md",
        "docs/world/setting-bible.md",
        "docs/design/ui-contract.md",
        "docs/knowledge/decisions.md",
        "docs/product/repository-goal.md",
        "docs/roadmap.md",
    )
    destinations = {
        unquote(urlsplit(match.group(1).strip().strip("<>")).path).lstrip("./")
        for match in re.finditer(r"(?<!!)\[[^\]]+\]\(([^)\s]+)(?:\s+['\"][^'\"]*['\"])?\)", readme)
    }
    absent_links = [link for link in required_links if link not in destinations]
    if absent_links:
        raise SystemExit("design-contract: FAIL\nREADME links missing:\n" + "\n".join(absent_links))
    review_document = (root / "docs/pr-self-review.md").read_text(encoding="utf-8")
    if "generated_by: nexus-ai-2045/nexus_ai scripts/export_pr_self_review.py" not in review_document:
        raise SystemExit("design-contract: FAIL\nPRセルフレビューの生成元が不明です")
    version = re.search(r"\| rules_version \| `([0-9a-f]{16})` \|", review_document)
    if version is None:
        raise SystemExit("design-contract: FAIL\nPRセルフレビューのrules_versionがありません")
    body_start = review_document.find("## R1 ")
    if body_start < 0:
        raise SystemExit("design-contract: FAIL\nPRセルフレビューの本文開始がありません")
    actual_version = sha256(review_document[body_start:].encode("utf-8")).hexdigest()[:16]
    if version.group(1) != actual_version:
        raise SystemExit("design-contract: FAIL\nPRセルフレビューが生成元と一致しません")

    synthesis = (root / "docs/research/local-and-external-synthesis.md").read_text(encoding="utf-8")
    sources = (root / "docs/knowledge/sources.md").read_text(encoding="utf-8")
    required_research_terms = {
        "将来成果物`model.odd.md`": synthesis,
        "prompt版またはハッシュ": synthesis,
        "終了理由・終了ターン": synthesis,
        "感度分析は任意の付録ではなく": synthesis,
        "7d6d248f79d4167a68f1c37dc345e560fd8ef65d": sources,
        "未コミットの作業ツリーは根拠に含めない": sources,
    }
    missing_research_terms = [term for term, document in required_research_terms.items() if term not in document]
    if missing_research_terms:
        raise SystemExit(
            "design-contract: FAIL\n研究統合契約の必須語がありません:\n" + "\n".join(missing_research_terms)
        )
    simulation_contract = (root / "docs/architecture/simulation-contract.md").read_text(encoding="utf-8")
    agent_contract = (root / "docs/architecture/agent-contract.md").read_text(encoding="utf-8")
    evaluation = (root / "docs/architecture/evaluation.md").read_text(encoding="utf-8")
    results = (root / "RESULTS.md").read_text(encoding="utf-8")
    contract_terms = {
        "共通の分析ホライズン": simulation_contract,
        "外生事象用と条件固有判断用の乱数ストリーム": simulation_contract,
        '"state_before_ref"': simulation_contract,
        '"reversibility": "high"': simulation_contract,
        '"action_type": "request_verification"': agent_contract,
        "0.0` 以上 `1.0` 以下": agent_contract,
        "prompt_version_or_hash": evaluation,
        "code_version": evaluation,
        "| `over_disclosure` |": results,
    }
    absent_terms = [term for term, document in contract_terms.items() if term not in document]
    if absent_terms:
        raise SystemExit("design-contract: FAIL\n設計契約の必須語がありません:\n" + "\n".join(absent_terms))

    public_documents = "\n".join(
        (root / relative).read_text(encoding="utf-8")
        for relative in (
            "README.md",
            "THIRD_PARTY_NOTICES.md",
            "PUBLIC_READY.md",
            "docs/knowledge/sources.md",
        )
    )
    forbidden_claims = (
        "Version 1.0",
        "katayama-meta-security-v1",
        "application-0165",
        "poseidon-public-infrastructure-01",
    )
    leaked_claims = [term for term in forbidden_claims if term in public_documents]
    if leaked_claims:
        raise SystemExit("design-contract: FAIL\n未確認または非公開の識別子があります:\n" + "\n".join(leaked_claims))
    required_boundaries = ("正式な版番号", "名称オマージュを明示する非公式")
    missing_boundaries = [term for term in required_boundaries if term not in public_documents]
    if missing_boundaries:
        raise SystemExit("design-contract: FAIL\n公開境界の説明がありません:\n" + "\n".join(missing_boundaries))
    setting = (root / "docs/world/setting-bible.md").read_text(encoding="utf-8")
    operative = (root / "docs/architecture/operative-contract.md").read_text(encoding="utf-8")
    adr_010 = (root / "docs/adr/ADR-010-elite-operative-perspective.md").read_text(encoding="utf-8")
    adr_011 = (root / "docs/adr/ADR-011-named-homage-boundary.md").read_text(encoding="utf-8")
    decisions = (root / "docs/knowledge/decisions.md").read_text(encoding="utf-8")
    characters = (root / "docs/world/characters.md").read_text(encoding="utf-8")
    setting_terms = {
        "ほぼ何でもできる。それでも、何をするべきかは決まらない。": setting,
        "境界事象調整局": setting,
        "接界機動班": setting,
        "御影冴": setting,
        "ポセイドン": setting,
        "主人公を弱くして難易度を作らない": operative,
        "provider-neutral": operative,
        "capability_failure": operative,
    }
    missing_setting_terms = [term for term, document in setting_terms.items() if term not in document]
    if missing_setting_terms:
        raise SystemExit("design-contract: FAIL\n設定正本の必須語がありません:\n" + "\n".join(missing_setting_terms))
    try:
        identity_rows = _table_rows(_section(setting, "Canonical identity"), ("field", "value"))
        identity = {row["field"]: row["value"] for row in identity_rows}
        expected_identity = {
            "city": "ポセイドン",
            "organization": "境界事象調整局",
            "unit": "接界機動班",
            "protagonist": "御影冴",
        }
        if len(identity_rows) != len(identity) or identity != expected_identity:
            raise ValueError("Canonical identity must contain each expected field exactly once")
        canonical_contracts = (
            (adr_010, "- 状態: 一部をADR-011で置換"),
            (adr_011, "舞台名を海洋複合都市圏 **ポセイドン**、主人公を **御影冴**、実働班を **接界機動班**"),
            (operative, "| 組織 | 境界事象調整局・接界機動班 |"),
            (decisions, "| ADR-011 | ポセイドン／御影冴と名称オマージュ境界を採用する | accepted |"),
        )
        if any(document.count(contract) != 1 for document, contract in canonical_contracts):
            raise ValueError("Canonical identity contracts must occur exactly once")
        canonical_surfaces = "\n".join((readme, setting, operative, adr_010, adr_011, decisions, characters))
        if "臨界対応班" in canonical_surfaces:
            raise ValueError("superseded unit name remains on a canonical surface")
        _validate_artifact_registry((root / "docs/knowledge/artifacts.md").read_text(encoding="utf-8"))
    except ValueError as error:
        raise SystemExit(f"design-contract: FAIL\nCanonical contract error: {error}") from error
    roadmap = (root / "docs/roadmap.md").read_text(encoding="utf-8")
    results_document = (root / "RESULTS.md").read_text(encoding="utf-8")
    completion_terms = {
        "ai-replica-mvp.md#今日の受入条件": roadmap,
        "失敗runと反証判定を機械可読なresult cardへ出力": roadmap,
        "| ADR-006 | scenario / experiment / run manifest / result cardを分離する | accepted |": decisions,
        "{17, 42, 99}": results_document,
        "## 複数seed感度": results_document,
        "## 失敗run・反証判定": results_document,
        "## actual AI replay証拠": results_document,
        "llm_generated_in_codex_session": results_document,
    }
    missing_completion_terms = [term for term, document in completion_terms.items() if term not in document]
    if missing_completion_terms:
        raise SystemExit("design-contract: FAIL\nMVP完了証拠が正本間で一致しません:\n" + "\n".join(missing_completion_terms))
    if "pending-current-tree" in results_document:
        raise SystemExit("design-contract: FAIL\nRESULTSの実行commitが未確定です")
    print("design-contract: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
