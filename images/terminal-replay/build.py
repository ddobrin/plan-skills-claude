#!/usr/bin/env python3
"""Build the terminal-replay GIF: one milestone as it looks in a Claude Code session.

    uvx --with pillow python3 images/terminal-replay/build.py [TRANSCRIPT]

TRANSCRIPT defaults to /tmp/swarm-e2e/transcript.json and is regenerated with
examples/e2e_demo.py when missing. Hook, gate, git, and test lines are copied verbatim
from that real run; the supervisor's narration lines are written for the replay.
Writes images/terminal-replay/{terminal.html, plan-swarm-terminal.gif, plan-swarm-terminal.png}.
"""
import json
import os
import subprocess
import sys
import textwrap

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(HERE, "..", "_build"))
import gifkit  # noqa: E402

W, H = 960, 600
COLS = 104
TRANSCRIPT = sys.argv[1] if len(sys.argv) > 1 else "/tmp/swarm-e2e/transcript.json"


def load():
    if not os.path.exists(TRANSCRIPT):
        subprocess.run([sys.executable, os.path.join(ROOT, "examples", "e2e_demo.py"),
                        os.path.dirname(TRANSCRIPT)], check=True)
    steps = json.load(open(TRANSCRIPT))
    for s in steps:
        s["output"] = s["output"].replace("/private/tmp/swarm-e2e/shop", "~/shop").replace(
            "/tmp/swarm-e2e/shop", "~/shop").replace("/tmp/swarm-e2e/origin.git", "origin.git")
    return steps


def out_of(steps, label, nth=0):
    hits = [s for s in steps if s["label"].startswith(label)]
    return hits[nth]["output"].strip()


def wrap(kind, text, first="", rest=""):
    lines = []
    for para in text.splitlines() or [""]:
        chunks = textwrap.wrap(para, COLS - len(first)) or [""]
        for chunk in chunks:
            lines.append([kind, (first if not lines else rest) + chunk])
    return lines


