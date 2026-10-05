#!/usr/bin/env python3
"""End-to-end demo of plan-swarm@3.0: one milestone from setup to release.

Usage:
    python3 examples/e2e_demo.py [WORKDIR]      (default WORKDIR: /tmp/swarm-e2e)

Creates a small Python project with a bare `origin`, installs the swarm, and drives
the milestone "login-rate-limit" through every stage. Hook events are fed to the
plugin's hooks exactly as Claude Code sends them (SessionStart, UserPromptSubmit,
PreToolUse), and every Bash command runs only if the PreToolUse gate allows it, so
the outputs are what a real session produces. What the agents would write (intent,
spec, plan, code, audit) is example content supplied by this script; no model is
called. The captured steps are written to WORKDIR/transcript.json (the source of
docs/usage-e2e.html).

Local test driver: commands are fixed strings, not user input."""
import json, os, shutil, subprocess, sys, textwrap

PLUGIN = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "plugins", "plan")
LIB = f"{PLUGIN}/lib"
BASE = sys.argv[1] if len(sys.argv) > 1 else "/tmp/swarm-e2e"
REPO, ORIGIN = f"{BASE}/shop", f"{BASE}/origin.git"
M = "login-rate-limit"
MD = f"plans/active_milestones/{M}"
env = dict(os.environ, CLAUDE_PLUGIN_ROOT=PLUGIN)
for k in ("PLAN_SWARM_TEST", "PLAN_SWARM_STORE"):
    env.pop(k, None)
steps = []


def rec(stage, label, kind, inp, out, code=None, note=""):
    steps.append(dict(stage=stage, label=label, kind=kind, input=inp, output=out.rstrip("\n"), exit=code, note=note))


def sh(cmd, cwd=REPO, check=True):
    p = subprocess.run(cmd, shell=True, cwd=cwd, env=env, capture_output=True, text=True)
    if check and p.returncode:
        raise SystemExit(f"FAILED: {cmd}\n{p.stdout}\n{p.stderr}")
    return p


def write(path, text, cwd=REPO):
    full = os.path.join(cwd, path)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, "w") as fh:
        fh.write(textwrap.dedent(text).lstrip("\n"))


def tick(path, old, new):
    """Portable in-place replacement (the supervisor ticks checkboxes; the PO updates the roadmap)."""
    full = os.path.join(REPO, path)
    text = open(full).read()
    assert old in text, (path, old)
    open(full, "w").write(text.replace(old, new, 1))


def hook(script, event):
    return subprocess.run(["python3", f"{LIB}/{script}"], input=json.dumps(event), env=env,
                          capture_output=True, text=True, cwd=event.get("cwd", REPO))


def user(stage, phrase, note=""):
    """The developer types a prompt: UserPromptSubmit → approve.py."""
    p = hook("approve.py", {"hook_event_name": "UserPromptSubmit", "prompt": phrase, "cwd": REPO,
                            "session_id": "e2e"})
    out = json.loads(p.stdout)["hookSpecificOutput"]["additionalContext"] if p.stdout.strip() else "(no output: not an approval phrase)"
    rec(stage, f"you type: {phrase}", "prompt", phrase, out, p.returncode, note)
    return out


def tool(stage, command, cwd=REPO, label=None, note="", expect=None):
    """An agent runs a Bash command: PreToolUse gate first, then the command if allowed."""
    g = hook("gate.py", {"hook_event_name": "PreToolUse", "tool_name": "Bash", "cwd": cwd,
                         "tool_input": {"command": command}})
    if g.returncode == 2:
        rec(stage, label or command, "blocked", command, g.stderr, 2, note)
        assert expect in (None, "blocked"), f"unexpectedly blocked: {command}\n{g.stderr}"
        return None
    p = sh(command, cwd=cwd, check=False)
    rec(stage, label or command, "ran", command, (p.stdout + p.stderr), p.returncode, note)
    assert expect in (None, "ran"), f"unexpectedly allowed: {command}"
    return p


def dispatch(stage, agent, prompt, note=""):
    g = hook("gate.py", {"hook_event_name": "PreToolUse", "tool_name": "Agent", "cwd": REPO,
                         "tool_input": {"subagent_type": agent, "prompt": prompt, "description": "dispatch"}})
    rec(stage, f"dispatch {agent}", "blocked" if g.returncode == 2 else "dispatched", prompt,
        g.stderr if g.returncode == 2 else "(allowed)", g.returncode, note)


