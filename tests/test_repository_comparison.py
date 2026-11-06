"""Execute the actual Ubuntu workflow steps against synthetic Git histories."""

from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import textwrap

import pytest


ROOT = Path(__file__).resolve().parents[1]
pytestmark = pytest.mark.skipif(os.name == "nt", reason="Auxiliary workflows run on Ubuntu bash")


def environment():
    result = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    result["GIT_CONFIG_NOSYSTEM"] = "1"
    result["GIT_CONFIG_GLOBAL"] = "/dev/null"
    return result


def git(repo, *args):
    return subprocess.check_output(
        ["git", "-C", str(repo), *args], env=environment(), text=True
    ).strip()


def commit(repo, name):
    (repo / name).write_text(name + "\n", encoding="utf-8")
    git(repo, "add", name)
    git(repo, "commit", "-qm", name)
    return git(repo, "rev-parse", "HEAD")


def step(filename, name):
    text = (ROOT / ".github/workflows" / filename).read_text(encoding="utf-8")
    marker = "      - name: " + name + "\n"
    assert text.count(marker) == 1
    block = text.split(marker, 1)[1].split("\n      - ", 1)[0]
    return textwrap.dedent(block.split("        run: |\n", 1)[1])


@pytest.fixture
def workspace(tmp_path):
    repo = tmp_path / "candidate"
    repo.mkdir()
    git(repo, "init", "-q", "-b", "main")
    git(repo, "config", "user.name", "Fixture Bot")
    git(repo, "config", "user.email", "fixture@example.invalid")
    fork = commit(repo, "root.txt")
    bindir = tmp_path / "bin"
    bindir.mkdir()
    recorder = bindir / "python"
    recorder.write_text(
        "#!/usr/bin/env python3\n"
        "import json, os, sys\n"
        "with open(os.environ['CAPTURE_ARGS'], 'a', encoding='utf-8') as output:\n"
        "    output.write(json.dumps(sys.argv[1:]) + '\\n')\n",
        encoding="utf-8",
    )
    recorder.chmod(0o755)
    return repo, fork, bindir


def execute(workspace, kind, base, expected_head=None):
    repo, _, bindir = workspace
    capture = repo.parent / "arguments.jsonl"
    env = environment()
    env.update(
        EXPECTED_HEAD=expected_head or git(repo, "rev-parse", "HEAD"),
        BASE_SHA=base,
        GITHUB_WORKSPACE=str(repo.parent),
        RUNNER_TEMP=str(repo.parent / "runner"),
        CAPTURE_ARGS=str(capture),
        PATH=str(bindir) + os.pathsep + os.environ["PATH"],
    )
    if kind == "candidate":
        filename = "repository-contract.yml"
        names = ["Bind the pull request comparison", "Check repository preflight",
                 "Check declared repository consistency"]
    else:
        filename = "repository-contract-trusted.yml"
        names = ["取得したheadを照合", "信頼済み検査器で候補のrepo契約を確認"]
    for name in names:
        result = subprocess.run(
            [shutil.which("bash"), "-c", step(filename, name)],
            cwd=repo, env=env, capture_output=True, text=True,
        )
        if result.returncode:
            return result, []
    arguments = [json.loads(line) for line in capture.read_text().splitlines()]
    return result, arguments


@pytest.mark.parametrize("kind", ["candidate", "trusted"])
@pytest.mark.parametrize("history", ["linear", "main_advanced", "merged_main"])
def test_workflow_keeps_current_baseline_and_uses_branch_comparison(workspace, kind, history):
    repo, fork, _ = workspace
    git(repo, "switch", "-qc", "topic")
    commit(repo, "topic.txt")
    base = fork
    if history != "linear":
        git(repo, "switch", "-q", "main")
        base = commit(repo, "main.txt")
        git(repo, "switch", "-q", "topic")
        if history == "merged_main":
            git(repo, "merge", "-q", "--no-edit", "main")
    comparison = git(repo, "merge-base", base, "HEAD")
    prefix = "contract" if kind == "candidate" else "trusted"
    base_ref = "refs/remotes/origin/" + prefix + "-base"
    comparison_ref = "refs/remotes/origin/" + prefix + "-comparison"
    git(repo, "update-ref", base_ref, base)
    git(repo, "symbolic-ref", "refs/remotes/origin/HEAD", base_ref)
    git(repo, "update-ref", "refs/remotes/origin/unrelated", fork)

    result, arguments = execute(workspace, kind, base)
    assert result.returncode == 0, result.stderr
    assert git(repo, "rev-parse", base_ref) == base
    assert git(repo, "rev-parse", comparison_ref) == comparison
    assert git(repo, "for-each-ref", "--sort=refname", "--format=%(refname)").splitlines() == [
        base_ref, comparison_ref,
    ]
    ratchet = next(args for args in arguments if args[0].endswith("/preflight_ratchet.py"))
    assert ratchet[ratchet.index("--baseline-base-ref") + 1] == base_ref
    assert ratchet[ratchet.index("--consistency-base-ref") + 1] == comparison_ref
    consistency = next(args for args in arguments if args[0].endswith("/consistency_gate.py"))
    assert consistency[consistency.index("--base-ref") + 1] == comparison_ref
    if history == "main_advanced":
        assert base != comparison


@pytest.mark.parametrize("kind", ["candidate", "trusted"])
@pytest.mark.parametrize("invalid", ["wrong_head", "missing_base", "unrelated_history"])
def test_workflow_stops_before_tools_when_comparison_is_invalid(workspace, kind, invalid):
    repo, fork, _ = workspace
    git(repo, "switch", "-qc", "topic")
    head = commit(repo, "topic.txt")
    base = fork
    if invalid == "missing_base":
        base = "0" * 40
    if invalid == "unrelated_history":
        git(repo, "switch", "-q", "--orphan", "unrelated")
        base = commit(repo, "other.txt")
        git(repo, "switch", "-q", "topic")
    result, arguments = execute(
        workspace, kind, base, expected_head=fork if invalid == "wrong_head" else head,
    )
    assert result.returncode != 0
    assert not arguments
    assert not (repo.parent / "arguments.jsonl").exists()