def beats(steps):
    o = lambda label, nth=0: out_of(steps, label, nth)  # noqa: E731
    first_line = lambda label, nth=0: o(label, nth).splitlines()[0]  # noqa: E731
    B = []

    def beat(lines, dur=900, typing=None):
        B.append(dict(lines=lines, dur=dur, typing=typing))

    beat([["dim", "~/shop $ claude --agent plan:supervisor"]], 700)
    beat(wrap("hook", o("SessionStart hook"), "  ⎿  SessionStart · ", "      "), 1500)
    beat([["sup", "⏺ Enforcement is active. No milestones yet. What would you like to change?"]], 1300)
    beat([["you", "› "]], 120, typing="Login gets brute-forced. Limit failed attempts per account and per IP.")
    beat([["agent", "⏺ plan:product-owner(intent mode)"],
          ["out", "  ⎿  Wrote plans/intents/2026-09-25-login-rate-limit.md"]], 1200)
    beat([["sup", "⏺ Proposed tier: routine. To accept the intent, type:"],
          ["phrase", "    approve intent login-rate-limit as login-rate-limit"]], 1500)
    beat([["you", "› "]], 100, typing="approve intent login-rate-limit as login-rate-limit")
    beat(wrap("ok", o("you type: approve intent"), "  ⎿  ", "     "), 1700)
    beat([["tool", "⏺ Bash(git switch -c swarm/login-rate-limit)"], ["out", "  ⎿  " + o("supervisor: create the milestone branch")],
          ["agent", "⏺ plan:auditor(commit plans/ · approve intent)"], ["out", "  ⎿  " + first_line("auditor: artifact commit")],
          ["agent", "⏺ Explore(codebase context for intent.md)"], ["out", "  ⎿  Appended ## Codebase context"]], 1600)
    beat([["agent", "⏺ plan:product-owner(Grill Loop → spec.md)"],
          ["out", "  ⎿  1. After how many failures should an account lock, and for how long?"],
          ["out", "     2. Should the lockout message reveal that the account exists?"]], 1500)
    beat([["you", "› "]], 90, typing="5 in 15 min, lock 15 min. Never reveal accounts.")
    beat([["out", "  ⎿  Wrote spec.md (3 scenarios, Policy Concerns: none open)"],
          ["sup", "⏺ Offered: spec-deliberator, spec-validator (tier routine). You declined; logged in usage.md."],
          ["sup", "⏺ To accept the spec, type:"], ["phrase", "    approve spec login-rate-limit"]], 1700)
    beat([["you", "› "]], 100, typing="approve spec login-rate-limit")
    beat([["ok", "  ⎿  approval recorded · " + first_line("auditor: artifact commit", 1)],
          ["agent", "⏺ plan:architect(plan.md)"], ["out", "  ⎿  Wrote plan.md: Group 1 (1.A, 1.B in parallel) → Group 2 (2.A)"],
          ["tool", "⏺ Bash(tier.py --stage plan)"],
          ["warn", "  ⎿  tier: critical (keyword 'password', path src/shop/auth/attempts.py matches **/auth/**)"]], 2000)
    beat([["sup", "⏺ Tier raised to critical; validators recommended. Review spec.md and plan.md, then type:"],
          ["phrase", "    approve plan login-rate-limit"]], 1400)
    beat([["you", "› "]], 100, typing="approve plan login-rate-limit")
    beat([["ok", "  ⎿  approval recorded · Tier: critical · engineers unblocked"],
          ["agent", "⏺ plan:engineer(Task 1.A · worktree swarm-wip/login-rate-limit/1.A)"],
          ["agent", "⏺ plan:engineer(Task 1.B · worktree swarm-wip/login-rate-limit/1.B)"],
          ["out", "  ⎿  Both done (TDD). Squashed into swarm/login-rate-limit, not committed"],
          ["agent", "⏺ plan:auditor(verify group 1)"],
          ["out", "  ⎿  uvx pytest -q → " + o("auditor runs the tests from AGENTS.md") + " · Group 1 · Round 1 · PASS"]], 2200)
    beat([["tool", "⏺ Bash(git commit -m 'feat(login-rate-limit): attempt counter and lockout message')"]]
         + wrap("deny", o("auditor tries before your approval"), "  ⎿  ", "     "), 2300)
    beat([["sup", "⏺ The gate needs your approval for group 1. Type:"], ["phrase", "    approve commit login-rate-limit g1"]], 1200)
    beat([["you", "› "]], 100, typing="approve commit login-rate-limit g1")
    beat([["ok", "  ⎿  approval recorded · " + first_line("auditor: group commit (both git-hook layers pass)")],
          ["dim", "  …  group 2 the same way → " + first_line("auditor: group commit", 1)]], 2000)
    beat([["sup", "⏺ Both groups committed. To open the pull request, type:"], ["phrase", "    approve pr login-rate-limit"]], 1200)
    beat([["you", "› "]], 100, typing="approve pr login-rate-limit")
    push = o("supervisor: push (the pre-push hook checks every commit)").splitlines()
    beat([["ok", "  ⎿  approval recorded · " + first_line("auditor: commit the PR approval")],
          ["tool", "⏺ Bash(git push -u origin swarm/login-rate-limit)"], ["out", "  ⎿  " + push[-1].strip()],
          ["tool", "⏺ Bash(gh pr create …)"], ["out", "  ⎿  " + o("PR title (lib/prbody.py)")],
          ["ok", "  ⎿  CI ledger: " + o("CI ledger job (from templates/ci/plan-swarm.yml)")],
          ["sup", "⏺ PR is open. A code owner reviews and merges it on GitHub."]], 3000)
    beat([["dim", "  …  merged on GitHub by a code owner"],
          ["sup", "⏺ Every milestone for v1.0.0 is merged. To tag the release, type:"],
          ["phrase", "    approve release v1.0.0"]], 1300)
    beat([["you", "› "]], 100, typing="approve release v1.0.0")
    tag = o("supervisor: push the tag (you agreed)").splitlines()
    beat([["ok", "  ⎿  approval recorded"], ["tool", "⏺ Bash(git tag -a v1.0.0 -m 'Release v1.0.0')"],
          ["tool", "⏺ Bash(git push origin v1.0.0)"], ["out", "  ⎿  " + tag[-1].strip()],
          ["sup", "⏺ v1.0.0 is tagged. The product owner marks the release Shipped."]], 3600)
    return B


def fit(line):
    """Wrap a line wider than the terminal, indenting continuations under its text."""
    kind, text = line
    if kind == "phrase" or len(text) <= COLS:
        return [line]
    lead = len(text) - len(text.lstrip(" "))
    marker = text.lstrip(" ")[:3] if text.lstrip(" ")[:1] in "⎿⏺…" else ""
    indent = " " * (lead + len(marker))
    parts = textwrap.wrap(text.strip(), COLS - len(indent))
    return [[kind, (" " * lead) + parts[0]]] + [[kind, indent + p] for p in parts[1:]]


def frames(B):
    for b in B:
        b["lines"] = [piece for line in b["lines"] for piece in fit(line)]
    out, lines = [], []
    for b in B:
        if b["typing"]:
            text = b["typing"]
            for k in range(1, 5):
                out.append(dict(lines=lines + [["you", "› " + text[:round(len(text) * k / 4)] + "▌"]], dur=110))
            lines = lines + [["you", "› " + text]]
            out.append(dict(lines=lines, dur=500))
        else:
            for line in b["lines"]:
                lines = lines + [line]
            out.append(dict(lines=lines, dur=b["dur"]))
    out.append(dict(lines=lines, card=True, dur=4000))
    return out


