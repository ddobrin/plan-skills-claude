---
name: swarm-metrics
description: Report AI-native SDLC indicators for plan-swarm milestones from committed artifacts - lead times (intent → spec → plan → commit → PR), groups committed, first-pass audit rate, failed audit rounds, validator re-runs, cost and declined gates, and intent survival. Triggers - "swarm metrics", "how is the swarm doing", "lead time for this milestone", "show rework and cost".
---

# Swarm metrics

Reads only committed files (`approvals.md`, `audit.md`, `usage.md`, gate reports, `plans/intents/`), so the numbers are reproducible and match the audit trail.

## Steps
1. Run `python3 "${CLAUDE_PLUGIN_ROOT}/lib/metrics.py" --format text` for every milestone, or add `--milestone {m}` for one. Use `--format json` when the user wants to process the numbers.
2. Present the result and point out what stands out:
   - **Lead time:** which stage waits longest (usually a human gate: that's review latency, not agent time).
   - **Quality:** a first-pass audit rate below 1.0 or several failed rounds means the plan's steps were under-specified; validator re-runs mean the artifact changed materially after review.
   - **Cost:** tokens per milestone, and which gates were declined at which tier.
   - **Intents:** survival rate = accepted / (accepted + closed); open intents are waiting for triage.
3. Keep interpretation to what the numbers show; say when a value is missing because the milestone hasn't reached that stage yet.
