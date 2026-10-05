import json
import os

import pytest

import approve
import swarmgit as sg
from conftest import git


def milestone(repo, m, files=None):
    d = repo / "plans" / "active_milestones" / m
    d.mkdir(parents=True, exist_ok=True)
    for name, text in (files or {}).items():
        (d / name).write_text(text)
    return d


@pytest.mark.parametrize("prompt, expected", [
    ("approve intent login-limit as login-rate-limit", {"kind": "intent", "slug": "login-limit", "moniker": "login-rate-limit"}),
    ("  Approve   SPEC   auth-mvp ", {"kind": "spec", "moniker": "auth-mvp"}),
    ("approve plan auth-mvp", {"kind": "plan", "moniker": "auth-mvp", "tier": ""}),
    ("approve plan auth-mvp tier=Critical", {"kind": "plan", "moniker": "auth-mvp", "tier": "critical"}),
    ("approve commit auth-mvp g12", {"kind": "commit", "moniker": "auth-mvp", "group": 12}),
    ("approve pr auth-mvp", {"kind": "pr", "moniker": "auth-mvp"}),
    ("approve release v1.4.0", {"kind": "release", "version": "v1.4.0"}),
    ("approve release 2.0.0-rc.1", {"kind": "release", "version": "2.0.0-rc.1"}),
])
def test_parse_accepts_exact_phrases(prompt, expected):
    assert approve.parse(prompt) == expected


@pytest.mark.parametrize("prompt", [
    "yes", "approve", "looks good, approve plan auth-mvp", "approve plan auth-mvp please",
    "approve commit auth-mvp", "approve plan auth-mvp tier=extreme", "approve pr ../etc",
])
def test_parse_rejects_anything_else(prompt):
    assert approve.parse(prompt) is None


def test_record_mints_nonce_and_writes_ledger(repo):
    milestone(repo, "auth-mvp", {"plan.md": "# Plan\n**Risk tier (proposed):** `elevated`\n"})
    msg = approve.record(approve.parse("approve plan auth-mvp"), str(repo))
    assert "approval recorded for plan auth-mvp" in msg and "Tier: elevated" in msg
    rows = sg.read_ledger(str(repo), "auth-mvp")
    assert len(rows) == 1 and rows[0]["kind"] == "plan" and rows[0]["tier"] == "elevated"
    assert rows[0]["who"] == "dev@example.com" and rows[0]["mode"] == "pr"
    nonces = sg.valid_nonces(sg.store_dir(str(repo)), sg.head(str(repo)), ["plan"])
    assert len(nonces) == 1 and nonces[0]["id"] == rows[0]["nonce"]


def test_explicit_tier_overrides_proposal_and_commit_inherits_it(repo):
    milestone(repo, "auth-mvp", {"plan.md": "Risk tier (proposed): critical\n"})
    approve.record(approve.parse("approve plan auth-mvp tier=elevated"), str(repo))
    approve.record(approve.parse("approve commit auth-mvp g1"), str(repo))
    rows = sg.read_ledger(str(repo), "auth-mvp")
    assert [r["tier"] for r in rows] == ["elevated", "elevated"]
    assert rows[1]["group"] == "1"


def test_missing_milestone_or_intent_is_not_recorded(repo):
    assert "NOT recorded" in approve.record(approve.parse("approve spec ghost"), str(repo))
    assert "NOT recorded" in approve.record(approve.parse("approve intent nope as ghost"), str(repo))


def test_intent_approval_needs_inbox_file(repo):
    (repo / "plans" / "intents").mkdir()
    (repo / "plans" / "intents" / "2026-09-24-login-limit.md").write_text("# Intent\n")
    msg = approve.record(approve.parse("approve intent login-limit as login-rate-limit"), str(repo))
    assert "approval recorded for intent login-rate-limit" in msg
    assert (repo / "plans" / "active_milestones" / "login-rate-limit" / "approvals.md").exists()


def test_release_goes_to_root_ledger(repo):
    approve.record(approve.parse("approve release v1.0.0"), str(repo))
    rows = sg.read_ledger(str(repo))
    assert rows[0]["kind"] == "release" and rows[0]["milestone"] == "v1.0.0"


def test_invalid_config_is_reported(repo, monkeypatch, capsys):
    milestone(repo, "auth-mvp")
    (repo / "plans" / "swarm.md").write_text("no block here")
    monkeypatch.setattr("sys.stdin", __import__("io").StringIO(json.dumps({"prompt": "approve spec auth-mvp", "cwd": str(repo)})))
    approve.main()
    out = json.loads(capsys.readouterr().out)
    assert "NOT recorded" in out["hookSpecificOutput"]["additionalContext"]


def test_main_passes_other_prompts_through(repo, monkeypatch, capsys):
    monkeypatch.setattr("sys.stdin", __import__("io").StringIO(json.dumps({"prompt": "hello", "cwd": str(repo)})))
    assert approve.main() == 0
    assert capsys.readouterr().out == ""
    assert sg.heartbeat(sg.store_dir(str(repo)))["last_prompt"]