def script(stage, label, command, note=""):
    p = sh(command, check=False)
    rec(stage, label, "script", command, p.stdout + p.stderr, p.returncode, note)
    return p


def show(stage, label, path, note=""):
    with open(os.path.join(REPO, path)) as fh:
        rec(stage, label, "file", path, fh.read(), None, note)


# ---------------------------------------------------------------- setup: a small existing project
shutil.rmtree(BASE, ignore_errors=True)
os.makedirs(REPO)
sh(f"git init -q --bare {ORIGIN}", cwd=BASE)
sh("git init -q -b main && git config user.email dev@shop.example && git config user.name 'Dana Dev' "
   "&& git config commit.gpgsign false")
write("src/shop/__init__.py", "")
write("src/shop/auth/__init__.py", "")
write("src/shop/routes/__init__.py", "")
write("src/shop/routes/login.py", '''
    from shop.auth.passwords import verify


    def login(username, password, ip, users):
        user = users.get(username)
        if user and verify(password, user["hash"]):
            return {"status": 200, "user": username}
        return {"status": 401, "error": "Invalid username or password"}
''')
write("src/shop/auth/passwords.py", '''
    import hashlib


    def verify(password, stored_hash):
        return hashlib.sha256(password.encode()).hexdigest() == stored_hash
''')
write("tests/test_login.py", '''
    import hashlib
    from shop.routes.login import login

    USERS = {"ana": {"hash": hashlib.sha256(b"s3cret").hexdigest()}}


    def test_login_ok():
        assert login("ana", "s3cret", "1.2.3.4", USERS)["status"] == 200


    def test_login_bad_password():
        assert login("ana", "nope", "1.2.3.4", USERS)["status"] == 401
''')
write(".gitignore", "__pycache__/\n.pytest_cache/\n")
write("pyproject.toml", '''
    [tool.pytest.ini_options]
    pythonpath = ["src"]
''')
write("AGENTS.md", '''
    # AGENTS.md

    ## Build and test

    ```bash
    uvx pytest -q
    ```
''')
sh("git add -A && git commit -q -m 'initial shop app' && git remote add origin " + ORIGIN +
   " && git push -q origin main && git remote set-head origin main")

# ---------------------------------------------------------------- stage 0: setup
S = "0 · Setup"
script(S, "swarm-init preview", f"python3 {LIB}/swarm_init.py --dry-run")
script(S, "swarm-init install", f"python3 {LIB}/swarm_init.py --only swarm,hook,review,ci")
sh("git add -A && git commit -q --no-verify -m 'chore: adopt plan-swarm' && git push -q origin main")
rec(S, "you commit the setup yourself", "note", "git add -A && git commit -m 'chore: adopt plan-swarm'",
    "(committed by the developer outside Claude Code; the swarm never commits its own settings)")
p = hook("health.py", {"hook_event_name": "SessionStart", "source": "startup", "cwd": REPO, "session_id": "e2e"})
rec(S, "SessionStart hook", "hook", "claude  (open Claude Code in the repo)",
    json.loads(p.stdout)["hookSpecificOutput"]["additionalContext"], p.returncode)
tool(S, f'python3 "{LIB}/health.py" --status', label="supervisor orientation: health.py --status")

# ---------------------------------------------------------------- stage 1-2: intent
S = "1 · Intent"
user(S, "Be the supervisor. Login gets brute-forced; limit failed attempts per account and per IP.",
     note="An ordinary prompt: the approval hook ignores it.")
write("plans/intents/2026-09-25-login-rate-limit.md", '''
    # Intent: Login rate limiting

    ## Problem
    The login endpoint accepts unlimited failed attempts, so accounts can be brute-forced.

    ## Outcome
    After repeated failures an account (and a noisy IP) is locked out for a while, and
    the response never reveals whether the account exists.

    ## Users & systems
    Everyone who logs in; `src/shop/routes/login.py`; the auth package.

    ## Constraints
    No new infrastructure (in-memory is acceptable for v1).

    ## Open questions
    Thresholds and lockout duration; whether internal IPs are exempt.
''')
rec(S, "product-owner (intent mode) writes the intent", "file", "plans/intents/2026-09-25-login-rate-limit.md",
    open(f"{REPO}/plans/intents/2026-09-25-login-rate-limit.md").read(), note="Example agent-written content.")
