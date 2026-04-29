#!/usr/bin/env python3
"""
Helper script for stripping user-specific / lab-specific values out of
STAMP-2.5D source files and replacing them with documented `<placeholder>`s.

This file ships *generically*. The actual substitution patterns are
user-specific (your username, your hostname, your local paths) and live in
`scripts/parameterize_targets.local.yaml`, which is git-ignored.

To use:
  1. Copy `scripts/parameterize_targets.example.yaml` →
     `scripts/parameterize_targets.local.yaml`.
  2. Edit your real values into the new file.
  3. Run `python scripts/parameterize.py` from the repo root.

The published commits of this repository are already parameterized; this
tool is provided as ongoing maintenance for contributors who pull in new
files from their personal workspaces and want a one-step way to scrub them.

The script is intentionally idempotent — running it twice is a no-op.
"""
from __future__ import annotations

import sys
from pathlib import Path

try:
    import yaml  # PyYAML
except ImportError:
    print("PyYAML is required. `pip install pyyaml` and re-run.", file=sys.stderr)
    sys.exit(1)


REPO_ROOT = Path(__file__).resolve().parents[1]
CONFIG = Path(__file__).parent / "parameterize_targets.local.yaml"


def load_config() -> dict:
    if not CONFIG.exists():
        print(f"No config at {CONFIG.relative_to(REPO_ROOT)} — nothing to do.")
        print(
            "Copy `scripts/parameterize_targets.example.yaml` to "
            "`scripts/parameterize_targets.local.yaml`, fill in your "
            "real values, and re-run."
        )
        sys.exit(0)
    with CONFIG.open() as f:
        return yaml.safe_load(f)


def scrub(path: Path, replacements: list[tuple[str, str]]) -> dict[str, int]:
    """Apply literal replacements to one file. Returns per-pattern hit counts."""
    text = path.read_text(encoding="utf-8")
    original = text
    counts: dict[str, int] = {}
    for old, new in replacements:
        n = text.count(old)
        if n:
            text = text.replace(old, new)
            counts[old] = n
    if text != original:
        path.write_text(text, encoding="utf-8")
    return counts


def main() -> None:
    cfg = load_config()
    replacements: list[tuple[str, str]] = [
        (item["from"], item["to"]) for item in cfg.get("replacements", [])
    ]
    targets: list[str] = cfg.get("targets", [])

    if not replacements:
        print("Config has no `replacements:` — nothing to do.")
        return
    if not targets:
        print("Config has no `targets:` — nothing to do.")
        return

    grand_total = 0
    print(f"{'file':<55}  hits")
    print("-" * 70)
    for rel in targets:
        path = REPO_ROOT / rel
        if not path.exists():
            print(f"{rel:<55}  MISSING")
            continue
        counts = scrub(path, replacements)
        total = sum(counts.values())
        grand_total += total
        print(f"{rel:<55}  {total}")
    print("-" * 70)
    print(f"Total replacements: {grand_total}")


if __name__ == "__main__":
    main()
