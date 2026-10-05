import os
import subprocess
import sys

import pytest

LIB = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLUGIN = os.path.dirname(LIB)
sys.path.insert(0, LIB)


def git(cwd, *args):
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True).stdout.strip()


SWARM_MD = """# Swarm configuration

Explanations live here.

```json swarm-config
{
  "version": 1,
  "delivery": {"mode": "pr", "host": "github"},
  "engineers": {"max_concurrent": 5},
  "tiers": {
    "critical": {"paths": ["**/auth/**", "migrations/**"], "keywords": ["payment", "pii"]},
    "elevated": {"paths": ["api/**"], "keywords": ["cache"], "diff_lines_over": 400}
  }
}
```
"""


@pytest.fixture
def repo(tmp_path, monkeypatch):
    """A git repo with plans/swarm.md, one commit on main, and an isolated nonce store."""
    root = tmp_path / "repo"
    root.mkdir()
    git(root, "init", "-q", "-b", "main")
    git(root, "config", "user.email", "dev@example.com")
    git(root, "config", "user.name", "Dev")
    git(root, "config", "commit.gpgsign", "false")
    (root / "plans").mkdir()
    (root / "plans" / "swarm.md").write_text(SWARM_MD)
    (root / "README.md").write_text("hello\n")
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", "init")
    monkeypatch.setenv("PLAN_SWARM_TEST", "1")
    monkeypatch.setenv("PLAN_SWARM_STORE", str(tmp_path / "store"))
    monkeypatch.chdir(root)
    return root
