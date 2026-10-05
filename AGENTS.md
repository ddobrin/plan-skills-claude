# AGENTS.md

Guidance for AI coding agents working **on** this repository. It ships one Claude Code plugin, `plan` (plan-swarm@3.0): role prompts that take a change from intent to pull request, plus a small Python control plane that enforces human approvals with hooks.

Two kinds of content live here, and both are behavior:

- **Prompts** (`plugins/plan/roles/*.md`): a one-word change changes how the swarm acts.
- **Control-plane code** (`plugins/plan/lib/*.py`, `hooks/hooks.json`): it decides what agents in *other* repositories may commit, push, or tag. Treat it as security-relevant code.

---

## Repository layout

```
.claude-plugin/marketplace.json     Marketplace "plan-skills" → plugin plan (3.0.0)
.github/workflows/plugin-ci.yml     L0 tests + generated-file check; L1–L2 evals block, L3–L4 report
plugins/plan/
  .claude-plugin/plugin.json        Manifest (version 3.0.0)
  roles/*.md                        CANONICAL role prompts (14): edit here only
  agents/*.md                       GENERATED agent form (14): never edit
  skills/{role}/SKILL.md            GENERATED skill form (14): never edit
  skills/{swarm-init,swarm-metrics,wf-trajectory}/   hand-written utility skills
  skills/visual-*/assets|references hand-written templates shared by both forms
  hooks/hooks.json                  SessionStart → health.py · UserPromptSubmit → approve.py · PreToolUse → gate.py
  templates/git-hooks/              pre-commit · pre-merge-commit · pre-push → gate.py (second layer)
  lib/                              control plane + helpers (stdlib only; see below)
  lib/tests/                        pytest suite (L0)
  evals/                            claude plugin eval cases (L1 contract, L2 discipline, L3 capability, L4 parity); see evals/README.md
  templates/                        installed into target repos by swarm-init
  topology.md                       plan-swarm@3.0 graph (Markdown + fenced JSON)
  README.md · SUBAGENTS.md          reference docs
docs/
  playbook.html · ai-dlc.html       developer guide · as-built AI-DLC description
  usage-e2e.html · walkthrough.html end-to-end run (real outputs) · reviewer walkthrough of the 3.0 change
  architecture.html · implementation-plan.html · feasible.html   design record
examples/e2e_demo.py                drives one milestone through every stage with the real hooks (no model calls)
images/                             visual introductions (GIFs, stepper, MP4, explainer, cheat sheet); see images/README.md
multi-agent/                        standalone pattern write-ups, not part of the plugin
```

`lib/`: `swarmdoc.py` (fenced-JSON reader, `swarm.md` validation, globs) · `swarmgit.py` (git, `.git/plan-swarm/` store, ledger) · `approve.py` · `gate.py` · `health.py` · `tier.py` · `worktree.py` · `usage.py` · `prbody.py` · `metrics.py` · `swarm_init.py` · `render_roles.py` · `tally.py`.

---

## The swarm in one paragraph

The supervisor derives each milestone's state from files in the target repo's `plans/`, dispatches roles in order (product owner → architect → engineers ×≤5 in worktrees → auditor), offers validator and deliberator panels by risk tier, and prints an exact approval phrase at every human gate: `approve intent|spec|plan|commit|pr|release …`. `approve.py` turns a phrase into a single-use approval bound to HEAD and writes `approvals.md`; `gate.py` consumes it before the git operation and blocks everything else. The full description is in `plugins/plan/README.md`; the graph is `plugins/plan/topology.md`.

---

## Invariants to keep when editing