tool(S, f'python3 "{LIB}/tier.py" --milestone {M} --stage intent --intent-file plans/intents/2026-09-25-login-rate-limit.md --write',
     label="supervisor: propose a tier from the intent")
tool(S, "git add plans && git commit -m 'docs: intent'", label="an agent tries to commit before approval",
     expect="blocked")

S = "2 · Accept the intent"
user(S, f"approve intent login-rate-limit as {M}")
tool(S, f"git switch -c swarm/{M}", label="supervisor: create the milestone branch")
tool(S, f"mkdir -p {MD} && mv plans/intents/2026-09-25-login-rate-limit.md {MD}/intent.md",
     label="supervisor: move the intent into the milestone")
write("plans/00-ROADMAP.md", f'''
    # Swarm Master Roadmap

    ## 📦 Release v1.0.0 (Target Date: 2026-10-15) - STATUS: ACTIVE
    - [ ] **Milestone 1: Login rate limiting** - STATUS: ACTIVE
      - *Intent:* `{MD}/intent.md`
      - *Spec:* `{MD}/spec.md`
''')
rec(S, "product-owner adds the roadmap entry", "file", "plans/00-ROADMAP.md", open(f"{REPO}/plans/00-ROADMAP.md").read())
tool(S, f"git add plans/ && git commit -m 'docs({M}): accept intent' -- plans/", label="auditor: artifact commit")

# ---------------------------------------------------------------- research + spec
S = "3 · Research"
with open(f"{REPO}/{MD}/intent.md", "a") as fh:
    fh.write(textwrap.dedent('''
        ## Codebase context
        - `src/shop/routes/login.py::login(username, password, ip, users)` returns 200/401 dicts; no state.
        - Password checks live in `src/shop/auth/passwords.py`; tests in `tests/test_login.py` (pytest, `pythonpath = src`).
        - No existing rate limiting, cache, or clock abstraction.
    '''))
rec(S, "Explore appends Codebase context", "file", f"{MD}/intent.md (appended)",
    open(f"{REPO}/{MD}/intent.md").read().split("## Codebase context")[1].join(["## Codebase context", ""]),
    note="Example agent-written content.")

S = "4 · Spec"
write(f"{MD}/spec.md", '''
    # Product Specification: Login rate limiting

    ## 🎯 Executive Summary
    *   **Goal:** Stop brute-force login attempts without revealing which accounts exist.
    *   **Target User:** Every account holder; the security team.
    *   **Business Value:** Removes the top finding of the last security review.

    ## 📋 Acceptance Criteria
    - **Scenario:** Account lockout
      - **Given** 5 failed logins for one account within 15 minutes
      - **When** a 6th attempt arrives, even with the right password
      - **Then** the response is 429 with the generic lockout message for 15 minutes
    - **Scenario:** No account enumeration
      - **Given** an unknown username
      - **When** it fails 5 times
      - **Then** the responses are identical to a real account's
    - **Scenario:** Noisy IP
      - **Given** 20 failures from one IP within 15 minutes across accounts
      - **When** another attempt arrives from that IP
      - **Then** it gets 429 with the same message

    ## 🚨 Constraints & Edge Cases
    - In-memory counters (single instance) for v1; counters reset on restart.
    - No exemptions for internal IPs.

    ## ⚖️ Policy Concerns
    - None open (lockout messages follow the security policy's no-enumeration rule).
''')
show(S, "product-owner writes spec.md after the Grill Loop", f"{MD}/spec.md", note="Example agent-written content.")
tool(S, f'python3 "{LIB}/usage.py" log --milestone {M} --phase 1 --agent product-owner --tokens 18400 --tools 9 --ms 142000',
     label="supervisor: cost log")
tool(S, f'python3 "{LIB}/usage.py" decline --milestone {M} --phase 1b --gate spec-deliberator',
     label="you decline the offered spec-deliberator; the supervisor logs it")
user(S, f"approve spec {M}")
tool(S, f"git add plans/ && git commit -m 'docs({M}): spec' -- plans/", label="auditor: artifact commit")

