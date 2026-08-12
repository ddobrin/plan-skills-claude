#!/usr/bin/env bash
# gemini-search.sh — run a research query through Gemini Flash on Vertex AI with Google
# Search grounding. Backs the `web-researcher` agent and the `web-research` skill.
#
#   gemini-search.sh "what changed in postgres 18"
#   printf '%s' "$query" | gemini-search.sh
#
# Auth is gcloud Application Default Credentials — no API key is stored anywhere.
#
# Configuration (all optional):
#   GOOGLE_CLOUD_PROJECT   GCP project; defaults to `gcloud config get-value project`
#   GEMINI_SEARCH_MODEL    model id; defaults to gemini-3.6-flash
#   GEMINI_SEARCH_LOCATION Vertex location; defaults to global
#   GEMINI_SEARCH_TIMEOUT  per-request seconds; defaults to 180
#
# Note: gemini-3.6-flash is served only from the `global` location. Regional endpoints
# such as us-central1 return 404 for it, which is why `global` is the default here.
#
# Exit codes: 0 ok · 1 API call failed · 2 bad usage · 3 auth/config problem

set -uo pipefail

MODEL="${GEMINI_SEARCH_MODEL:-gemini-3.6-flash}"
FALLBACK="gemini-2.5-flash"
LOCATION="${GEMINI_SEARCH_LOCATION:-global}"
TIMEOUT="${GEMINI_SEARCH_TIMEOUT:-180}"

for bin in gcloud curl python3; do
  command -v "$bin" >/dev/null 2>&1 || {
    echo "gemini-search: required command '$bin' not found on PATH." >&2
    exit 3
  }
done

if [ "$#" -gt 0 ]; then QUERY="$*"; else QUERY="$(cat)"; fi
if [ -z "${QUERY//[[:space:]]/}" ]; then
  echo "usage: gemini-search.sh <query>   (or pipe the query on stdin)" >&2
  exit 2
fi

PROJECT="${GOOGLE_CLOUD_PROJECT:-$(gcloud config get-value project 2>/dev/null)}"
if [ -z "$PROJECT" ] || [ "$PROJECT" = "(unset)" ]; then
  echo "gemini-search: no GCP project configured." >&2
  echo "Set one with: gcloud config set project <id>   (or export GOOGLE_CLOUD_PROJECT)" >&2
  exit 3
fi

TOKEN="$(gcloud auth print-access-token 2>/dev/null)"
if [ -z "$TOKEN" ]; then
  echo "gemini-search: could not get a gcloud access token." >&2
  echo "Run: gcloud auth application-default login" >&2
  exit 3
fi

PREAMBLE='Use Google Search to answer this. Rules: cite every non-obvious claim with an inline source URL; if sources disagree, say so explicitly; if you cannot verify something, label it "unverified" rather than guessing; prefer primary sources (official docs, release notes, filings) over blog summaries; note the date of time-sensitive facts. Be concise and factual.'

REQ="$(QUERY="$QUERY" PREAMBLE="$PREAMBLE" python3 -c '
import json, os
print(json.dumps({
    "contents": [{"role": "user", "parts": [{"text": os.environ["PREAMBLE"] + "\n\n" + os.environ["QUERY"]}]}],
    "tools": [{"googleSearch": {}}],
}))')"

RESP="$(mktemp -t gemini-search)"
trap 'rm -f "$RESP"' EXIT

host_for() {
  if [ "$LOCATION" = "global" ]; then
    echo "https://aiplatform.googleapis.com"
  else
    echo "https://${LOCATION}-aiplatform.googleapis.com"
  fi
}

call_model() {
  local model="$1"
  curl -s --max-time "$TIMEOUT" -o "$RESP" -w '%{http_code}' -X POST \
    -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
    "$(host_for)/v1/projects/${PROJECT}/locations/${LOCATION}/publishers/google/models/${model}:generateContent" \
    -d "$REQ" 2>/dev/null
}

CODE="$(call_model "$MODEL")"
USED="$MODEL"
if [ "$CODE" = "404" ] && [ "$MODEL" != "$FALLBACK" ]; then
  echo "gemini-search: model '$MODEL' not found at '$LOCATION' — falling back to $FALLBACK" >&2
  CODE="$(call_model "$FALLBACK")"
  USED="$FALLBACK"
fi

if [ "$CODE" != "200" ]; then
  echo "gemini-search: request failed (HTTP $CODE) for project '$PROJECT'" >&2
  python3 -c '
import json, sys
try:
    print("  " + str(json.load(open(sys.argv[1])).get("error", {}).get("message", "no message")), file=sys.stderr)
except Exception:
    print("  (unparseable response)", file=sys.stderr)
' "$RESP"
  case "$CODE" in
    401|403) echo "  Token may be expired, or the Vertex AI API may not be enabled on this project." >&2
             echo "  Try: gcloud auth application-default login" >&2
             echo "       gcloud services enable aiplatform.googleapis.com --project=$PROJECT" >&2 ;;
  esac
  exit 1
fi

printf '=== model: %s (Vertex %s, Google Search grounded) ===\n' "$USED" "$LOCATION"
python3 -c '
import json, sys

data = json.load(open(sys.argv[1]))
cands = data.get("candidates") or []
if not cands:
    print("No answer returned. Prompt feedback: " + json.dumps(data.get("promptFeedback", {})))
    sys.exit(0)

cand = cands[0]
text = "".join(p.get("text", "") for p in cand.get("content", {}).get("parts", [])).strip()
print(text if text else "(empty response)")

gm = cand.get("groundingMetadata") or {}
chunks = gm.get("groundingChunks") or []
if chunks:
    print("\n--- sources (redirect URLs; resolve before citing) ---")
    for ch in chunks:
        web = ch.get("web") or {}
        print("- %s\n  %s" % (web.get("title") or web.get("domain") or "(untitled)", web.get("uri", "")))

queries = gm.get("webSearchQueries") or []
if queries:
    print("\n--- searches run: " + "; ".join(queries))

reason = cand.get("finishReason")
if reason and reason not in ("STOP", "FINISH_REASON_STOP"):
    print("\n[warning] finishReason=%s — answer may be truncated." % reason)
' "$RESP"
