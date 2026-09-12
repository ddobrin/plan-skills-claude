---
name: teamwork-trajectory
description: Use to render a swarm run that wrote briefing and hand-off records under a project's .agents/ directory as a dark-mode interactive HTML timeline at .agents/trajectory.html. Out-of-band utility, not part of the spec-plan-execute lifecycle - it reads only what is already on disk and changes nothing else. Symptoms - "generate trajectory", "visualize teamwork", "trace the agents that ran", "update the trajectory dashboard". For a Claude Code Workflow run (wf_<runId>.json) use wf-trajectory instead.
---

# Teamwork Trajectory

Compile an interactive, dark-mode timeline of every agent a swarm executed, from the
briefing and hand-off records it left under `.agents/`.

## When to Use

- A run has already written per-agent records under a project's `.agents/` directory and
  someone wants to see the sequence.

## When NOT to Use

- The run you want to see is a Claude Code dynamic Workflow (`wf_<runId>.json` under
  `~/.claude/projects/.../workflows/`) — that is `wf-trajectory`.
- The project has no `.agents/` directory. Nothing in this plugin's lifecycle writes one
  (the swarm's artifacts live under `plans/`), so this skill applies only to a workspace
  that already follows the `.agents/` convention. Say so rather than creating the
  directory.

## Run

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/teamwork-trajectory/generator.py
```

## Contract

- **Input:** the nearest `.agents/` directory found by walking up from the generator's own
  location. It takes no arguments and no path override, so it finds the project's records
  only when the plugin is installed inside that project's tree. Outside that layout it
  exits 1 with `Error: .agents/ directory not found in parent path tree of <dir>` — report
  that message rather than retrying.
- **Output:** `<workspace>/.agents/trajectory.html`, overwritten in place. Self-contained;
  open it directly at `file://`.
- **Exit codes:** `0` on success, `1` when no `.agents/` directory is found. Progress lines
  go to stdout; the absolute output path is printed before the write.
- **Side effects:** none beyond that one file. It never reads or writes source code.
