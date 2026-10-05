#!/usr/bin/env python3
"""Render the canonical role files into the agent and skill forms.

Usage:
    render_roles.py            write agents/{role}.md and skills/{role}/SKILL.md
    render_roles.py --check    exit 1 if any generated file is missing or stale

Each role lives in roles/{role}.md, the only place a role's prompt is edited.
A role file holds up to two verbatim front-matter blocks and one body:

    <!-- @agent:frontmatter -->      agent front matter, copied as-is
    ---
    name: engineer
    ...
    ---
    <!-- @end -->
    <!-- @skill:frontmatter -->      skill front matter, copied as-is
    ...
    <!-- @end -->
    <!-- @body -->                   everything below is the body
    shared text goes to both forms
    <!-- @agent -->
    agent-only text
    <!-- @end -->
    <!-- @skill -->
    skill-only text
    <!-- @end -->

Lines above the first block are notes for editors and are not rendered.
A role without an agent (or skill) front-matter block has no such form.
Front matter is copied verbatim, so no YAML parser is needed.
"""
import os
import sys

PLUGIN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FORMS = ("agent", "skill")
MARK_FM = {f"<!-- @{f}:frontmatter -->": f for f in FORMS}
MARK_BLOCK = {f"<!-- @{f} -->": f for f in FORMS}
MARK_END = "<!-- @end -->"
MARK_BODY = "<!-- @body -->"


class RoleError(ValueError):
    pass


def parse(text, name):
    """Return {form: rendered text} for one role file."""
    lines = text.splitlines(keepends=True)
    frontmatter = {}
    i = 0
    while i < len(lines):
        line = lines[i].rstrip("\n")
        if line in MARK_FM:
            form = MARK_FM[line]
            if form in frontmatter:
                raise RoleError(f"{name}: duplicate {form} front matter")
            start = i + 1
            while i + 1 < len(lines) and lines[i + 1].rstrip("\n") != MARK_END:
                i += 1
            if i + 1 >= len(lines):
                raise RoleError(f"{name}: unterminated {form} front matter")
            frontmatter[form] = "".join(lines[start:i + 1])
            i += 2
            continue
        if line == MARK_BODY:
            body = lines[i + 1:]
            break
        i += 1
    else:
        raise RoleError(f"{name}: missing {MARK_BODY}")
    if not frontmatter:
        raise RoleError(f"{name}: no front matter block")

    out = {form: [] for form in frontmatter}
    current = None
    for n, raw in enumerate(body, start=1):
        line = raw.rstrip("\n")
        if line in MARK_BLOCK:
            if current is not None:
                raise RoleError(f"{name}: body line {n}: nested @{MARK_BLOCK[line]} block")
            current = MARK_BLOCK[line]
            continue
        if line == MARK_END:
            if current is None:
                raise RoleError(f"{name}: body line {n}: @end without an open block")
            current = None
            continue
        if line in MARK_FM or line == MARK_BODY:
            raise RoleError(f"{name}: body line {n}: marker not allowed in the body")
        for form in out:
            if current is None or current == form:
                out[form].append(raw)
    if current is not None:
        raise RoleError(f"{name}: unterminated @{current} block")

    rendered = {}
    for form, parts in out.items():
        fm = frontmatter[form]
        if f"name: {name}\n" not in fm:
            raise RoleError(f"{name}: {form} front matter must declare 'name: {name}'")
        rendered[form] = fm + "".join(parts)
    return rendered


def target(form, name):
    if form == "agent":
        return os.path.join(PLUGIN, "agents", f"{name}.md")
    return os.path.join(PLUGIN, "skills", name, "SKILL.md")


def render_all(plugin=PLUGIN):
    roles_dir = os.path.join(plugin, "roles")
    outputs = {}
    for fname in sorted(os.listdir(roles_dir)):
        if not fname.endswith(".md"):
            continue
        name = fname[:-3]
        with open(os.path.join(roles_dir, fname), encoding="utf-8") as fh:
            for form, text in parse(fh.read(), name).items():
                outputs[target(form, name)] = text
    return outputs


def main(argv):
    check = "--check" in argv
    try:
        outputs = render_all()
    except (OSError, RoleError) as err:
        print(f"render_roles.py: {err}", file=sys.stderr)
        return 2
    stale = []
    for path, text in outputs.items():
        current = None
        if os.path.exists(path):
            with open(path, encoding="utf-8") as fh:
                current = fh.read()
        if current == text:
            continue
        stale.append(os.path.relpath(path, PLUGIN))
        if not check:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(text)
    if check:
        if stale:
            print("stale generated files (edit roles/, then run lib/render_roles.py):", file=sys.stderr)
            for path in stale:
                print(f"  {path}", file=sys.stderr)
            return 1
        print(f"render_roles.py: {len(outputs)} generated files up to date")
        return 0
    print(f"render_roles.py: wrote {len(stale)} of {len(outputs)} files")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
