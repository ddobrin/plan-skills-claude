# `plan` plugin: plan-swarm@3.0

An AI-native software development lifecycle for Claude Code. A swarm of role agents takes a feature, bug fix, or refactor from **intent → spec → plan → parallel build → audit → commit → pull request → release**. Optional validator and deliberator panels attack or improve each artifact at its phase boundary, and a hook-enforced **control plane** makes sure nothing is committed, pushed, or tagged without the user's exact approval phrase.

The swarm ships in two forms with identical behavior: **skills** (invoked with the `Skill` tool, e.g. `plan:supervisor`) and **subagents** (dispatched with the `Agent` tool as `plan:{name}`, auto-delegated, or launched with `claude --agent {name}`). Both are generated from one source per role in [`roles/`](roles/). This document describes the skills form and the shared machinery; [`SUBAGENTS.md`](SUBAGENTS.md) covers the agent specifics. The developer guide is [`docs/playbook.html`](../../docs/playbook.html); the as-built description is [`docs/ai-dlc.html`](../../docs/ai-dlc.html).

---

## Quick start

```text
/plugin marketplace add ddobrin/plan-skills-claude
/plugin install plan@plan-skills
```

Until 3.0 is published to the marketplace, the installed plugin is the older 2.1 (no `swarm-init`). Load the 3.0 plugin from a checkout instead, with `claude --plugin-dir <checkout>/plugins/plan`, and disable the installed `plan@plan-skills` in the `/plugin` menu.

