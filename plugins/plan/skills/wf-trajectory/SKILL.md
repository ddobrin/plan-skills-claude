---
name: wf-trajectory
description: Renders a completed Claude Code dynamic Workflow run (wf_<runId>.json) as a self-contained, offline HTML page with a run→phase→agent tree and a parallelism timeline. Trigger when the user asks to "visualize the workflow run", "render wf trajectory", "trace a workflow", or "show the last workflow execution".
---

# Workflow Trajectory Skill

Turns the telemetry the Workflow engine writes to disk into a browsable HTML
dashboard of a completed run — summary metrics, a collapsible run→phase→agent
tree with per-agent prompt/result previews and links to full transcripts, and a
CSS Gantt timeline that shows parallel fan-out.

Workflow-agnostic: works on any run from any workflow, retroactively.

## Usage

Run the generator with the project whose run you want to visualize as the working
directory — it locates the run from the current directory, not from its own location:

- Newest run: `python3 ${CLAUDE_PLUGIN_ROOT}/skills/wf-trajectory/generator.py`
- Specific run: `python3 ${CLAUDE_PLUGIN_ROOT}/skills/wf-trajectory/generator.py wf_<runId>`

Output is written to `./wf-trajectory/<runId>.html` (e.g.
`wf-trajectory/wf_c8873586-bae.html`; the dir is added to
`.gitignore`). Open it directly, or serve with
`python3 -m http.server --directory wf-trajectory` if your viewer blocks
`file://`.

## How it works

1. `wf_locator.py` finds the run file under `$CLAUDE_CONFIG_DIR` (or `~/.claude`)
   `/projects/<encoded-cwd>/*/workflows/`, matching the longest ancestor of the
   current directory.
2. `wf_model.py` parses `wf_<runId>.json` into a typed model.
3. `wf_timeline.py` computes the Gantt geometry from agent timings.
4. `wf_render.py` injects everything into `assets/template.html`.

See `references/data-contract.md` for the fields consumed and
`references/component-catalog.md` for the rendered surfaces.

## Tests

`python3 -m pytest ${CLAUDE_PLUGIN_ROOT}/skills/wf-trajectory/tests/ -v` (uses a checked-in run fixture; no network, no
`~/.claude` dependency).
