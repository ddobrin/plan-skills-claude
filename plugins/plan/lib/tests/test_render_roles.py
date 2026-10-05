import pytest

import render_roles


ROLE = """<!-- note for editors -->
<!-- @agent:frontmatter -->
---
name: demo
tools: [Read]
---
<!-- @end -->
<!-- @skill:frontmatter -->
---
name: demo
description: a demo
---
<!-- @end -->
<!-- @body -->
shared top
<!-- @agent -->
agent only
<!-- @end -->
<!-- @skill -->
skill only
<!-- @end -->
shared bottom
"""


def test_parse_splits_forms():
    out = render_roles.parse(ROLE, "demo")
    assert out["agent"] == "---\nname: demo\ntools: [Read]\n---\nshared top\nagent only\nshared bottom\n"
    assert out["skill"] == "---\nname: demo\ndescription: a demo\n---\nshared top\nskill only\nshared bottom\n"


def test_role_without_agent_frontmatter_has_no_agent_form():
    text = ROLE.split("<!-- @skill:frontmatter -->")[1]
    out = render_roles.parse("<!-- @skill:frontmatter -->" + text, "demo")
    assert set(out) == {"skill"}


@pytest.mark.parametrize("broken, message", [
    (ROLE.replace("<!-- @body -->\n", ""), "missing"),
    (ROLE.replace("name: demo\ntools", "name: other\ntools"), "must declare"),
    (ROLE.replace("agent only\n<!-- @end -->", "agent only"), "nested"),
    (ROLE + "<!-- @end -->\n", "@end without an open block"),
])
def test_parse_rejects_malformed_roles(broken, message):
    with pytest.raises(render_roles.RoleError, match=message):
        render_roles.parse(broken, "demo")


def test_repository_roles_render_and_are_in_sync():
    outputs = render_roles.render_all()
    assert any(p.endswith("agents/supervisor.md") for p in outputs)
    assert any(p.endswith("skills/simplifier/SKILL.md") for p in outputs)
    assert render_roles.main(["--check"]) == 0
