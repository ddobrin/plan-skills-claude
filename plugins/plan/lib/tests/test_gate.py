import json
import os

import pytest

import approve
import gate
import swarmgit as sg
from conftest import git


def bash(repo, command):
    gate.pre_tool_use({"cwd": str(repo), "tool_name": "Bash", "tool_input": {"command": command}})


def denied(repo, command, match=None):
    with pytest.raises(gate.Deny, match=match):
        bash(repo, command)


def ok(phrase, repo):
    msg = approve.record(approve.parse(phrase), str(repo))
    assert "approval recorded" in msg, msg


def setup_milestone(repo, m="auth-mvp", branch=True):
    if branch:
        git(repo, "checkout", "-q", "-b", f"swarm/{m}")
    d = repo / "plans" / "active_milestones" / m
    d.mkdir(parents=True, exist_ok=True)
    (d / "spec.md").write_text("# Spec\n")
    return d


def code_change(repo, name="src.py"):
    (repo / name).write_text("print('x')\n")
    git(repo, "add", name)


# --- scope -------------------------------------------------------------------

def test_inactive_without_swarm_md(repo):
    os.remove(repo / "plans" / "swarm.md")
    code_change(repo)
    bash(repo, "git commit -m x")  # no exception


def test_invalid_swarm_md_refuses_gated_git_but_not_other_commands(repo):
    (repo / "plans" / "swarm.md").write_text("```json swarm-config\n{\"version\": 9}\n```\n")
    denied(repo, "git commit -m x", "swarm.md is invalid")
    bash(repo, "ls -la")


# --- commits -------------------------------------------------------------------

def test_code_commit_needs_commit_nonce(repo):
    setup_milestone(repo)
    code_change(repo)
    denied(repo, "git commit -m x", "approve commit auth-mvp g<n>")
    ok("approve commit auth-mvp g1", repo)
    bash(repo, "git commit -m x")
    assert sg.take_ticket(sg.store_dir(str(repo)), sg.head(str(repo)))
    denied(repo, "git commit -m again", "already used")


def test_plans_only_commit_accepts_spec_nonce_for_that_milestone(repo):
    d = setup_milestone(repo)
    ok("approve spec auth-mvp", repo)
    git(repo, "add", "plans")
    bash(repo, "git commit -m 'docs(auth-mvp): spec'")


def test_spec_nonce_does_not_cover_code(repo):
    setup_milestone(repo)
    ok("approve spec auth-mvp", repo)
    code_change(repo)
    denied(repo, "git commit -m x", "no valid approval")


def test_stale_head_is_rejected(repo):
    setup_milestone(repo)
    ok("approve commit auth-mvp g1", repo)
    (repo / "other.txt").write_text("x")
    git(repo, "add", "other.txt")
    git(repo, "commit", "-q", "--no-verify", "-m", "someone else")
    code_change(repo)
    denied(repo, "git commit -m x", "stale")


def test_pr_mode_requires_milestone_branch(repo):
    setup_milestone(repo, branch=False)
    ok("approve commit auth-mvp g1", repo)
    code_change(repo)
    denied(repo, "git commit -m x", "swarm/<milestone>")


def test_local_mode_commits_on_current_branch(repo):
    text = (repo / "plans" / "swarm.md").read_text().replace('"mode": "pr"', '"mode": "local"')
    (repo / "plans" / "swarm.md").write_text(text)
    setup_milestone(repo, branch=False)
    ok("approve commit auth-mvp g1", repo)
    code_change(repo)
    bash(repo, "git commit -m x")


@pytest.mark.parametrize("cmd, match", [
    ("git commit --no-verify -m x", "skip hooks"),
    ("git commit -nm x", "skip hooks"),
    ("git commit --amend -m x", "amend"),
])
def test_commit_bypasses_are_denied(repo, cmd, match):
    setup_milestone(repo)
    ok("approve commit auth-mvp g1", repo)
    code_change(repo)
    denied(repo, cmd, match)


def test_message_text_is_not_parsed_as_flags(repo):
    setup_milestone(repo)
    ok("approve commit auth-mvp g1", repo)
    code_change(repo)
    bash(repo, 'git commit -m "-n is not a flag here; approvals.md -> tracked"')


def test_add_in_same_command_counts_unstaged_changes(repo):
    setup_milestone(repo)
    ok("approve spec auth-mvp", repo)
    (repo / "src.py").write_text("x\n")  # unstaged code change
    denied(repo, "git add -A\ngit commit -m x", "no valid approval")