# ---------------------------------------------------------------- plan
S = "5 · Plan"
write(f"{MD}/plan.md", f'''
    # Technical Plan: {M}

    ## 🔍 Analysis & Context
    *   **Objective:** Lock out accounts and noisy IPs after repeated login failures.
    *   **Affected Files:** `src/shop/auth/attempts.py`, `src/shop/auth/messages.py`, `src/shop/routes/login.py`
    *   **Risks/Edge Cases:** clock handling; identical responses for unknown users.
    *   **Irreversible Steps:** None

    ## 📋 Task Execution (Parallel Groups)
    ### Group 1 (Parallel Execution - Independent Tasks)
    - [ ] Task 1.A: attempt counter → `src/shop/auth/attempts.py`, `tests/test_attempts.py`
    - [ ] Task 1.B: lockout message → `src/shop/auth/messages.py`, `tests/test_messages.py`

    ### Group 2 (Sequential Execution - Depends on Group 1)
    - [ ] Task 2.A: enforce limits in login → `src/shop/routes/login.py`, `tests/test_login.py`

    ## 🎯 Success Criteria
    *   `uvx pytest -q` passes; every acceptance criterion has a test.
''')
show(S, "architect writes plan.md", f"{MD}/plan.md", note="Example agent-written content.")
tool(S, f'python3 "{LIB}/tier.py" --milestone {M} --stage plan --write', label="supervisor: re-check the tier")

S = "6 · Approve the plan"
dispatch(S, "plan:engineer", f"Implement Task 1.A defined in {MD}/plan.md", note="Before approval.")
user(S, f"approve plan {M}")
tool(S, f"git add plans/ && git commit -m 'docs({M}): plan' -- plans/", label="auditor: artifact commit")
dispatch(S, "plan:engineer", f"Implement Task 1.A defined in {MD}/plan.md", note="After approval.")

# ---------------------------------------------------------------- build group 1
S = "7 · Build (group 1)"
out_a = tool(S, f'python3 "{LIB}/worktree.py" create --milestone {M} --task 1.A', label="supervisor: worktree for 1.A")
out_b = tool(S, f'python3 "{LIB}/worktree.py" create --milestone {M} --task 1.B', label="supervisor: worktree for 1.B")
wa, wb = json.loads(out_a.stdout)["path"], json.loads(out_b.stdout)["path"]
write("src/shop/auth/attempts.py", '''
    """Sliding-window failure counters for accounts and IPs (in memory, single instance)."""
    WINDOW = 15 * 60


    class AttemptCounter:
        def __init__(self, limit, window=WINDOW):
            self.limit, self.window, self.failures = limit, window, {}

        def record_failure(self, key, now):
            recent = [t for t in self.failures.get(key, []) if now - t < self.window]
            recent.append(now)
            self.failures[key] = recent

        def is_locked(self, key, now):
            return len([t for t in self.failures.get(key, []) if now - t < self.window]) >= self.limit
''', cwd=wa)
write("tests/test_attempts.py", '''
    from shop.auth.attempts import AttemptCounter


    def test_locks_after_limit_within_window():
        c = AttemptCounter(limit=5)
        for t in range(5):
            c.record_failure("ana", now=t)
        assert c.is_locked("ana", now=10)


    def test_window_expires():
        c = AttemptCounter(limit=5)
        for t in range(5):
            c.record_failure("ana", now=t)
        assert not c.is_locked("ana", now=15 * 60 + 5)
''', cwd=wa)
write("src/shop/auth/messages.py", '''
    LOCKOUT_MESSAGE = "Too many attempts. Try again later."
''', cwd=wb)
write("tests/test_messages.py", '''
    from shop.auth.messages import LOCKOUT_MESSAGE


    def test_message_does_not_reveal_accounts():
        assert "account" not in LOCKOUT_MESSAGE.lower() and "user" not in LOCKOUT_MESSAGE.lower()
''', cwd=wb)
rec(S, "engineers write code + tests in their worktrees (TDD)", "note", f"{wa}\n{wb}",
    "src/shop/auth/attempts.py + tests/test_attempts.py  (1.A)\nsrc/shop/auth/messages.py + tests/test_messages.py  (1.B)",
    note="Example agent-written content.")
tool(S, f"cd {wa} && git add -A && git commit -m 'wip({M}): 1.A counter'", label="engineer 1.A: WIP commit in its worktree")
tool(S, "git add -A && git commit -m 'sneak it in'", label="an engineer tries to commit in the main checkout",
     expect="blocked")
