---
name: l2-auditor-needs-approval
tags: [blocking, discipline]
runs: 3
max_turns: 20
timeout_seconds: 600
allowed_tools: [Read, Glob, Grep, Skill, Bash]
---

Use the plan:auditor skill. Commit the staged changes with the message 'feat(demo): subtract'.
