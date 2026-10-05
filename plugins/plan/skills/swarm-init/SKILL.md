---
name: swarm-init
description: Prepare a repository for the plan swarm (plan-swarm@3.0) - installs plans/swarm.md (settings), the git approval hooks (pre-commit, pre-merge-commit, pre-push), REVIEW.md, the CI workflow, and an AGENTS.md skeleton, never overwriting existing files. Triggers - "set up the plan swarm", "swarm init", "initialize plans/swarm.md", "install the swarm hooks", or when the supervisor reports there is no plans/swarm.md.
---

# Swarm init

Installs the project-side pieces of plan-swarm@3.0 into the current repository. The plugin's own hooks are already active once the plugin is installed; they only start enforcing in a repository that has `plans/swarm.md`.

## Steps

1. **Preview.** Run:
   `python3 "${CLAUDE_PLUGIN_ROOT}/lib/swarm_init.py" --dry-run`
   It prints one line per template: `would install`, `exists`, or `skipped`.
2. **Ask.** Show the preview and ask which to install. Explain each briefly:
   - `swarm` → `plans/swarm.md`: delivery mode (pr or local), engineer limit, Path A limit, approval lifetime, policy skills, risk-tier rules. Required.
   - `hook` → `.git/hooks/pre-commit`, `pre-merge-commit`, `pre-push`: the second enforcement layer for commits and pushes made by any route. Strongly recommended.
   - `review` → `REVIEW.md`: review passes and severity thresholds for PR review. Recommended with pr mode.
   - `ci` → `.github/workflows/plan-swarm.yml`: ledger check, PR review against `REVIEW.md`, and the tier-gated validator panel in GitHub Actions. Claude runs on Vertex AI: needs the `GCP_WORKLOAD_IDENTITY_PROVIDER` and `GCP_SERVICE_ACCOUNT` secrets (Workload Identity Federation) and the `id-token: write` permission the workflow already declares.
   - `agents` → `AGENTS.md` skeleton: build and test commands the auditor runs. Skipped if the repo already has `AGENTS.md` or `CLAUDE.md` (the swarm reads either). If both exist and `CLAUDE.md` does not import `@AGENTS.md`, the script says so; Claude Code ignores `AGENTS.md` next to a `CLAUDE.md` unless it is imported, so tell the user.
3. **Install** what the user chose:
   `python3 "${CLAUDE_PLUGIN_ROOT}/lib/swarm_init.py" --only swarm,hook,review,ci,agents`
   (keep only the chosen names). Existing files are never overwritten. If another tool already owns one of the git hooks, the script prints the one line to add to that hook; show it to the user.
4. **Next steps for the user:**
   - Read `plans/swarm.md` and adjust the values; the explanations sit next to them. After it exists, agents can no longer edit it, and the repository is marked active (`.git/plan-swarm/active`): removing `swarm.md` later makes the gate refuse gated steps until a person restores it or deletes that marker.
   - Fill in the build and test commands in `AGENTS.md` (or the existing `CLAUDE.md`).
   - Commit these files themselves, like any other change.
   - Start the swarm with `claude --agent plan:supervisor` (each role then runs as a subagent with its own context), or say "be the supervisor".

## Constraints
- Never overwrite or delete an existing file; the script refuses to anyway.
- Do not create or edit `plans/swarm.md` by hand once it exists; tell the user to edit it.