HTML = r"""<!doctype html><html><head><meta charset="utf-8"><title>plan-swarm terminal replay</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
html,body{width:960px;height:600px;overflow:hidden;background:#e9e6df;font-family:-apple-system,BlinkMacSystemFont,"SF Pro Text",Inter,sans-serif}
#win{position:absolute;left:20px;top:16px;width:920px;height:542px;background:#16171b;border-radius:12px;overflow:hidden;box-shadow:0 14px 40px rgba(0,0,0,.28)}
#bar{height:34px;background:#24252b;display:flex;align-items:center;padding:0 14px;gap:8px}
#bar i{width:12px;height:12px;border-radius:50%;display:inline-block}
#bar span{flex:1;text-align:center;color:#9a9ca3;font-size:12.5px;margin-right:52px}
#term{position:absolute;top:34px;left:0;right:0;bottom:0;padding:12px 16px;font:13px/19.5px "SF Mono",ui-monospace,Menlo,monospace;color:#d7d8dc;overflow:hidden;display:flex;flex-direction:column;justify-content:flex-end}
.l{white-space:pre}
.dim{color:#7d808a}.sup{color:#eceef2}.you{color:#f3c56b}.agent{color:#8fb0ff}.tool{color:#c9cbd3}
.out{color:#9fa2ab}.ok{color:#6fd39b}.deny{color:#ff8a80}.warn{color:#f3c56b}.hook{color:#b8a6ff}
.phrase{color:#16171b;background:#f3c56b;display:inline-block;border-radius:4px;padding:0 6px;margin-left:30px}
#cap{position:absolute;left:24px;right:24px;bottom:12px;font-size:11.5px;color:#6b6f76;text-align:center}
#card{position:absolute;inset:0;display:none;align-items:center;justify-content:center;background:rgba(22,23,27,.78)}
#card div{background:#fff;border-radius:16px;padding:26px 32px;width:560px}
#card h1{font-size:25px;letter-spacing:-.01em;color:#1d1d1f}
#card p{color:#5f6368;font-size:14.5px;margin-top:8px;line-height:1.5}
#card code{display:inline-block;margin:12px 8px 0 0;font:13px "SF Mono",ui-monospace,Menlo,monospace;background:#16171b;color:#f3c56b;border-radius:7px;padding:6px 10px}
</style></head><body>
<div id="win"><div id="bar"><i style="background:#ff5f57"></i><i style="background:#febc2e"></i><i style="background:#28c840"></i>
<span>claude --agent plan:supervisor — ~/shop</span></div><div id="term"></div>
<div id="card"><div><h1>One milestone, six phrases</h1><p>The supervisor dispatched every role as a subagent. You typed the approvals; hooks refused everything else, and each approval shipped in the commit it authorized.</p><code>/plan:swarm-init</code><code>claude --agent plan:supervisor</code></div></div></div>
<div id="cap">Condensed from a real run of examples/e2e_demo.py: hook, gate, git, and test lines are verbatim; the supervisor's narration is illustrative.</div>
<script>
const FRAMES = __FRAMES__;
const P = new URLSearchParams(location.hash.slice(1));
const fr = FRAMES[Math.min(+P.get("f") || 0, FRAMES.length - 1)];
const esc = s => s.replace(/&/g,"&amp;").replace(/</g,"&lt;");
const term = document.getElementById("term");
term.innerHTML = fr.lines.slice(-24).map(([k, t]) => k === "phrase"
  ? `<div class="l"><span class="phrase">${esc(t.trim())}</span></div>` : `<div class="l ${k}">${esc(t)}</div>`).join("");
if (fr.card) document.getElementById("card").style.display = "flex";
</script></body></html>"""


def main():
    steps = load()
    fr = frames(beats(steps))
    page = os.path.join(HERE, "terminal.html")
    with open(page, "w", encoding="utf-8") as fh:
        fh.write(HTML.replace("__FRAMES__", json.dumps(fr)))
    images = gifkit.render_frames(page, [f"f={i}" for i in range(len(fr))], W, H)
    durations = [f["dur"] for f in fr]
    size = gifkit.save_gif(images, durations, os.path.join(HERE, "plan-swarm-terminal.gif"))
    still = max(i for i, f in enumerate(fr) if not f.get("card"))
    gifkit.save_png(images[still], os.path.join(HERE, "plan-swarm-terminal.png"))
    print(f"terminal: {len(images)} frames, {sum(durations) / 1000:.1f}s, {size / 1e6:.2f} MB")


if __name__ == "__main__":
    main()
