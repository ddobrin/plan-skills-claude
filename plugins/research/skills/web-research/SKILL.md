---
name: web-research
description: Resolve a question against live web sources using two independent search paths — Gemini Flash on Vertex AI with Google Search grounding, plus native WebSearch/WebFetch — then cross-check them and return a cited answer that separates verified facts from unverified assertions. Use for current library/API versions, pricing, rate limits, regulations, release notes, vendor comparisons, or verifying any claim that may have changed since training cutoff.
---

# Web Research Skill

Answers questions that depend on information newer or more specific than training data,
and shows its work so the answer can be trusted or challenged.

## Usage

Trigger this skill when the user asks to "look up", "check the latest", "what version is",
"verify that", "is that still true", or otherwise poses a question whose answer turns on
current external facts.

For anything beyond a single lookup, dispatch the **`web-researcher`** agent rather than
searching inline — it runs both paths and applies the verification discipline below.

## The two paths

**Path 1 — Gemini Flash (Vertex AI, Google Search grounded):**

```bash
${CLAUDE_PLUGIN_ROOT}/scripts/gemini-search.sh "<one focused question>"
```

**Path 2 — native `WebSearch`, with `WebFetch` for primary sources.**

Run both. Their value is that they fail differently: Path 1 reaches Google's index with a
model that summarizes aggressively; Path 2 lets you read the actual page. Where they agree
with real citations, the answer is solid. Where they diverge, fetch the primary source and
let it decide.

## Rules that make the output trustworthy

- Never print a citation that did not come from a tool result in this session.
- The `--- sources ---` URLs from Path 1 are `vertexaisearch.cloud.google.com` **redirects**,
  not source URLs. Resolve them with `WebFetch` before citing, or cite the inline URLs from
  the model's prose instead.
- Date every time-sensitive fact. Versions, prices, and limits go stale.
- Report GA and pre-release (milestone/RC/snapshot) versions separately and label them.
- State contradictions between sources rather than averaging them away.
- Close with a confidence level that names what went unverified.

## Setup

Path 1 needs gcloud ADC and a project with the Vertex AI API enabled:

```bash
gcloud auth application-default login
gcloud config set project <your-project>          # or export GOOGLE_CLOUD_PROJECT
gcloud services enable aiplatform.googleapis.com
```

Tunable via `GEMINI_SEARCH_MODEL`, `GEMINI_SEARCH_LOCATION`, `GEMINI_SEARCH_TIMEOUT`.

If Path 1 is unavailable the skill still works — fall back to Path 2 alone and say so in
the report, since a single-path answer carries less weight than a cross-checked one.
