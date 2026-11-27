"""Prepares the PyPI build: PyPI refuses dependencies given by direct URL, so the extras that need
them (ru, all, bench: pii-guard and the spaCy models from GitHub) are left out of the PyPI package,
and relative links in README.md are made absolute so that they work on pypi.org.
The full install from GitHub is unchanged. Run in the repository root before `uv build` (.github/workflows/pypi.yml does)."""

import re
import tomllib
from pathlib import Path

REPO = "https://github.com/beskvladimir-create/pii-roundtrip/blob/main/"

text = Path("pyproject.toml").read_text(encoding="utf-8")
extras = tomllib.loads(text)["project"]["optional-dependencies"]
drop = sorted(k for k, deps in extras.items() if any("@" in d for d in deps))
drop += sorted(
    k for k, deps in extras.items() if k not in drop and any(f"[{x}" in d or f",{x}" in d for d in deps for x in drop)
)
lines, skip = [], False
for line in text.splitlines(keepends=True):
    key = re.match(r"^([a-z]+) = \[", line)
    if key and key.group(1) in drop:
        skip = not line.rstrip().endswith("]")
        while lines and lines[-1].startswith("#"):
            lines.pop()
        continue
    if skip:
        skip = line.strip() != "]"
        continue
    lines.append(line)
Path("pyproject.toml").write_text("".join(lines), encoding="utf-8")
left = tomllib.loads("".join(lines))["project"]["optional-dependencies"]
assert not any("@" in d for deps in left.values() for d in deps), left

readme = Path("README.md").read_text(encoding="utf-8")
readme = re.sub(r"\]\((?!https?:|#|mailto:)([^)]+)\)", lambda m: f"]({REPO}{m.group(1)})", readme)
Path("README.md").write_text(readme, encoding="utf-8")
print("left out of the PyPI package:", ", ".join(drop), "| kept:", ", ".join(left))
