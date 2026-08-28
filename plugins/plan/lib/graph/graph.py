#!/usr/bin/env python3
"""Single-source topology tooling for the plan swarm.

`graph.json` at the plugin root declares the swarm's nodes, edges, gates and node
contracts. This module is the only thing allowed to turn that declaration into a
diagram, and the only thing that checks the declaration against the skills on disk.

    python3 lib/graph/graph.py validate          # topology vs. filesystem
    python3 lib/graph/graph.py render ascii      # the lifecycle diagram
    python3 lib/graph/graph.py render mermaid    # the same graph, for docs
    python3 lib/graph/graph.py render svg        # themed inline SVG of the whole graph
    python3 lib/graph/graph.py sync              # rewrite generated blocks in the READMEs
    python3 lib/graph/graph.py sync --check      # non-zero exit if a README is stale

Stdlib only, no third-party imports: this has to run in whatever environment the
plugin is installed into.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = PLUGIN_ROOT.parents[1]
GRAPH_FILE = PLUGIN_ROOT / "graph.json"

BEGIN = "<!-- BEGIN GENERATED: lifecycle (python3 lib/graph/graph.py sync) -->"
END = "<!-- END GENERATED: lifecycle -->"


# --------------------------------------------------------------------------- model


def load(path: Path = GRAPH_FILE) -> dict:
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


def by_id(graph: dict) -> dict:
    return {n["id"]: n for n in graph["nodes"]}


def phases(graph: dict) -> list[tuple[str, list[dict]]]:
    """Nodes grouped by phase, preserving declaration order."""
    out: list[tuple[str, list[dict]]] = []
    for node in graph["nodes"]:
        if out and out[-1][0] == node["phase"]:
            out[-1][1].append(node)
        else:
            out.append((node["phase"], [node]))
    return out


# ------------------------------------------------------------------------ validate


def validate(graph: dict) -> list[str]:
    """Return a list of problems. Empty list means the declaration matches reality."""
    problems: list[str] = []
    nodes = by_id(graph)

    if len(nodes) != len(graph["nodes"]):
        problems.append("duplicate node id in graph.json")

    # edges point at real nodes
    for edge in graph["edges"]:
        for end in ("from", "to"):
            if edge[end] not in nodes:
                problems.append(f"edge {edge['from']} -> {edge['to']}: unknown node {edge[end]!r}")

    # every non-entry node is reachable
    targets = {e["to"] for e in graph["edges"]}
    for node in graph["nodes"]:
        if node["kind"] != "entry" and node["id"] not in targets:
            problems.append(f"node {node['id']!r} has no inbound edge — unreachable")

    # declared skills and agents exist on disk
    for node in graph["nodes"]:
        skill = node.get("skill")
        if skill and not (PLUGIN_ROOT / "skills" / skill / "SKILL.md").is_file():
            problems.append(f"node {node['id']!r}: skills/{skill}/SKILL.md not found")
        agent = node.get("agent")
        if agent and not (PLUGIN_ROOT / "agents" / f"{agent}.md").is_file():
            problems.append(f"node {node['id']!r}: agents/{agent}.md not found")
        for alt in node.get("alternatives", []):
            if not (PLUGIN_ROOT / "skills" / alt / "SKILL.md").is_file():
                problems.append(f"node {node['id']!r}: alternative skills/{alt}/SKILL.md not found")

    # panels: lens count matches n, and every lens is actually present in the prompt file
    for node in graph["nodes"]:
        panel = node.get("panel")
        if not panel:
            continue
        lenses = panel.get("lenses", [])
        if len(lenses) != panel.get("n"):
            problems.append(
                f"node {node['id']!r}: panel.n={panel.get('n')} but {len(lenses)} lenses declared"
            )
        if len(set(lenses)) != len(lenses):
            problems.append(f"node {node['id']!r}: duplicate lens name")
        prompt_path = PLUGIN_ROOT / panel["prompt_file"]
        if not prompt_path.is_file():
            problems.append(f"node {node['id']!r}: {panel['prompt_file']} not found")
            continue
        text = prompt_path.read_text(encoding="utf-8")
        for lens in lenses:
            if lens not in text:
                problems.append(
                    f"node {node['id']!r}: lens {lens!r} declared in graph.json "
                    f"but absent from {panel['prompt_file']}"
                )
        # the defect this whole exercise exists to prevent
        if "three times, unchanged" in text or "three times**, unchanged" in text:
            problems.append(
                f"node {node['id']!r}: {panel['prompt_file']} still dispatches identical "
                f"prompts — correlated skeptics manufacture false corroboration"
            )

    # write contracts: only the nodes allowed to touch source may declare it
    source_writers = {"engineer", "simplifier"}
    for node in graph["nodes"]:
        if "<repo source>" in node.get("writes", []) and node["id"] not in source_writers:
            problems.append(f"node {node['id']!r} declares it writes repository source")
        if "git commit" in node.get("writes", []) and node.get("held_by") != "starter":
            problems.append(f"node {node['id']!r} declares it commits but is not held by starter")

    # gates reference real nodes of the right kind
    for gate in graph["gates"]:
        node = nodes.get(gate["node"])
        if node is None:
            problems.append(f"gate {gate['id']!r}: unknown node {gate['node']!r}")
        elif node["kind"] != "human-gate":
            problems.append(f"gate {gate['id']!r}: node {gate['node']!r} is not a human-gate")

    return problems


# -------------------------------------------------------------------------- render


def _panel_line(node: dict) -> str:
    lenses = " · ".join(node["panel"]["lenses"])
    return f"[{node['panel']['n']}-lens {node['panel']['gate']} gate: {lenses}]"


def render_ascii(graph: dict) -> str:
    lines: list[str] = ["```text", " IDEA"]
    for phase, group in phases(graph):
        for node in group:
            kind = node["kind"]
            if kind == "entry":
                continue
            if kind == "human-gate":
                lines.append("  |")
                lines.append(f"  v  Phase {phase}  *** {node['label']} *** -- {node['sublabel']}")
                continue
            if kind == "terminal":
                lines.append("  |")
                lines.append(f"  v  Phase {phase}  {node['label']} -- {node['sublabel']}")
                continue
            if kind == "panel":
                lines.append(f"  |            === GATE {node['label']} " + _panel_line(node))
                lines.append(f"  |                 -> {node['writes'][0]}")
                continue
            prefix = "  |            " if node.get("optional") or kind in ("deliberation", "renderer") else "  v  Phase %-2s  " % phase
            tag = ""
            if node.get("optional"):
                tag = "(optional) "
            if kind == "deliberation":
                tag = "(optional) " if node.get("optional") else ""
            if node.get("optional") or kind in ("deliberation", "renderer"):
                lines.append(f"{prefix}+- {tag}{node['label']} -- {node['sublabel']}")
            else:
                lines.append("  |")
                lines.append(f"{prefix}{node['label']} -- {node['sublabel']}")
            if node.get("fanout"):
                fo = node["fanout"]
                lines.append(
                    f"  |               fan-out over {fo['over']}, "
                    f"max {fo['max_concurrent']} concurrent, {fo['disjoint']}-disjoint"
                )

    # cycles are edges that point backwards; they read badly on a spine, so list them
    order = {n["id"]: i for i, n in enumerate(graph["nodes"])}
    back = [e for e in graph["edges"] if order[e["to"]] < order[e["from"]]]
    if back:
        lines.append("")
        lines.append(" feedback edges (cycles):")
        for e in back:
            label = f" — {e['label']}" if e.get("label") else ""
            lines.append(f"   {e['from']} -> {e['to']}   when: {e['when']}{label}")
    lines.append("```")
    return "\n".join(lines)


_MERMAID_SHAPE = {
    "entry": ("([", "])"),
    "role": ("[", "]"),
    "panel": ("{{", "}}"),
    "deliberation": ("[/", "/]"),
    "human-gate": ("[[", "]]"),
    "renderer": ("(", ")"),
    "terminal": ("([", "])"),
}


def render_mermaid(graph: dict) -> str:
    lines = ["```mermaid", "flowchart TD"]
    for node in graph["nodes"]:
        open_s, close_s = _MERMAID_SHAPE[node["kind"]]
        label = node["label"]
        if node["kind"] == "panel":
            label += "<br/>" + " · ".join(node["panel"]["lenses"])
        if node.get("optional"):
            label += "<br/>(optional)"
        lines.append(f'  {node["id"].replace("-", "_")}{open_s}"{label}"{close_s}')
    lines.append("")
    for edge in graph["edges"]:
        src = edge["from"].replace("-", "_")
        dst = edge["to"].replace("-", "_")
        text = edge.get("label") or edge["when"]
        arrow = "-.->" if edge["when"] == "optional" else "-->"
        lines.append(f'  {src} {arrow}|"{text}"| {dst}')
    lines.append("")
    lines.append("  classDef gate fill:#f6eedc,stroke:#8a5a12,stroke-width:2px;")
    lines.append("  classDef panel fill:#e0eff2,stroke:#0e7385,stroke-width:2px;")
    gate_ids = ",".join(n["id"].replace("-", "_") for n in graph["nodes"] if n["kind"] == "human-gate")
    panel_ids = ",".join(n["id"].replace("-", "_") for n in graph["nodes"] if n["kind"] == "panel")
    if gate_ids:
        lines.append(f"  class {gate_ids} gate;")
    if panel_ids:
        lines.append(f"  class {panel_ids} panel;")
    lines.append("```")
    return "\n".join(lines)



# ------------------------------------------------------------------------ svg

ROW_H = 66
SPINE_CX, SPINE_W = 300, 232
BRANCH_CX, BRANCH_W = 578, 208
BOX_H = 40
TOP, BOTTOM_PAD = 26, 30
WIDTH = 760

_SVG_CLASS = {
    "entry": "n-entry", "role": "n-role", "panel": "n-panel",
    "deliberation": "n-delib", "human-gate": "n-gate",
    "renderer": "n-render", "terminal": "n-term",
}


def _layout(graph: dict) -> tuple[dict, list[dict], list[dict]]:
    """Deterministic two-lane layout: a spine of required nodes, optional nodes to the right."""
    nodes = by_id(graph)
    spine = [n for n in graph["nodes"] if not n.get("optional")]
    branch = [n for n in graph["nodes"] if n.get("optional")]

    pos: dict[str, dict] = {}
    for row, node in enumerate(spine):
        pos[node["id"]] = {"row": row, "cx": SPINE_CX, "w": SPINE_W,
                           "y": TOP + row * ROW_H, "lane": "spine"}

    # an optional node sits on the row of the spine node that feeds it
    for node in branch:
        feeder = next((e["from"] for e in graph["edges"]
                       if e["to"] == node["id"] and e["from"] in pos), None)
        row = pos[feeder]["row"] if feeder else 0
        pos[node["id"]] = {"row": row, "cx": BRANCH_CX, "w": BRANCH_W,
                           "y": TOP + row * ROW_H, "lane": "branch"}
    return pos, spine, branch


def render_svg(graph: dict) -> str:
    pos, spine, _branch = _layout(graph)
    order = {n["id"]: i for i, n in enumerate(graph["nodes"])}
    height = TOP + (len(spine) - 1) * ROW_H + BOX_H + BOTTOM_PAD

    o: list[str] = []
    a = o.append
    a(f'<svg class="graphsvg" viewBox="0 0 {WIDTH} {height}" role="img" '
      f'aria-label="The complete plan swarm topology generated from graph.json: '
      f'{len(graph["nodes"])} nodes and {len(graph["edges"])} edges. A vertical spine of required '
      f'nodes runs from request to release, optional nodes branch to the right, and feedback '
      f'edges arc back on the left.">')
    a('<defs>')
    a('<marker id="gh" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" '
      'orient="auto-start-reverse"><path d="M0,1 L9,5 L0,9 z" fill="currentColor"/></marker>')
    a('</defs>')

    # --- edges first, so nodes paint over them
    back_slot = 0
    for e in graph["edges"]:
        src, dst = pos[e["from"]], pos[e["to"]]
        forward = order[e["to"]] > order[e["from"]]
        optional = e["when"] == "optional" or graph_nodes_optional(graph, e)
        cls = "e-opt" if optional else "e-fwd"

        if not forward:
            # feedback: arc out to the left of the spine
            back_slot += 1
            off = 22 + back_slot * 15
            x = SPINE_CX - SPINE_W / 2
            y1, y2 = src["y"] + BOX_H / 2, dst["y"] + BOX_H / 2
            a(f'<path class="e-back" d="M{x:.0f},{y1:.0f} C{x-off:.0f},{y1:.0f} '
              f'{x-off:.0f},{y2:.0f} {x:.0f},{y2:.0f}" marker-end="url(#gh)"/>')
            label = e.get("label") or e["when"]
            a(f'<text class="e-lbl-back" x="{x-off-4:.0f}" y="{(y1+y2)/2:.0f}" '
              f'text-anchor="end">{_esc(label)}</text>')
            continue

        if src["lane"] == dst["lane"] == "spine" and dst["row"] == src["row"] + 1:
            x = SPINE_CX
            a(f'<line class="{cls}" x1="{x}" y1="{src["y"]+BOX_H}" x2="{x}" '
              f'y2="{dst["y"]}" marker-end="url(#gh)"/>')
            if e.get("label"):
                a(f'<text class="e-lbl" x="{x+8}" y="{src["y"]+BOX_H+16}">{_esc(e["label"])}</text>')
        else:
            x1 = src["cx"] + (src["w"] / 2 if dst["cx"] > src["cx"] else -src["w"] / 2)
            x2 = dst["cx"] + (-dst["w"] / 2 if dst["cx"] > src["cx"] else dst["w"] / 2)
            y1, y2 = src["y"] + BOX_H / 2, dst["y"] + BOX_H / 2
            mx = (x1 + x2) / 2
            a(f'<path class="{cls}" d="M{x1:.0f},{y1:.0f} C{mx:.0f},{y1:.0f} '
              f'{mx:.0f},{y2:.0f} {x2:.0f},{y2:.0f}" marker-end="url(#gh)"/>')

    # --- nodes
    for node in graph["nodes"]:
        p = pos[node["id"]]
        x = p["cx"] - p["w"] / 2
        a(f'<rect class="{_SVG_CLASS[node["kind"]]}" x="{x:.0f}" y="{p["y"]}" '
          f'width="{p["w"]}" height="{BOX_H}" rx="2"/>')
        a(f'<text class="n-lbl" x="{p["cx"]}" y="{p["y"]+17}" text-anchor="middle">'
          f'{_esc(node["label"])}</text>')
        sub = node["sublabel"]
        if node.get("panel"):
            sub = " · ".join(node["panel"]["lenses"])
        a(f'<text class="n-sub" x="{p["cx"]}" y="{p["y"]+31}" text-anchor="middle">'
          f'{_esc(sub)}</text>')

    a('</svg>')
    return "\n".join(o)


def graph_nodes_optional(graph: dict, edge: dict) -> bool:
    nodes = by_id(graph)
    return bool(nodes[edge["to"]].get("optional"))


def _esc(t: str) -> str:
    return (t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
             .replace('"', "&quot;"))

# ---------------------------------------------------------------------------- sync

TARGETS = [
    (PLUGIN_ROOT / "README.md", "ascii"),
    (PLUGIN_ROOT / "agents" / "README.md", "ascii"),
    (REPO_ROOT / "docs" / "updated" / "skills-conformance.html", "svg"),
]


def _block(graph: dict, flavor: str) -> str:
    body = {"ascii": render_ascii, "mermaid": render_mermaid, "svg": render_svg}[flavor](graph)
    return (
        f"{BEGIN}\n"
        f"<!-- graph_version: {graph['graph_version']} — edit graph.json, then run sync. -->\n\n"
        f"{body}\n\n{END}"
    )


def sync(graph: dict, check: bool = False) -> int:
    stale: list[str] = []
    for path, flavor in TARGETS:
        if not path.is_file():
            stale.append(f"{path}: missing")
            continue
        text = path.read_text(encoding="utf-8")
        if BEGIN not in text or END not in text:
            stale.append(f"{path}: no generated block — add the BEGIN/END markers")
            continue
        new_block = _block(graph, flavor)
        pattern = re.compile(re.escape(BEGIN) + r".*?" + re.escape(END), re.DOTALL)
        updated = pattern.sub(lambda _m: new_block, text)
        if updated == text:
            continue
        if check:
            stale.append(f"{path}: out of date")
        else:
            path.write_text(updated, encoding="utf-8")
            print(f"updated {path.relative_to(REPO_ROOT)}")
    if stale:
        for line in stale:
            print(f"STALE  {line}", file=sys.stderr)
        return 1
    if check:
        print("all generated blocks are up to date")
    return 0


# ----------------------------------------------------------------------------- cli


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("validate", help="check graph.json against the skills on disk")
    r = sub.add_parser("render", help="print a diagram")
    r.add_argument("flavor", choices=["ascii", "mermaid", "svg"])
    s = sub.add_parser("sync", help="rewrite the generated blocks in the READMEs")
    s.add_argument("--check", action="store_true", help="exit non-zero if a block is stale")
    args = parser.parse_args(argv)

    graph = load()

    if args.cmd == "validate":
        problems = validate(graph)
        if problems:
            print(f"{len(problems)} problem(s):", file=sys.stderr)
            for p in problems:
                print(f"  - {p}", file=sys.stderr)
            return 1
        n = len(graph["nodes"])
        panels = sum(1 for x in graph["nodes"] if x["kind"] == "panel")
        gates = sum(1 for x in graph["nodes"] if x["kind"] == "human-gate")
        print(f"graph.json OK — {n} nodes, {len(graph['edges'])} edges, {panels} lens-partitioned panels, {gates} human gates")
        return 0

    if args.cmd == "render":
        print({"ascii": render_ascii, "mermaid": render_mermaid, "svg": render_svg}[args.flavor](graph))
        return 0

    return sync(graph, check=args.check)


if __name__ == "__main__":
    raise SystemExit(main())
