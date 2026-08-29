from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_cloud_review_root_cause_contract_is_discoverable() -> None:
    contract = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    for marker in (
        "docs/pr-self-review.md",
        "一つの根因 group",
        "同一HEADに一回",
        "最大三サイクル",
        "BLOCKED_ROOT_CAUSE",
        "candidate SHA",
        "unresolved thread",
    ):
        assert marker in contract
