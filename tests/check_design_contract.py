"""設計リポジトリの入口・契約文書が欠けないことを検査する。"""

from __future__ import annotations

from hashlib import sha256
from pathlib import Path
import re


REQUIRED = (
    "README.md",
    "RESULTS.md",
    "docs/architecture/overview.md",
    "docs/architecture/simulation-contract.md",
    "docs/architecture/agent-contract.md",
    "docs/architecture/evaluation.md",
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
        "docs/design/ui-contract.md",
    )
    absent_links = [link for link in required_links if link not in readme]
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
    print("design-contract: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
