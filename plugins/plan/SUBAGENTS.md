# `plan` plugin agents (subagents): plan-swarm@3.0

The subagent packaging of the swarm. The [skills form](README.md) and this agents form are **generated from the same role files** in [`roles/`](roles/), so they describe the same lifecycle, write the same `plans/` artifacts, and are held by the same control plane. What differs is delivery: an agent is a standalone subagent with its own tool allowlist, dispatched with the `Agent` tool (`subagent_type: plan:{name}`), invoked with an `@"plan:{name} (agent)"` mention, auto-delegated from its `description`, or launched as the main session with `claude --agent plan:{name}`.

Lifecycle, control plane, approval phrases, artifact map, and configuration are documented once in [README.md](README.md).

---

## Anatomy of an agent

Each `agents/{name}.md` is rendered from the `<!-- @agent:frontmatter -->` block and the body of `roles/{name}.md` (shared text plus `<!-- @agent -->` sections). Never edit `agents/` directly.

| Field | Purpose |
|---|---|
| `name` | Dispatch it as `plan:{name}`. |
| `description` | Purpose plus `<example>` blocks; the runtime reads these to **auto-delegate**, so they are functional. |
| `model` | `inherit` for every agent (runs on the caller's model and effort). |
| `color` | UI color: cyan supervisor/recap, purple product owner/deliberators, blue architects, green engineer/simplifier, yellow auditor, red validators. |
| `tools` | A capability contract. `architect` and `product-owner` have no `Bash` (read-only on code, cannot run git). `engineer`, `auditor`, `simplifier`, and the visual roles have `Bash`. Validators, deliberators, and the supervisor get all tools because they dispatch their own subagents. |

When dispatched, an agent is written to stop on an ambiguous target and put the question in its final report, which the supervisor relays to you. Launched as the main session (`claude --agent plan:{name}`), the same agent asks you directly.

The control plane applies to agents exactly as to skills: an engineer's `git commit` outside its worktree, an auditor's commit without an approval, or an engineer dispatched before `approve plan` is refused by the `PreToolUse` gate, and the agent reports the reason.

---

## Agents

| Agent | Tools | Notes |
|---|---|---|
| `supervisor` | all | Orchestrates the state machine; prints approval phrases; runs `health.py`, `tier.py`, `worktree.py`, `usage.py`, `prbody.py`. |
| `product-owner` | Read, Write, Edit, Glob, Grep, AskUserQuestion | Grill Loop needs `AskUserQuestion`; intent mode; roadmap. The supervisor does the `git mv` of accepted intents. |
| `visual-product-owner` | … + Bash | Drop-in; renders `visual-spec.html`. |
| `architect` | Read, Write, Edit, Glob, Grep | Read-only on code; plans parallel groups with disjoint files. |
| `visual-architect` | … + Bash | Drop-in; renders `visual-plan.html`. |
| `engineer` | Read, Write, Edit, Glob, Grep, Bash | TDD; worktree mode (WIP commits on `swarm-wip/*` only). |
| `simplifier` | Read, Write, Edit, Glob, Grep, Bash | **New in 3.0** as an agent; clarity-only pass on the staged diff. |
| `auditor` | Read, Write, Edit, Glob, Grep, Bash | Audit rounds in `audit.md`; the only committer. |
| `visual-implementation-recap` | Read, Write, Edit, Glob, Grep, Bash | Renders `visual-recap.html`; never commits. |
| `spec-deliberator`, `plan-deliberator` | all | Delegate panels; generative, may revise their artifact. |
| `spec-validator`, `plan-validator`, `implementation-validator` | all | Skeptic panels; **report only**. `implementation-validator` has a PR mode. |

---

## Invoking an agent

**Recommended layout: the supervisor as the main session.**

```bash
cd your-repo
claude --agent plan:supervisor     # add --plugin-dir <checkout>/plugins/plan until 3.0 is published
```

`--agent supervisor` also works. To make it the default in a repository, set `"agent": "plan:supervisor"` in that repository's `.claude/settings.json`. The supervisor then dispatches each role as a `plan:<role>` subagent, so every role works in its own context on the files it is handed.

Verified against Claude Code 2.1.282:

- **Approval phrases only count from the human.** The `UserPromptSubmit` hook fires for prompts you type in the main session. A subagent whose entire prompt was an approval phrase recorded nothing, so type every phrase in the main session.
- **Nested dispatch works.** A subagent that has the Agent tool can start its own subagents, so validators and deliberators dispatched by the supervisor still fan out their skeptics and delegates.

Calling one role yourself:

| How | Example |
|---|---|
| @-mention (always invokes it) | `@"plan:architect (agent)" plan plans/active_milestones/x/spec.md` |
| Plain request (Claude decides) | "use the plan:architect agent to plan …" (auto-delegation from its `description`) |
| As the whole session | `claude --agent plan:architect` |

Use agents rather than role skills when you want separation: a skill such as `/plan:architect` loads into the current context, an agent gets its own. The utility skills (`/plan:swarm-init`, `/plan:swarm-metrics`) are meant to run in the main session. `architect` and `product-owner` have no Agent tool and cannot dispatch; if you want the Grill Loop's questions live, run `claude --agent plan:product-owner` for that stage.

---

## Differences from the skills family

| Aspect | Skills | Agents |
|---|---|---|
| Source | `roles/{name}.md` (`@skill` sections) | `roles/{name}.md` (`@agent` sections) |
| Utilities | `swarm-init`, `swarm-metrics`, `wf-trajectory` | not ported (utilities, out of lifecycle) |
| Runtime config | inherits the session | explicit `model`, `color`, `tools` |
| Invocation | `Skill` tool, `/plan:<name>` | `@"plan:<name> (agent)"`, auto-delegation, `Agent` tool (`subagent_type: plan:<name>`), `claude --agent plan:<name>` |

The eval suite includes parity cases (`evals/l4-parity-architect-agent` and `-skill`) that run the same task through both forms.
