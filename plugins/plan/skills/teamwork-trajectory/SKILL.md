---
name: teamwork-trajectory
description: Automatically scans the .agents/ directory, parses agent briefing and handoff records, and compiles a stunning interactive HTML visualization timeline written directly under .agents/trajectory.html.
---

# Teamwork Trajectory Skill

This skill allows you to dynamically compile an interactive, dark-mode visual timeline of all agents executed by your swarm.

## Usage
- Trigger this skill when the user asks to "generate trajectory", "visualize teamwork", "trace agents", or "update trajectory dashboard".
- Run `python3 ${CLAUDE_PLUGIN_ROOT}/skills/teamwork-trajectory/generator.py` from the project root; it scans `.agents/` and writes `.agents/trajectory.html`.
