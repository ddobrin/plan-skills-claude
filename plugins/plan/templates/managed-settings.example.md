# Managed settings for the plan swarm (for platform teams)

The plan swarm's approval gate runs as a plugin hook. If your organization sets `allowManagedHooksOnly` or `disableAllHooks`, plugin hooks never run: the supervisor detects this ("enforcement off") and refuses gated steps, but nothing is enforced until the gate is adopted as a managed hook.

To keep enforcement with managed-only hooks, install the plugin's `lib/` directory at a fixed path on developer machines (for example `/opt/plan-swarm/lib/`) and add the three hooks to your managed settings. Paths below are examples.

```json managed-settings-example
{
  "allowManagedHooksOnly": true,
  "hooks": {
    "SessionStart": [
      { "hooks": [ { "type": "command", "command": "python3 /opt/plan-swarm/lib/health.py" } ] }
    ],
    "UserPromptSubmit": [
      { "hooks": [ { "type": "command", "command": "python3 /opt/plan-swarm/lib/approve.py" } ] }
    ],
    "PreToolUse": [
      {
        "matcher": "Bash|Write|Edit|MultiEdit|NotebookEdit|Agent|Task",
        "hooks": [ { "type": "command", "command": "python3 /opt/plan-swarm/lib/gate.py" } ]
      }
    ]
  }
}
```

The hooks are inactive in repositories without `plans/swarm.md`, so installing them fleet-wide does not affect other projects. Keep the managed copy in step with the plugin version your teams use.