1. **One source per role.** Edit `roles/{name}.md`, then run `python3 plugins/plan/lib/render_roles.py`. Shared body text goes to both forms; `<!-- @agent -->` / `<!-- @skill -->` blocks go to one. CI fails if `agents/` or `skills/{role}/` are stale (`--check`). Front matter is copied verbatim, so keep `name:` equal to the file name.
2. **Stdlib only in `lib/`.** Hooks run on the user's `python3`; no third-party imports. That is also why configuration is Markdown with one fenced JSON block (`swarm-config`, `plan-swarm-topology`), found by its tag via `swarmdoc.extract` (not `tally.load`, which ignores tags).
3. **The gate fails closed.** Inactive only when `plans/swarm.md` is absent *and* the repository was never activated (`.git/plan-swarm/active`); invalid or missing-after-activation config refuses gated operations while all other checks still run; any exception in a hook exits 2 (PreToolUse) or 1 (git hooks). Never add a code path that lets a commit, push, or tag through without a consumed approval, except WIP commits inside a linked worktree under `.swarm/worktrees/`. Unknown git forms are refused, not allowed.
3a. **Threat model.** The gate guards against well-meaning agents, not determined adversaries; do not claim more. Every bypass found gets a regression test in `lib/tests/test_security.py` before the fix.
4. **Approvals come only from real user prompts.** Only `approve.py` (UserPromptSubmit) mints approvals and writes `approvals.md`. The gate blocks agent writes to `approvals.md`, `plans/swarm.md`, `.git/plan-swarm/`, and `.git/hooks/`.
5. **Branch names are part of the contract:** `swarm/{m}` for milestones, `swarm-wip/{m}/{task}` for worktrees (git cannot hold refs below an existing branch, so never `swarm/{m}/…`).
6. **Which approval authorizes what:** intent/spec/plan/commit rows authorize the commit whose parent is their HEAD; a `pr` row authorizes the first push and the one ledger-only commit that records it; a `release` row authorizes the tag. `approve.py` stages each row. The gate, the `pre-push` hook, and the CI ledger check must agree on this.
6a. **Parseable formats are shared contracts:** the ledger table (9 columns), `### Group g · Round r · PASS|FAIL` in `audit.md`, `Risk tier (proposed)` lines, the `| Result |` row in panel reports, `usage.md` columns, and skeptic JSON for `tally.py`. Change a format and its parser together (`swarmgit`, `metrics`, `prbody`, `tier`, the CI ledger check in `templates/ci/plan-swarm.yml`).
7. **Reviewers never write.** Validators report; authors apply (product owner, architect, engineer). Only the auditor commits.
8. **Tool allowlists are capability contracts.** `architect` and `product-owner` have no `Bash`; the supervisor performs git moves for them.
9. **Docs follow behavior.** When a role, gate, phrase, artifact, or format changes, update `plugins/plan/README.md`, `SUBAGENTS.md`, `topology.md`, and `docs/playbook.html` / `docs/ai-dlc.html`.

---

## Commands

```bash
# render roles → agents/ + skills/ (and check in CI)
python3 plugins/plan/lib/render_roles.py
python3 plugins/plan/lib/render_roles.py --check

# tests (pytest is not installed globally; use uvx)
uvx pytest -q plugins/plan/lib/tests
uvx pytest -q plugins/plan/skills/wf-trajectory/tests

# evals (real Claude sessions; cost money)
claude plugin eval plugins/plan --tag blocking --scaffold --trust-plugin \
  --allow-tools Bash Write Edit --ablation none --no-publish

# run the swarm from this checkout (supervisor as main session; roles run as subagents)
claude --plugin-dir plugins/plan --agent plan:supervisor

# validate manifests
claude plugin validate . && claude plugin validate plugins/plan

# try the hooks by hand in a scratch repo with plans/swarm.md
echo '{"cwd":"'"$PWD"'","tool_name":"Bash","tool_input":{"command":"git push origin main"}}' \
  | python3 plugins/plan/lib/gate.py; echo "exit $?"
```

---

## Known limits

- The gate reads shell command strings and refuses what it cannot parse or recognize; the git hooks re-check commits and pushes made by any route. A determined agent with shell access can still defeat local controls, so branch protection, the CI ledger check, and code-owner review are the authority.
- Hook inputs do not identify the calling subagent, so file-scope rules are role-agnostic (they protect specific paths, not specific roles).
- Organizations that enforce `allowManagedHooksOnly` must adopt the gate as a managed hook (`templates/managed-settings.example.md`); otherwise the supervisor reports enforcement off and refuses gated steps.
