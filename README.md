# Plan Swarm: Spec-Driven Planning Skills & Agents

A disciplined swarm of role-based agents, deliberative panels, and adversarial validation gates that drive features, bug fixes, or refactors through a robust **spec → plan → execute → audit → commit** lifecycle. 

This repository packages the swarm for **Claude Code**, as both skills and subagents. For the Antigravity CLI (AGY CLI) packaging, see the sibling repository [ddobrin/plan-skills](https://github.com/ddobrin/plan-skills).

---

## 🚀 Quick Start & Installation

### 1. How to Install Skills in Claude Code
> 📖 See [plugins/plan/README.md](plugins/plan/README.md) for the complete skill reference.

In Claude Code, you add the repository to your plugin marketplace and install the relevant plugins:
```bash
/plugin marketplace add ddobrin/plan-skills-claude
/plugin install plan@plan-skills
/plugin install research@plan-skills   # optional, standalone web research
```

---

### 2. How to Install Agents in Claude Code
> 📖 See [plugins/plan/AGENTS.md](plugins/plan/AGENTS.md) for the subagent reference.

Subagents (agents) in Claude Code are packaged and distributed directly within the `plan` plugin. 

* **Installation:** Simply installing the `plan` plugin (as shown above using `/plugin install plan@plan-skills`) automatically makes these subagents available to Claude Code. No additional commands or directory copies are required.
* **Usage & Invocation:** Once installed, there are three ways to invoke a subagent:
  1. **Explicitly via the `Task` tool:** Set the `subagent_type` field to `plan:{name}` (e.g., `plan:supervisor`, `plan:architect`).
  2. **Automatically via Auto-Delegation:** The runtime automatically picks an agent when a user request matches the patterns/examples inside the agent's frontmatter description.
  3. **From the CLI:** Run `claude --agent {name}` to launch a single role directly.

---

## 📚 Documentation Directory

Explore the underlying documentation for details on individual roles, lifecycle stages, and deliverables:

* **Planning Skills:** Complete guide to skills, artifacts, and lifecycle is documented in [plugins/plan/README.md](plugins/plan/README.md).
* **Planning Subagents:** Complete guide to subagents, frontmatter schema, and auto-delegation triggers is documented in [plugins/plan/AGENTS.md](plugins/plan/AGENTS.md).
* **Research Plugin:** The standalone web-research agent and skill are documented in [plugins/research/README.md](plugins/research/README.md).


---

This is only an open source test set of skills - not an official Google project
