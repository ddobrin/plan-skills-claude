# Research Plugin

A web research specialist that resolves questions against **two independent search paths**
and reports which of its claims it actually verified.

Most wrong answers about the outside world are not hallucinations — they are confidently
stale facts. A version number, a rate limit, or a price that was true at training time reads
exactly like one that is true today. This plugin exists to make that difference visible.

---

## What's in it

| Component | Kind | Purpose |
|---|---|---|
| `web-researcher` | Agent | Runs both search paths, cross-checks them, returns a cited synthesis with a confidence line |
| `web-research` | Skill | The lookup discipline itself — when to use which path, and what makes output trustworthy |
| `scripts/gemini-search.sh` | Script | Calls Gemini Flash on Vertex AI with Google Search grounding |

---

## The two paths

| Path | Reaches | Fails by |
|---|---|---|
| **Gemini Flash** (Vertex AI, Google Search grounded) | Google's live index | Summarizing aggressively; returning redirect URLs instead of sources |
| **Native `WebSearch` / `WebFetch`** | Search results and the actual page text | Narrower result sets; no grounding pass |

They are used together because they fail *differently*. Agreement between them plus real
citations is a strong signal. Disagreement is itself the finding, and gets resolved by
fetching the primary source.

---

## Why an agent and not just a search call

The agent enforces the part that is easy to skip under time pressure:

- Every citation traces to a tool result from the same session — no reconstructed URLs
- Verified claims are reported separately from single-path assertions
- GA versions are distinguished from milestone/RC/snapshot releases
- Time-sensitive facts are dated
- Source conflicts are reported rather than averaged away
- Every report ends with a confidence level naming what went unverified

---

## Setup

Path 1 uses **gcloud Application Default Credentials** — no API key is created or stored.

```bash
gcloud auth application-default login
gcloud config set project <your-project>          # or export GOOGLE_CLOUD_PROJECT
gcloud services enable aiplatform.googleapis.com
```

Optional environment overrides:

| Variable | Default | Notes |
|---|---|---|
| `GOOGLE_CLOUD_PROJECT` | `gcloud config get-value project` | |
| `GEMINI_SEARCH_MODEL` | `gemini-3.6-flash` | Falls back to `gemini-2.5-flash` on 404 |
| `GEMINI_SEARCH_LOCATION` | `global` | `gemini-3.6-flash` is served **only** from `global`; regional endpoints 404 |
| `GEMINI_SEARCH_TIMEOUT` | `180` | Seconds per request |

Path 2 needs nothing. **If Path 1 is unavailable the agent still works** — it falls back to
native search alone and says so in the report, so a single-path answer is never silently
passed off as a cross-checked one.

---

## Usage

Ask naturally, and the agent's description should route the question to it:

```
What's the current GA version of Spring AI, and what broke since 1.0?
```

Or dispatch it explicitly:

```
Use the web-researcher agent to verify the published rate limit for <API>
```

Or bypass the agent for a raw grounded answer:

```bash
${CLAUDE_PLUGIN_ROOT}/scripts/gemini-search.sh "latest Spring AI GA version and release date"
```

Exit codes: `0` ok · `1` API call failed · `2` bad usage · `3` auth/config problem.

---

## Relationship to the other plugins

Deliberately standalone. The `plan` and `orchestrator` plugins carry no cloud dependency,
and folding research into them would hand every installer a gcloud requirement they may not
want. Install this one only if you want the Gemini-backed path.

It composes naturally with the lifecycle anyway: the research and discovery phases are where
external facts enter a spec, and an unverified version number that reaches a plan becomes an
unverified assumption in the build.
