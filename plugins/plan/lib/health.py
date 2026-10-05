#!/usr/bin/env python3
"""SessionStart hook and enforcement status for the plan-swarm control plane.

    health.py            SessionStart hook: heartbeat, refresh git-hook copy, report
    health.py --status   print enforcement status; exit 0 when active, 1 when not

Every plan-swarm hook refreshes the heartbeat in .git/plan-swarm/heartbeat.json.
Running `--status` through Claude Code's Bash tool fires the PreToolUse gate
first, so a fresh heartbeat proves the hooks are firing in this session. If an
administrator disabled plugin hooks (allowManagedHooksOnly / disableAllHooks),
the heartbeat goes stale and the supervisor refuses gated steps.
"""
import json
import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import swarmdoc  # noqa: E402
import swarmgit as sg  # noqa: E402

LIB = os.path.dirname(os.path.abspath(__file__))
HOOK_MARKER = "plan-swarm git hook"
BIN_FILES = ("gate.py", "swarmdoc.py", "swarmgit.py")


def plugin_version():
    try:
        with open(os.path.join(os.path.dirname(LIB), ".claude-plugin", "plugin.json"), encoding="utf-8") as fh:
            return json.load(fh).get("version", "unknown")
    except (OSError, ValueError):
        return "unknown"


HOOK_NAMES = ("pre-commit", "pre-merge-commit", "pre-push")


def hook_path(root, name="pre-commit"):
    path = sg.git("rev-parse", "--git-path", f"hooks/{name}", cwd=root)
    return os.path.join(root, path) if path and not os.path.isabs(path) else path


def git_hook_installed(root, name="pre-commit"):
    try:
        with open(hook_path(root, name), encoding="utf-8") as fh:
            return HOOK_MARKER in fh.read()
    except OSError:
        return False


def refresh_bin(root, store):
    """Copy the gate into the store so the git hook runs the current version."""
    dest = os.path.join(store, "bin")
    os.makedirs(dest, exist_ok=True)
    for name in BIN_FILES:
        shutil.copyfile(os.path.join(LIB, name), os.path.join(dest, name))


def status(root):
    info = {"swarm_repo": os.path.exists(os.path.join(root, swarmdoc.CONFIG_PATH))}
    if not info["swarm_repo"]:
        info["message"] = "not a plan-swarm repository (no plans/swarm.md); run the swarm-init skill"
        return info, False
    try:
        cfg = swarmdoc.load_config(root)
        info.update(config="valid", mode=cfg["delivery"]["mode"],
                    max_engineers=cfg["engineers"]["max_concurrent"],
                    max_path_a_rounds=cfg["audit"]["max_path_a_rounds"])
    except swarmdoc.SwarmDocError as err:
        info.update(config=f"INVALID: {err}")
    store = sg.store_dir(root)
    age = sg.age_seconds((sg.heartbeat(store) or {}).get("updated"))
    missing = [n for n in HOOK_NAMES if not git_hook_installed(root, n)]
    info.update(heartbeat_age_seconds=None if age is None else int(age),
                git_hook="installed" if not missing else "missing: " + ", ".join(missing),
                plugin_version=plugin_version())
    active = age is not None and age <= sg.HEARTBEAT_FRESH_SECONDS and info["config"] == "valid"
    info["enforcement"] = "active" if active else "OFF"
    if not active:
        info["message"] = ("enforcement off: plan-swarm hooks are not firing (organization settings may "
                           "block plugin hooks) or plans/swarm.md is invalid. Do not run gated steps.")
    return info, active


def session_start(event):
    root = sg.repo_root(event.get("cwd"))
    if not os.path.exists(os.path.join(root, swarmdoc.CONFIG_PATH)):
        return None
    store = sg.store_dir(root)
    sg.mark_active(store)
    sg.touch_heartbeat(store, started=sg.iso(sg.now()), session=event.get("session_id", ""),
                       source=event.get("source", ""), plugin_version=plugin_version())
    if any(git_hook_installed(root, n) for n in HOOK_NAMES):
        refresh_bin(root, store)
    info, active = status(root)
    if info.get("config") != "valid":
        return f"plan-swarm: plans/swarm.md is {info['config']}. Gated operations are refused until it is fixed."
    hook = "" if info["git_hook"] == "installed" else f" Git hooks {info['git_hook']}; run the swarm-init skill."
    return (f"plan-swarm {info['plugin_version']}: enforcement active. Delivery mode {info['mode']}, "
            f"up to {info['max_engineers']} engineers, Path A capped at {info['max_path_a_rounds']} rounds. "
            f"Commits, pushes, and tags need an exact approval phrase from the user.{hook}")


def main(argv):
    if "--status" in argv:
        info, active = status(sg.repo_root())
        print(json.dumps(info, indent=2))
        return 0 if active else 1
    try:
        event = json.load(sys.stdin)
    except ValueError:
        return 0
    message = session_start(event)
    if message:
        print(json.dumps({"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": message}}))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
