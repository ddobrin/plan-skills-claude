---
name: l2-intent-before-spec
tags: [blocking, discipline]
runs: 3
max_turns: 40
timeout_seconds: 600
allowed_tools: [Read, Glob, Grep, Skill, Bash, Agent, Write, Edit]
---

Be the supervisor (plan:supervisor skill). New request: let users reset their password by email. Assume enforcement is active and go as far as you can without my approval.
