#!/usr/bin/env python3
"""UserPromptSubmit hook: turn a human approval phrase into a single-use nonce.

The whole prompt must be exactly one of (case-insensitive):

    approve intent  <slug> as <milestone>
    approve spec    <milestone>
    approve plan    <milestone> [tier=routine|elevated|critical]
    approve commit  <milestone> g<n>
    approve pr      <milestone>
    approve release <version>

On a match it mints a nonce bound to the current HEAD (single use, expires after
approvals.nonce_ttl_minutes), appends a row to the milestone's approvals.md, and
returns additionalContext saying what was recorded. Any other prompt passes
through untouched. The hook never blocks a prompt.

Only real user prompts fire UserPromptSubmit, so an agent cannot approve its own
work. lib/gate.py consumes the nonce before the matching git operation.
"""
import datetime as dt
import glob
import json
import secrets
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import swarmdoc  # noqa: E402
import swarmgit as sg  # noqa: E402

M = sg.MONIKER
VERSION = r"v?\d+\.\d+\.\d+[0-9A-Za-z.+-]*"
GRAMMAR = [
    ("intent", re.compile(rf"approve intent ({M}) as ({M})", re.I)),
    ("spec", re.compile(rf"approve spec ({M})", re.I)),
    ("plan", re.compile(rf"approve plan ({M})(?: tier=(routine|elevated|critical))?", re.I)),
    ("commit", re.compile(rf"approve commit ({M}) g(\d+)", re.I)),
    ("pr", re.compile(rf"approve pr ({M})", re.I)),
    ("release", re.compile(rf"approve release ({VERSION})", re.I)),
]
NEXT_STEP = {
    "intent": "create branch swarm/{m} (pr mode), move the intent into the milestone, and commit plans/",
    "spec": "commit spec.md and its gate reports (plans/ paths only)",
    "plan": "commit the plan (plans/ paths only), then dispatch engineers",
    "commit": "have the auditor create the group commit",
    "pr": "push swarm/{m} and open the pull request",
    "release": "create the annotated tag (and push it if the user agrees)",
}


def parse(prompt):
    text = " ".join(prompt.strip().split())
    for kind, pattern in GRAMMAR:
        m = pattern.fullmatch(text)
        if not m:
            continue
        g = m.groups()
        if kind == "intent":
            return {"kind": kind, "slug": g[0].lower(), "moniker": g[1].lower()}
        if kind == "plan":
            return {"kind": kind, "moniker": g[0].lower(), "tier": (g[1] or "").lower()}
        if kind == "commit":
            return {"kind": kind, "moniker": g[0].lower(), "group": int(g[1])}
        if kind == "release":
            return {"kind": kind, "version": g[0]}
        return {"kind": kind, "moniker": g[0].lower()}
    return None


def proposed_tier(root, moniker):
    for name in ("plan.md", "intent.md"):
        path = os.path.join(sg.milestone_dir(root, moniker), name)
        try:
            with open(path, encoding="utf-8") as fh:
                m = re.search(r"Risk tier \(proposed\)\W*(routine|elevated|critical)", fh.read(), re.I)
        except OSError:
            continue
        if m:
            return m.group(1).lower()
    return ""


def record(approval, root):
    """Mint the nonce and write the ledger row. Returns a message for the session."""
    cfg = swarmdoc.load_config(root)
    store = sg.store_dir(root)
    if not store:
        return "Approval NOT recorded: this directory is not a git repository."
    kind, moniker = approval["kind"], approval.get("moniker")

    if kind == "intent":
        found = glob.glob(os.path.join(root, "plans", "intents", f"*{approval['slug']}.md"))
        if not found and not os.path.exists(os.path.join(sg.milestone_dir(root, moniker), "intent.md")):
            return f"Approval NOT recorded: no intent file matching plans/intents/*{approval['slug']}.md."
    elif kind != "release" and not os.path.isdir(sg.milestone_dir(root, moniker)):
        return f"Approval NOT recorded: plans/active_milestones/{moniker}/ does not exist."

    tier = approval.get("tier") or ""
    if kind == "plan" and not tier:
        tier = proposed_tier(root, moniker)
    if kind in ("commit", "pr") and moniker:
        tier = sg.confirmed_tier(root, moniker)

    head_sha = sg.head(root)
    if not head_sha:
        return "Approval NOT recorded: the repository has no commits yet."
    t = sg.now()
    ttl = cfg["approvals"]["nonce_ttl_minutes"]
    record = {
        "kind": kind, "moniker": moniker, "group": approval.get("group"),
        "version": approval.get("version"), "slug": approval.get("slug"),
        "tier": tier, "mode": cfg["delivery"]["mode"], "head": head_sha,
        "branch": sg.branch(root), "who": sg.user_email(root),
        "created": sg.iso(t), "expires": sg.iso(t + dt.timedelta(minutes=ttl)),
        "id": "n_" + secrets.token_hex(6),
    }
    # Ledger first: an approval that cannot be recorded must not become usable.
    ledger = sg.append_ledger(root, moniker if kind != "release" else None, {
        "when": record["created"], "who": record["who"], "kind": kind,
        "milestone": moniker or approval.get("version"), "group": approval.get("group") or "",
        "tier": tier, "mode": record["mode"], "head": head_sha[:12], "nonce": record["id"],
    })
    # Stage the ledger so its row ships inside the commit it authorizes (CI and the
    # pre-push hook match each commit's parent against these rows).
    sg.git("add", "--", ledger, cwd=root)
    nonce = sg.mint_nonce(store, record)
    label = kind + (f" {moniker}" if moniker else f" {approval['version']}")
    label += f" g{approval['group']}" if approval.get("group") else ""
    tier_note = f" Tier: {tier}." if tier else ""
    return (f"plan-swarm: approval recorded for {label} (nonce {nonce['id']}, valid once until "
            f"{nonce['expires'][11:16]} UTC while HEAD stays at {nonce['head'][:12]}).{tier_note} "
            f"Next: {NEXT_STEP[kind].format(m=moniker)}.")


def main():
    try:
        event = json.load(sys.stdin)
    except ValueError:
        return 0
    if not isinstance(event, dict) or event.get("hook_event_name", "UserPromptSubmit") != "UserPromptSubmit":
        return 0
    root = sg.repo_root(event.get("cwd"))
    store = sg.store_dir(root)
    if store:
        sg.touch_heartbeat(store, last_prompt=sg.iso(sg.now()))
    approval = parse(event.get("prompt") or "")
    if not approval:
        return 0
    try:
        message = record(approval, root)
    except swarmdoc.SwarmDocError as err:
        message = f"Approval NOT recorded: plans/swarm.md is invalid ({err}). Fix it and type the phrase again."
    except Exception as err:  # never mint silently: report and record nothing usable
        message = f"Approval NOT recorded: {type(err).__name__}: {err}"
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "UserPromptSubmit", "additionalContext": message}}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