def test_wip_commits_only_inside_a_swarm_worktree(repo):
    import worktree
    setup_milestone(repo)
    wt = worktree.create(str(repo), "auth-mvp", "1.A")["path"]
    open(os.path.join(wt, "a.py"), "w").write("a\n")
    bash(repo, f"cd {wt} && git add -A && git commit -m wip")
    d = os.path.join(wt, "plans", "active_milestones", "auth-mvp")
    os.makedirs(d, exist_ok=True)
    open(os.path.join(d, "approvals.md"), "w").write("forged\n")
    git(wt, "add", "-A")
    denied(repo, f"cd {wt} && git commit -m wip2", "approvals.md")
    # the same branch name in the main checkout gets no WIP exemption
    git(repo, "checkout", "-q", "-b", "swarm-wip/auth-mvp/x")
    code_change(repo, "b.py")
    denied(repo, "git commit -m unapproved", "no valid approval")


# --- push, tag, history ---------------------------------------------------------

def test_push_rules(repo):
    setup_milestone(repo)
    denied(repo, "git push origin main", "never pushes main")
    denied(repo, "git push --force origin swarm/auth-mvp", "force")
    denied(repo, "git push origin +swarm/auth-mvp", "force")
    denied(repo, "git push origin swarm-wip/auth-mvp/1.A", "never pushed")
    denied(repo, "git push origin feature/x", "pushed by people")
    denied(repo, "git push origin", "name the remote and the ref")
    denied(repo, "git push -u origin swarm/auth-mvp", "approve pr auth-mvp")
    ok("approve pr auth-mvp", repo)
    bash(repo, "git push -u origin swarm/auth-mvp")
    assert not sg.valid_nonces(sg.store_dir(str(repo)), sg.head(str(repo)), ["pr"])


def test_tag_rules(repo):
    bash(repo, "git tag")
    bash(repo, "git tag -l 'v*'")
    denied(repo, "git tag -a v1.0.0 -m 'Release v1.0.0'", "approve release v1.0.0")
    denied(repo, "git push --tags", "push a release tag explicitly")
    ok("approve release v1.0.0", repo)
    bash(repo, "git tag -a v1.0.0 -m 'Release v1.0.0'")
    git(repo, "tag", "-a", "v1.0.0", "-m", "Release v1.0.0")
    bash(repo, "git push origin v1.0.0")
    denied(repo, "git push --follow-tags origin main", "push a release tag explicitly")
    denied(repo, "git tag -d v1.0.0", "deleting")


@pytest.mark.parametrize("cmd, match", [
    ("git merge feature", "merge --squash"),
    ("git rebase main", "rewrites history"),
    ("git reset --hard HEAD~1", "rewrites approved history"),
    ("git reset --soft HEAD", "rewrites approved history"),
    ("git branch -D swarm/auth-mvp", "evidence"),
    ("git -c core.hooksPath=/dev/null commit -m x", "-c setting"),
    ("git config core.hooksPath /tmp", "hooks"),
    ("git -C ../other commit -m x", "-C"),
    ("git update-ref refs/heads/swarm/auth-mvp HEAD", "writes history"),
    ("git cherry-pick abc123", "--no-commit"),
    ("git commit -m a && git push", "separate commands"),
])
def test_history_and_bypass_rules(repo, cmd, match):
    setup_milestone(repo)
    (repo / "second.txt").write_text("x\n")
    git(repo, "add", "second.txt")
    git(repo, "commit", "-q", "--no-verify", "-m", "second")  # so HEAD~1 is a real commit
    denied(repo, cmd, match)


def test_allowed_orchestration(repo):
    setup_milestone(repo)
    for cmd in ("git merge --squash swarm-wip/auth-mvp/1.A", "git status", "git diff --stat",
                "git branch -D swarm-wip/auth-mvp/1.A", "git worktree add ../w1 -b swarm-wip/auth-mvp/1.A",
                "git reset", "git log --oneline | head -5"):
        bash(repo, cmd)


# --- protected files -------------------------------------------------------------

@pytest.mark.parametrize("path", [
    "plans/active_milestones/auth-mvp/approvals.md", ".git/plan-swarm/nonces/x.json",
    ".git/hooks/pre-commit", ".git/config", "plans/swarm.md", ".git//hooks/pre-commit", ".git/./hooks/x",
    ".claude/settings.json",
])
def test_write_guard(repo, path):
    with pytest.raises(gate.Deny):
        gate.pre_tool_use({"cwd": str(repo), "tool_name": "Write", "tool_input": {"file_path": str(repo / path)}})