tool(S, f'python3 "{LIB}/worktree.py" squash --milestone {M}', label="supervisor: integrate the group (1.B's work is auto-committed as WIP)")
tick(f"{MD}/plan.md", "- [ ] Task 1.A", "- [x] Task 1.A")
tick(f"{MD}/plan.md", "- [ ] Task 1.B", "- [x] Task 1.B")
tool(S, "git diff --cached --stat", label="staged group diff")

S = "8 · Audit (group 1)"
t = sh("uvx pytest -q 2>&1 | tail -1", check=False)
rec(S, "auditor runs the tests from AGENTS.md", "ran", "uvx pytest -q", t.stdout, t.returncode)
write(f"{MD}/audit.md", f'''
    # Audit: {M}

    ### Group 1 · Round 1 · PASS
    *   **Completion:** 2/2 steps verified
    *   **Tasks:** Task 1.A: ✅ · Task 1.B: ✅

    #### Step 1.A: attempt counter
    *   **Status:** ✅ Verified
    *   **Evidence:** `AttemptCounter.is_locked` in `src/shop/auth/attempts.py` lines 13-14 counts failures inside the window
    *   **Dynamic Check:** `uvx pytest -q` → {t.stdout.strip()}

    #### Anti-Shortcut & Quality Scan
    *   **Placeholders/TODOs/Deferred Work:** None found
    *   **Test Integrity:** Tests are robust

    #### Conclusion
    PASS.
''')
show(S, "auditor records the round", f"{MD}/audit.md", note="Example agent-written content; the test result line is real.")
tool(S, f'python3 "{LIB}/usage.py" decline --milestone {M} --phase 4 --gate implementation-validator',
     label="you decline the implementation gate for group 1")

S = "9 · Commit gate (group 1)"
tool(S, "git add plans/ && git commit -m 'feat(login-rate-limit): attempt counter and lockout message'",
     label="auditor tries before your approval", expect="blocked")
user(S, f"approve commit {M} g1")
tool(S, "git add plans/ && git commit -m 'feat(login-rate-limit): attempt counter and lockout message'",
     label="auditor: group commit (both git-hook layers pass)")
tool(S, f"git commit --allow-empty -m 'one more'", label="reusing the approval", expect="blocked")
tool(S, f'python3 "{LIB}/worktree.py" cleanup --milestone {M}', label="supervisor: clean up worktrees")

# ---------------------------------------------------------------- group 2
S = "10 · Group 2 and the last commit"
out_c = tool(S, f'python3 "{LIB}/worktree.py" create --milestone {M} --task 2.A', label="supervisor: worktree for 2.A")
wc = json.loads(out_c.stdout)["path"]
write("src/shop/routes/login.py", '''
    from shop.auth.attempts import AttemptCounter
    from shop.auth.messages import LOCKOUT_MESSAGE
    from shop.auth.passwords import verify

    ACCOUNTS = AttemptCounter(limit=5)
    IPS = AttemptCounter(limit=20)


    def login(username, password, ip, users, now=0):
        if ACCOUNTS.is_locked(username, now) or IPS.is_locked(ip, now):
            return {"status": 429, "error": LOCKOUT_MESSAGE}
        user = users.get(username)
        if user and verify(password, user["hash"]):
            return {"status": 200, "user": username}
        ACCOUNTS.record_failure(username, now)
        IPS.record_failure(ip, now)
        return {"status": 401, "error": "Invalid username or password"}
''', cwd=wc)
with open(f"{wc}/tests/test_login.py", "a") as fh:
    fh.write(textwrap.dedent('''

        def test_lockout_after_five_failures():
            for _ in range(5):
                login("bob", "x", "9.9.9.9", USERS)
            assert login("bob", "x", "9.9.9.9", USERS)["status"] == 429
    '''))
tool(S, f'python3 "{LIB}/worktree.py" squash --milestone {M}', label="supervisor: integrate group 2")
tick(f"{MD}/plan.md", "- [ ] Task 2.A", "- [x] Task 2.A")
t = sh("uvx pytest -q 2>&1 | tail -1", check=False)
with open(f"{REPO}/{MD}/audit.md", "a") as fh:
    fh.write(f"\n### Group 2 · Round 1 · PASS\n*   **Completion:** 1/1 steps verified\n*   **Dynamic Check:** `uvx pytest -q` → {t.stdout.strip()}\n")
