#!/usr/bin/env python3
"""
Strip execution outputs from Jupyter notebooks and apply the same
placeholder substitutions used on the .py sources.

Run from repo root:
    python scripts/clean_notebooks.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

NOTEBOOKS = [
    "notebooks/geometry_generation.ipynb",
    "notebooks/installation.ipynb",
]

# Keep this list in sync with scripts/parameterize_targets.example.yaml — but
# this is a one-shot cleanup tool, so the literal patterns are inlined and
# the script itself is gitignored against being committed back with sensitive
# values. The committed version of this file uses generic placeholders only.
REPLACEMENTS_GENERIC = [
    # Notebook source-cell hardcoded paths land here. The actual values
    # used during initial cleanup were loaded from the (gitignored) local
    # YAML config; this committed copy intentionally only documents the
    # placeholder shape.
    # ("C:/Users/<your_username>/Documents/<your_project>/...", "<path_to_your_workspace>/..."),
]


def strip_outputs(nb: dict) -> tuple[int, int]:
    """Clear cell outputs + execution counts. Returns (cells_touched, outputs_removed)."""
    cells_touched = 0
    outputs_removed = 0
    for cell in nb.get("cells", []):
        if cell.get("cell_type") != "code":
            continue
        n_out = len(cell.get("outputs", []) or [])
        if n_out or cell.get("execution_count") is not None:
            cells_touched += 1
            outputs_removed += n_out
            cell["outputs"] = []
            cell["execution_count"] = None
    # Also wipe notebook-level metadata that may carry kernel/host info
    nb.setdefault("metadata", {}).pop("language_info", None)
    return cells_touched, outputs_removed


def apply_replacements(text: str, replacements: list[tuple[str, str]]) -> tuple[str, int]:
    total = 0
    for old, new in replacements:
        n = text.count(old)
        if n:
            text = text.replace(old, new)
            total += n
    return text, total


def main(replacements: list[tuple[str, str]] | None = None) -> None:
    replacements = replacements or REPLACEMENTS_GENERIC
    grand_outputs = 0
    grand_subs = 0
    for rel in NOTEBOOKS:
        path = REPO_ROOT / rel
        if not path.exists():
            print(f"  MISSING: {rel}")
            continue
        nb = json.loads(path.read_text(encoding="utf-8"))
        cells, outs = strip_outputs(nb)
        # Re-serialize then apply text-level substitutions to remaining source cells
        text = json.dumps(nb, indent=1, ensure_ascii=False)
        text, n_subs = apply_replacements(text, replacements)
        path.write_text(text, encoding="utf-8")
        grand_outputs += outs
        grand_subs += n_subs
        print(f"  {rel}: cleared {cells} cells / {outs} outputs, {n_subs} string replacements")
    print(f"  Total: {grand_outputs} outputs removed, {grand_subs} string substitutions")


if __name__ == "__main__":
    main()
