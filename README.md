# Plan Swarm: Spec-Driven Planning Skills & Agents for Claude Code

A disciplined swarm of role-based agents, deliberative panels, and adversarial validation gates that drive features, bug fixes, or refactors through a robust **spec → plan → execute → audit → commit** lifecycle.

This repository is built exclusively for **Claude Code** and **Claude models**. The swarm ships in two packagings inside a single plugin — skills (invoked via the Skill tool) and subagents (invoked via the Task tool, auto-delegation, or `claude --agent`) — with identical roles, workflows, and output files.

---

## 🚀 Quick Start & Installation

### 1. Install the Plugins
> 📖 See [plugins/plan/README.md](plugins/plan/README.md) for the complete skill reference.

Add this repository to your Claude Code plugin marketplace and install the plugins:
```bash
/plugin marketplace add ddobrin/plan-skills-claude
/plugin install plan@plan-skills
/plugin install orchestrator@plan-skills
```

The `plan` plugin bundles the skills, subagents, and shared libraries as one atomic unit — install it whole; the two families cross-reference each other and are not designed for partial installs.

### 2. Subagents Ship With the Plugin
> 📖 See [plugins/plan/agents/README.md](plugins/plan/agents/README.md) for the subagent reference.

Subagents are packaged and distributed directly within the `plan` plugin.

* **Installation:** Installing the `plan` plugin (as shown above) automatically makes the subagents available to Claude Code. No additional commands or directory copies are required.
* **Usage & Invocation:** Once installed, there are three ways to invoke a subagent:
  1. **Explicitly via the `Task` tool:** Set the `subagent_type` field to `plan:{name}` (e.g., `plan:supervisor`, `plan:architect`).
  2. **Automatically via Auto-Delegation:** The runtime automatically picks an agent when a user request matches the patterns/examples inside the agent's frontmatter description.
  3. **From the CLI:** Run `claude --agent {name}` to launch a single role directly.

### 3. Claude Models
The swarm runs on the Claude model family. Roles inherit the session's model by default; where a role benefits from a specific tier, the agent pins it explicitly in its frontmatter (e.g., the engineer pins `claude-sonnet-5`).

---

## 📚 Documentation Directory

Explore the underlying documentation for details on individual roles, lifecycle stages, and deliverables:

* **Planning Skills:** Complete guide to skills, artifacts, and lifecycle is documented in [plugins/plan/README.md](plugins/plan/README.md).
* **Planning Subagents:** Complete guide to subagents, frontmatter schema, and auto-delegation triggers is documented in [plugins/plan/agents/README.md](plugins/plan/agents/README.md).
* **Supervisor Orchestrator Plugin:** Documentation for the spec-driven coordinator and validation gates is in [plugins/orchestrator/README.md](plugins/orchestrator/README.md).