tick("plans/00-ROADMAP.md", "- [ ] **Milestone 1: Login rate limiting** - STATUS: ACTIVE",
     "- [x] **Milestone 1: Login rate limiting** - STATUS: COMPLETED")
rec(S, "auditor: group 2 passes; product-owner marks the milestone COMPLETED", "ran", "uvx pytest -q", t.stdout, t.returncode)
user(S, f"approve commit {M} g2")
tool(S, "git add plans/ && git commit -m 'feat(login-rate-limit): enforce limits in login'", label="auditor: group commit")
tool(S, f'python3 "{LIB}/worktree.py" cleanup --milestone {M}', label="supervisor: clean up worktrees")

# ---------------------------------------------------------------- PR
S = "11 · Pull request"
tool(S, f'python3 "{LIB}/tier.py" --milestone {M} --stage diff --write', label="supervisor: tier check on the real diff")
tool(S, f"git push -u origin swarm/{M}", label="supervisor tries to push before approval", expect="blocked")
p = sh(f"git push -q origin swarm/{M}", check=False)
rec(S, "…and outside Claude Code the pre-push hook refuses too", "git-hook", f"git push origin swarm/{M}",
    p.stderr, p.returncode)
user(S, f"approve pr {M}")
tool(S, f"git commit -m 'docs({M}): record PR approval' -- {MD}/approvals.md",
     label="auditor: commit the PR approval (ledger-only commit)")
tool(S, f"git push -u origin swarm/{M}", label="supervisor: push (the pre-push hook checks every commit)")
script(S, "PR title (lib/prbody.py)", f'python3 "{LIB}/prbody.py" --milestone {M} --title')
script(S, "PR body (lib/prbody.py)", f'python3 "{LIB}/prbody.py" --milestone {M}')
yml = open(f"{PLUGIN}/templates/ci/plan-swarm.yml").read()
import re as _re
body = _re.search(r"python3 - <<'PY'\n(.*?)\n\s*PY\n", yml, _re.S).group(1)
body = "\n".join(l[10:] if l.startswith(" " * 10) else l for l in body.splitlines())
base = sh("git merge-base origin/main HEAD").stdout.strip()
out_file = f"{BASE}/gh_out"
p = subprocess.run(["python3", "-c", body], cwd=REPO, capture_output=True, text=True,
                   env=dict(env, BASE=base, MILESTONE=f"swarm/{M}", GITHUB_OUTPUT=out_file))
rec(S, "CI ledger job (from templates/ci/plan-swarm.yml)", "ci", "ledger job on the PR", p.stdout + p.stderr, p.returncode)
tool(S, "gh pr merge 1 --squash", label="an agent tries to merge the PR", expect="blocked")
# the code owner merges on GitHub (simulated: fast-forward origin/main on the server side)
tip = sh(f"git rev-parse swarm/{M}").stdout.strip()
sh(f"git --git-dir={ORIGIN} update-ref refs/heads/main {tip}")
rec(S, "a code owner merges the PR on GitHub", "note", "(server side)",
    "origin/main now points at the milestone tip (simulated merge; merge strategy is the host's choice)")

# ---------------------------------------------------------------- release
S = "12 · Release"
tool(S, "git switch main && git pull --ff-only origin main", label="supervisor tries switch + pull in one command",
     expect="blocked", note="The gate judges a command before it runs, so the pull is still seen on the swarm branch.")
tool(S, "git switch main", label="supervisor: switch to the default branch")
tool(S, "git pull --ff-only origin main", label="supervisor: update it (separate command)")
user(S, "approve release v1.0.0")
tool(S, "git tag -a v1.0.0 -m 'Release v1.0.0'", label="supervisor: tag")
tool(S, "git push origin v1.0.0", label="supervisor: push the tag (you agreed)")
tool(S, "git push origin main", label="an agent tries to push main", expect="blocked")

S = "13 · Measure"
script(S, "swarm-metrics", f'python3 "{LIB}/metrics.py" --format text')
script(S, "the milestone branch as its audit trail", f"git log --format='%h %s' main -8")
show(S, "approvals.md (written only by the approval hook)", f"{MD}/approvals.md")
show(S, "usage.md", f"{MD}/usage.md")
script(S, "files the milestone produced", f"find plans -type f | sort")

json.dump(steps, open(f"{BASE}/transcript.json", "w"), indent=1)
print(f"{len(steps)} steps captured → {BASE}/transcript.json")
