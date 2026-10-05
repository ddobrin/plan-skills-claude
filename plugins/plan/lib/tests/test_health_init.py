import json
import os

import health
import swarm_init
import swarmgit as sg
from conftest import git


def test_status_reports_off_without_heartbeat_and_active_with_one(repo):
    info, active = health.status(str(repo))
    assert not active and info["enforcement"] == "OFF" and info["git_hook"].startswith("missing")
    sg.touch_heartbeat(sg.store_dir(str(repo)))
    info, active = health.status(str(repo))
    assert active and info["mode"] == "pr" and info["max_engineers"] == 5


def test_status_outside_swarm_repo(repo):
    os.remove(repo / "plans" / "swarm.md")
    info, active = health.status(str(repo))
    assert not active and "swarm-init" in info["message"]


def test_session_start_message_and_invalid_config(repo):
    msg = health.session_start({"cwd": str(repo), "session_id": "s1", "source": "startup"})
    assert "enforcement active" in msg and "Git hooks missing" in msg
    (repo / "plans" / "swarm.md").write_text("broken")
    assert "Gated operations are refused" in health.session_start({"cwd": str(repo)})


def test_swarm_init_installs_without_overwriting(repo):
    os.remove(repo / "plans" / "swarm.md")
    dry = swarm_init.install(str(repo), dry_run=True)
    assert ("swarm", "would install", os.path.join("plans", "swarm.md")) in dry
    res = dict((n, s) for n, s, _ in swarm_init.install(str(repo)))
    assert res["swarm"] == "installed"
    assert all(res[f"hook:{h}"] == "installed" for h in health.HOOK_NAMES)
    assert all(health.git_hook_installed(str(repo), h) for h in health.HOOK_NAMES)
    assert os.path.exists(os.path.join(sg.store_dir(str(repo)), "bin", "gate.py"))
    assert sg.is_active(sg.store_dir(str(repo)))
    again = dict((n, s) for n, s, _ in swarm_init.install(str(repo)))
    assert again["swarm"] == "exists" and again["hook:pre-push"] == "exists"


def test_swarm_init_installs_agents_md_only_without_project_instructions(repo):
    res = {n: (s, d) for n, s, d in swarm_init.install(str(repo), only={"agents"})}
    assert res["agents"] == ("installed", "AGENTS.md")
    assert (repo / "AGENTS.md").read_text().startswith("# AGENTS.md")
    assert not (repo / "CLAUDE.md").exists()
    # "claude" is still accepted as the old name of the item
    assert swarm_init.install(str(repo), only={"claude"})[0][:2] == ("agents", "exists")


def test_swarm_init_keeps_an_existing_claude_md(repo):
    (repo / "CLAUDE.md").write_text("# CLAUDE.md\n")
    name, state, detail = swarm_init.install(str(repo), only={"agents"})[0]
    assert (name, state) == ("agents", "exists") and detail.startswith("CLAUDE.md")
    assert not (repo / "AGENTS.md").exists()  # Claude Code would ignore it next to CLAUDE.md


def test_swarm_init_flags_claude_md_that_hides_agents_md(repo):
    (repo / "AGENTS.md").write_text("# AGENTS.md\n")
    (repo / "CLAUDE.md").write_text("# CLAUDE.md\n")
    state, detail = swarm_init.install(str(repo), only={"agents"})[0][1:]
    assert state == "exists" and "@AGENTS.md" in detail
    (repo / "CLAUDE.md").write_text("@AGENTS.md\n")
    assert swarm_init.install(str(repo), only={"agents"})[0][1:] == ("exists", "AGENTS.md")


def test_swarm_init_reports_foreign_hook(repo):
    hook = health.hook_path(str(repo))
    os.makedirs(os.path.dirname(hook), exist_ok=True)
    with open(hook, "w") as fh:
        fh.write("#!/bin/sh\nnpx lint-staged\n")
    res = {n: (s, d) for n, s, d in swarm_init.install(str(repo), only={"hook"})}
    assert res["hook:pre-commit"][0] == "exists" and "--git-hook" in res["hook:pre-commit"][1]
    assert res["hook:pre-push"][0] == "installed"


def test_installed_git_hook_blocks_unapproved_commit_end_to_end(repo):
    swarm_init.install(str(repo), only={"hook"})
    git(repo, "checkout", "-q", "-b", "swarm/auth-mvp")
    (repo / "x.py").write_text("x\n")
    git(repo, "add", "x.py")
    import subprocess
    proc = subprocess.run(["git", "commit", "-m", "sneaky"], cwd=repo, capture_output=True, text=True)
    assert proc.returncode != 0 and "need an approval phrase" in proc.stderr


def ledger_check_script():
    import re
    from conftest import PLUGIN
    text = open(os.path.join(PLUGIN, "templates", "ci", "plan-swarm.yml")).read()
    body = re.search(r"python3 - <<'PY'\n(.*?)\n\s*PY\n", text, re.S).group(1)
    return "\n".join(line[10:] if line.startswith(" " * 10) else line for line in body.splitlines())


def test_ci_ledger_check_matches_commits_to_approvals(repo, tmp_path, monkeypatch):
    import subprocess
    import approve
    import gate
    base = git(repo, "rev-parse", "HEAD")
    git(repo, "checkout", "-q", "-b", "swarm/auth-mvp")
    d = repo / "plans" / "active_milestones" / "auth-mvp"
    d.mkdir(parents=True)
    (d / "spec.md").write_text("# Spec\n")
    approve.record(approve.parse("approve plan auth-mvp tier=elevated"), str(repo))
    git(repo, "add", "-A")
    gate.pre_tool_use({"cwd": str(repo), "tool_name": "Bash", "tool_input": {"command": "git commit -m plan"}})
    git(repo, "commit", "-q", "-m", "plan")  # hook not installed here; the gate allowed it above
    out = tmp_path / "gh_out"
    env = dict(os.environ, BASE=base, MILESTONE="swarm/auth-mvp", GITHUB_OUTPUT=str(out))
    script = ledger_check_script()
    ok = subprocess.run(["python3", "-c", script], cwd=repo, env=env, capture_output=True, text=True)
    assert ok.returncode == 0, ok.stdout + ok.stderr
    assert "tier=elevated" in out.read_text()
    approve.record(approve.parse("approve pr auth-mvp"), str(repo))
    gate.pre_tool_use({"cwd": str(repo), "tool_name": "Bash", "tool_input": {"command":
                       "git commit -m rec -- plans/active_milestones/auth-mvp/approvals.md"}})
    git(repo, "commit", "-q", "-m", "rec", "--", "plans/active_milestones/auth-mvp/approvals.md")
    rec_ok = subprocess.run(["python3", "-c", script], cwd=repo, env=env, capture_output=True, text=True)
    assert rec_ok.returncode == 0, rec_ok.stdout + rec_ok.stderr   # the ledger-only PR record is accepted
    (repo / "sneaky.py").write_text("x\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "--no-verify", "-m", "unapproved")
    bad = subprocess.run(["python3", "-c", script], cwd=repo, env=env, capture_output=True, text=True)
    assert bad.returncode == 1 and "unapproved" in bad.stdout