In the target repository, type **`/plan:swarm-init`** once. It installs `plans/swarm.md` (settings), three git hooks (`pre-commit`, `pre-merge-commit`, `pre-push`), and optionally `REVIEW.md`, the CI workflow, and an `AGENTS.md` skeleton (not added when the repository already has a `CLAUDE.md`; the roles read either file). Then start the supervisor as the main session, **`claude --agent plan:supervisor`** (or say "be the supervisor"); it dispatches each role as a subagent. See [SUBAGENTS.md](SUBAGENTS.md#invoking-an-agent). The plugin's hooks are active only in repositories that have `plans/swarm.md`.

---

## The lifecycle

```
 request ─► 1 INTENT ─► 🔒 approve intent ─► 2 research ─► 3 SPEC ─► [spec gates] ─► 🔒 approve spec
        ─► 4 PLAN ─► [plan gates] ─► 🔒 approve plan (tier confirmed)
        ─► 5 per execution group: engineers ×≤5 in worktrees ─► squash ─► [simplifier] ─► auditor
                                  ─► [implementation gate · recap] ─► 🔒 approve commit {m} g{n}
        ─► 6 🔒 approve pr ─► CI review ─► code owner merges ─► 7 🔒 approve release ─► tag
```

- 🔒 = a human approval phrase. The `UserPromptSubmit` hook turns it into a single-use approval bound to the current HEAD (15 minutes by default) and appends a row to the milestone's `approvals.md`. The `PreToolUse` gate consumes it before the matching git operation.
- `[…]` = offered: validators, deliberators, simplifier, and recap run only when the user says yes. The milestone's **risk tier** (routine · elevated · critical, from rules in `plans/swarm.md`) sets how strongly the supervisor recommends them; declines are logged with the tier.
- In **pr mode** (default) the milestone lives on branch `swarm/{m}`, created when the intent is accepted, and ends in a PR. In **local mode** commits land on the current branch and there is no PR.
- Feedback loops: validator findings go back to the author (product owner or architect); audit failures go back to an engineer (**Path A**, at most 3 rounds per task, then the user decides); impossible plans go back to the architect (**Path B**, re-approved); PR review findings become a fix group.

---

## Skills

### Lifecycle roles

| Skill | Role |
|---|---|
| `supervisor` | Orchestrator. Checks enforcement (`lib/health.py --status`), derives each milestone's state from its files, dispatches roles, offers gates by tier, prints the exact approval phrase at every gate, runs worktrees and squashes, opens the PR. Never codes, never commits. |
| `product-owner` | Writes intents (intent mode) and Gherkin specs through the **Grill Loop** (≤3 questions at a time), loads the project's policy skills, records *Policy Concerns*, owns `00-ROADMAP.md`, applies spec-validator tightenings. No code, no Bash. |
| `visual-product-owner` | Drop-in for `product-owner`; also renders `visual-spec.html`. |
| `architect` | Reads the code (read-only, no Bash) and writes `plan.md`: micro-steps, test first, parallel groups with disjoint files, *Irreversible Steps*. Applies plan-validator fixes and Path B revisions. |
| `visual-architect` | Drop-in for `architect`; also renders `visual-plan.html`. |
| `engineer` | Implements one task under strict TDD. In **worktree mode** it works only in its own worktree and may make WIP commits on `swarm-wip/{m}/{task}`; otherwise it never commits. |
| `simplifier` | Optional clarity-only refactor of the staged group diff, zero behavioral change. |
| `auditor` | Verifies each group with `file:line` evidence, build and tests, and an anti-shortcut scan; appends `### Group g · Round r · PASS/FAIL` to the tracked `audit.md`. **The only role that commits**, and only with an approval. |
| `visual-implementation-recap` | Renders `visual-recap.html` for the commit gate and the PR; additive, never a substitute for the audit. |

### Offered panels

| Skill | Panel |
|---|---|
| `spec-deliberator` | 3 delegates with **disjoint** context bundles (product · engineering · ops/security) converge on one revised spec, ≤4 rounds. Always followed by `spec-validator`. |
| `spec-validator` | 3 independent skeptics attack the spec (ambiguity, gaps, untestable criteria, malicious compliance, policy). 2-of-3 quorum via `lib/tally.py`. **Report only**: tightenings go to the product owner. |
| `plan-deliberator` | 3 delegates with **assigned territories** (intent · codebase · delivery) reshape the plan and decide trade-offs. Always followed by `plan-validator`. |
| `plan-validator` | 3 skeptics read the codebase to find the **first domino**. Report only: fixes go to the architect. |
| `implementation-validator` | 3 skeptics attack the diff; its key output is **calibrated severity**. Report only: defects go to an engineer. **PR mode** reads `REVIEW.md` and maps severity to Important/Nit. |

All panels write a Markdown report under the milestone (`adversarial-reviews/` or `deliberations/`) on every run, re-runs as `-r2`, `-r3`.

### Utilities

| Skill | Purpose |
|---|---|
| `swarm-init` | Installs the project templates (never overwrites). |
| `swarm-metrics` | Reports lead times, first-pass audit rate, rework, cost, declined gates, and intent survival from committed files (`lib/metrics.py`). |
| `wf-trajectory` | Renders a Claude Code Workflow run as an offline HTML page. |

---

## Control plane (`hooks/hooks.json` → `lib/`)

| Hook | Script | Does |
|---|---|---|
| `SessionStart` | `health.py` | Heartbeat, refreshes the git hook's copy of the gate, reports enforcement status. |
| `UserPromptSubmit` | `approve.py` | Parses the six approval phrases (whole message, case-insensitive), mints the approval, writes the ledger row. |
| `PreToolUse` (Bash, Write, Edit, Agent) | `gate.py` | Git policy: commits need a matching approval (WIP only on `swarm-wip/*`), first push of `swarm/{m}` needs `approve pr`, tags need `approve release`; no default-branch or force pushes, no history rewrites on swarm branches, no hook bypasses. Blocks agent writes to `approvals.md`, `plans/swarm.md`, `.git/plan-swarm/`, `.git/hooks/`. Blocks engineer dispatch before `approve plan`. |
| git `pre-commit`, `pre-merge-commit` | `gate.py --git-hook` | Second layer for commits by any route: allowed only with the one-time ticket the first layer issued; a plans-only approval cannot carry code; WIP only inside the swarm's linked worktrees. |
| git `pre-push` | `gate.py --pre-push` | Second layer for pushes: `swarm/{m}` fast-forwards whose every new commit's parent matches an intent/spec/plan/commit ledger row (a `pr` row authorizes only the ledger-only commit that records it; the first push needs that row). Other branches and tags are refused only while a swarm session is active. |

Approval phrases:

```text
approve intent  <slug> as <milestone>
approve spec    <milestone>
approve plan    <milestone> [tier=routine|elevated|critical]
approve commit  <milestone> g<n>
approve pr      <milestone>
approve release <version>
```

Approvals and tickets live in `.git/plan-swarm/` (outside the working tree, shared by worktrees). The approval hook stages each new ledger row, so it ships inside the commit it authorizes. The gate fails closed: an invalid `plans/swarm.md`, a missing one after `swarm-init` marked the repository (`.git/plan-swarm/active`), or any internal error refuses gated operations.

**Threat model.** The local layers guard against well-meaning agents that try to unblock themselves; they are not a sandbox against a determined adversary with shell access. Branch protection, the CI ledger check, and code-owner review are the authoritative controls. `lib/tests/test_security.py` holds a regression test for every finding of the security review. If an organization disables plugin hooks, the heartbeat goes stale and the supervisor reports **enforcement off**; `templates/managed-settings.example.md` shows how to run the gate as a managed hook.

### Helper scripts (called by the supervisor)

`tier.py` (risk tier, only rises) · `worktree.py` (create / squash / cleanup per-task worktrees; refuses overlapping files) · `usage.py` (cost and declined-gate log) · `prbody.py` (PR title and body from committed artifacts) · `metrics.py` · `swarmdoc.py` (reads the fenced JSON block of `swarm.md`, `topology.md`) · `tally.py` (validator votes) · `render_roles.py` (roles → agents + skills) · `swarm_init.py`.

---

## Artifact map

| Path | Written by | Committed at |
|---|---|---|
| `plans/swarm.md` | people (`swarm-init` template) | by the user |
| `plans/intents/{date}-{slug}.md` | product-owner (intent mode) | moved into the milestone on acceptance; rejected ones go to `plans/intents/closed/` |
| `plans/00-ROADMAP.md` | product-owner | with the intent; COMPLETED ships in the PR |
| `plans/active_milestones/{m}/intent.md` | product-owner + Explore (*Codebase context*) | `approve intent` / `approve spec` |
| `…/spec.md` (+ `visual-spec.html`) | product-owner | `approve spec` |
| `…/plan.md` (+ `data-model.md`, `api-contracts.md`, `visual-plan.html`) | architect; `tier.py` adds the tier line | `approve plan` |
| `…/approvals.md` | `approve.py` only | with the commit it authorizes |
| `…/audit.md` | auditor | with the group commit |
| `…/usage.md` | supervisor via `usage.py` | with the next commit |
| `…/adversarial-reviews/*.md`, `…/deliberations/*.md` | panels | with the next artifact or group commit |
| `…/visual-recap.html` | recap | with the group commit |
| `plans/approvals.md` | `approve.py` (release rows) | with the next roadmap commit |

---

## Configuration: `plans/swarm.md`

Markdown for people plus exactly one fenced `json swarm-config` block for the scripts (stdlib `json`, no YAML dependency). Keys: `delivery.mode` (`pr` | `local`), `delivery.host` (`github`), `engineers.max_concurrent` (default 5), `audit.max_path_a_rounds` (default 3), `approvals.nonce_ttl_minutes` (default 15), `policies` (project skill names), `tiers.{elevated,critical}.{paths,keywords,diff_lines_over}`. See `templates/swarm.md`.

---

## Developing the plugin

- Edit roles only in `roles/{name}.md`, then run `python3 lib/render_roles.py`. `--check` fails CI when generated files are stale.
- Tests: `uvx pytest -q lib/tests` and `uvx pytest -q skills/wf-trajectory/tests`.
- Evals: `claude plugin eval . --tag blocking --scaffold --trust-plugin --allow-tools Bash Write Edit --ablation none --no-publish` (use `--tag report` for L3–L4). Layers, case format, and graders: [`evals/README.md`](evals/README.md).
- The topology is `topology.md` (Markdown + fenced JSON, checked by the tests).