def test_write_guard_allows_normal_files(repo):
    gate.pre_tool_use({"cwd": str(repo), "tool_name": "Edit", "tool_input": {"file_path": str(repo / "src.py")}})


@pytest.mark.parametrize("cmd", [
    "echo x >> plans/active_milestones/m/approvals.md",
    "sed -i '' 's/a/b/' plans/active_milestones/m/approvals.md",
    "rm plans/swarm.md",
    "cat .git/plan-swarm/nonces/*.json",
    "cp /tmp/x .git/hooks/pre-commit",
])
def test_bash_guard(repo, cmd):
    denied(repo, cmd)


def test_bash_guard_allows_reads_and_staging(repo):
    bash(repo, "cat plans/active_milestones/m/approvals.md")
    bash(repo, "git add plans/active_milestones/m/approvals.md")


# --- dispatch --------------------------------------------------------------------

def test_engineer_dispatch_needs_plan_approval(repo):
    setup_milestone(repo)
    event = {"cwd": str(repo), "tool_name": "Agent", "tool_input": {
        "subagent_type": "plan:engineer",
        "prompt": "Implement Task 1.A defined in plans/active_milestones/auth-mvp/plan.md"}}
    with pytest.raises(gate.Deny, match="approve plan auth-mvp"):
        gate.pre_tool_use(event)
    ok("approve plan auth-mvp", repo)
    gate.pre_tool_use(event)
    event["tool_input"]["subagent_type"] = "plan:auditor"
    gate.pre_tool_use(event)


# --- main / exit codes -------------------------------------------------------------

def test_main_exit_codes(repo, monkeypatch, capsys):
    setup_milestone(repo)
    code_change(repo)
    ev = {"cwd": str(repo), "tool_name": "Bash", "tool_input": {"command": "git commit -m x"}}
    monkeypatch.setattr("sys.stdin", __import__("io").StringIO(json.dumps(ev)))
    assert gate.main([]) == 2
    assert "plan-swarm:" in capsys.readouterr().err


# --- git hook (second layer) ---------------------------------------------------------

def test_git_hook_needs_ticket_on_swarm_branch(repo):
    setup_milestone(repo)
    code_change(repo)
    assert gate.git_hook() == 1
    ok("approve commit auth-mvp g1", repo)
    bash(repo, "git commit -m x")  # writes the ticket
    assert gate.git_hook() == 0
    assert gate.git_hook() == 1  # ticket is single-use


def test_git_hook_allows_wip_only_in_swarm_worktrees(repo, monkeypatch):
    import worktree
    setup_milestone(repo)
    wt = worktree.create(str(repo), "auth-mvp", "1.A")["path"]
    open(os.path.join(wt, "a.py"), "w").write("a\n")
    git(wt, "add", "a.py")
    monkeypatch.chdir(wt)
    assert gate.git_hook() == 0
    monkeypatch.chdir(repo)
    git(repo, "checkout", "-q", "-b", "swarm-wip/auth-mvp/x")
    code_change(repo)
    assert gate.git_hook() == 1


def test_git_hook_local_mode_only_during_active_session(repo):
    text = (repo / "plans" / "swarm.md").read_text().replace('"mode": "pr"', '"mode": "local"')
    (repo / "plans" / "swarm.md").write_text(text)
    code_change(repo)
    assert gate.git_hook() == 0  # no session: human commit
    sg.touch_heartbeat(sg.store_dir(str(repo)))
    assert gate.git_hook() == 1


def test_pathspec_commit_of_plans_only_while_code_is_staged(repo):
    d = setup_milestone(repo)
    code_change(repo)  # group code staged
    (d / "plan.md").write_text("# revised plan\n")
    ok("approve plan auth-mvp", repo)
    denied(repo, "git commit -m 'plan: revise'", "no valid approval")
    bash(repo, "git commit -m 'plan: revise' -- plans/active_milestones/auth-mvp/")


def test_changed_paths_keeps_first_letter_of_unstaged_files(repo):
    (repo / "README.md").write_text("changed\n")
    assert sg.changed_paths(str(repo), include_unstaged=True) == {"README.md"}


def test_cd_into_worktree_allows_wip_commit_there(repo):
    import worktree
    setup_milestone(repo)
    wt = worktree.create(str(repo), "auth-mvp", "1.A")["path"]
    open(os.path.join(wt, "a.py"), "w").write("a\n")
    bash(repo, f"cd {wt} && git add -A && git commit -m 'wip(auth-mvp): 1.A'")
    denied(repo, "git add -A && git commit -m x", "no valid approval")  # main checkout still gated
