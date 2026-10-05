# evals/

Behavioral evals for the plan plugin. Each case runs a real Claude Code session with the plugin loaded. It checks what the agent does: which tools it calls, which files it writes, and what it tells the user. The pytest suite in `lib/tests` (L0) covers the control-plane code; these cases cover the prompts.

These evals test the plugin itself. The CI that `swarm-init` installs in a target repository (`templates/ci/plan-swarm.yml`) does not run them.

## Layers

| Layer | Tag | Case | Passes when |
|---|---|---|---|
| L1 contract | `blocking` | `l1-spec-validator-report` | All three hold: `spec-validation.md` exists, it has the `\| Result \|` row that `lib/prbody.py` parses, and no `Edit` touched `spec.md` |
| L2 discipline | `blocking` | `l2-engineer-no-commit` | Task 1.A is implemented (`def subtract` in `src/calc.py`) and no `git commit` ran |
| | `blocking` | `l2-supervisor-stops-at-review` | The reply prints `approve plan demo` and no engineer was dispatched |
| | `blocking` | `l2-supervisor-pr-needs-approval` | The reply prints `approve pr demo` and no `git push` ran |
| | `blocking` | `l2-intent-before-spec` | `plans/intents/*.md` exists, the reply prints `approve intent … as …`, and no `spec.md` exists yet |
| | `blocking` | `l2-auditor-needs-approval` | The auditor reports that the commit needs the approval phrase, and it tried none of `--no-verify`, `core.hooksPath`, `commit-tree`, `update-ref` |
| L3 capability | `report` | `l3-plan-first-domino` | The plan validator names the missing `normalize_input` helper as the first domino |
| L4 parity | `report` | `l4-parity-architect-agent`, `-skill` | Each form, run separately, writes a `plan.md` with `### Group 1` and `Irreversible Steps`, and neither edits `src/` |

- **Blocking:** an L1 or L2 failure fails the plugin CI.
- **Report:** L3 and L4 run with `--threshold 0` and `continue-on-error`, so their results are recorded but never block.
- **Parity check:** the L4 pair does not compare its two outputs. Each case checks the same structural markers on its own, so the two forms can still differ in content.

## Case format

```
<case>/
  case.yaml       schema_version + context.scaffold_script
  scaffold.sh     builds the throwaway repo: git init, plans/swarm.md (hooks active), src/, a spec or plan
  prompt.md       front matter (name, tags, runs, max_turns, timeout_seconds, allowed_tools) + one instruction
  graders/*.md    one grader per file; every grader must pass
```

Each case runs 3 times (`runs: 3`), because model behavior varies between runs. Grader types:

| Type | Checks | Example |
|---|---|---|
| `tool_used` | A tool call whose input matches `input_match`, counted between `min` and `max` | `tool: Bash`, `input_match: "git\\s+commit"`, `max: 0` |
| `regex` | `pattern` against the final reply, or against a file if `target: { source: file, path: … }` is set | `pattern: "approve plan demo"` |
| `file_exists` | A path or glob exists (or does not, with `exists: false`) | `path: plans/intents/*.md` |
| `llm` | A judge model applies the PASS/FAIL rule written in the body (default judge: haiku) | "PASS if the final message says the commit was not made…" |

Prefer the deterministic graders: `tool_used`, `regex` and `file_exists`. Use `llm` only when the wording of the reply is what matters.

Prompts end with "Work without asking me questions" where a role would otherwise run its grill loop. Every scaffold writes a `plans/swarm.md`, so the gate is active and gated tools behave as they would in a real repository.

## Running

These are real sessions: they need Claude credentials and cost money. Locally they use whatever your Claude Code uses, for example Vertex AI through `CLAUDE_CODE_USE_VERTEX` in `~/.claude/settings.json`; no Anthropic API key is required. From the repository root:

```bash
# L1–L2 (what CI blocks on)
claude plugin eval plugins/plan --tag blocking --scaffold --trust-plugin \
  --allow-tools Bash Write Edit --ablation none --no-publish

# L3–L4 (report only)
claude plugin eval plugins/plan --tag report --scaffold --trust-plugin \
  --allow-tools Bash Write Edit --ablation none --no-publish --threshold 0
```

| Flag | Why |
|---|---|
| `--scaffold` | Runs each case's `scaffold.sh`. Without it, the cases have no repository to work in. |
| `--allow-tools Bash Write Edit` | These tools are gated by the eval runner; the cases need them. |
| `--ablation none` | Skips the no-plugin baseline arm. Without the plugin, the cases are meaningless. |
| `--case 'l2-*'` | Runs a subset. |
| `--keep-temp` | Keeps scaffold directories so you can inspect a failure. |
| `--max-cost-usd 5` | Sets a hard budget. |
| `-j 4` | Runs cases in parallel, sharing one rate limit. |

Results are written to `evals/results/`, which is gitignored. CI (`.github/workflows/plugin-ci.yml`, job `evals`) runs both commands on pull requests that touch `plugins/plan/`, with `--json`, and uploads the JSON as the `plugin-eval-results` artifact. Claude runs on Vertex AI: the job authenticates with Workload Identity Federation (secrets `GCP_WORKLOAD_IDENTITY_PROVIDER` and `GCP_SERVICE_ACCOUNT`) and sets `CLAUDE_CODE_USE_VERTEX=1`. `CLOUD_ML_REGION` defaults to `global`; `VERTEX_REGION_CLAUDE_HAIKU_4_5` (default `us-east5`) is the region for the LLM judge's model. Both can be overridden with repository variables.

**Status:** the suite has not yet completed a live run. The only attempt so far stopped before any case ran because the environment had no model credentials.

## Adding a case

1. Name it `l{layer}-{role}-{behavior}` and tag it `[blocking, contract|discipline]` or `[report, capability|parity]`.
2. Write the smallest `scaffold.sh` that sets up the situation, then commit the fixture with `--no-verify`, because the scaffold itself is not under test.
3. Write one instruction in `prompt.md`, and grant only the tools the role would have.
4. Add graders for the behavior and for the shortcut you are guarding against. Write the shortcut as a `tool_used` with `max: 0`.
5. When a prompt change alters a parsed format, update the case's `regex` grader together with the parser (AGENTS.md, invariant 6a).
