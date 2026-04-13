#!/usr/bin/env python3
"""
configure_inputs.py — Propagate shared case parameters to all solver input files.

Reads  inputs/case_config.cfg  and updates every  inputs/input.*  file in place.

Usage:
    python run_scripts/configure_inputs.py              # dry run (show changes)
    python run_scripts/configure_inputs.py --apply      # write changes to disk
    python run_scripts/configure_inputs.py --apply --section shared
    python run_scripts/configure_inputs.py --apply --file input.adaptive_local

Config sections:
    [shared]  → applied to ALL input files
    [local]   → applied only to files whose name ends with _local
    [hpc]     → applied to all OTHER input files (HPC / cluster)
"""

import argparse
import re
import sys
from pathlib import Path

# ── Paths ────────────────────────────────────────────────────────────────────
SCRIPT_DIR  = Path(__file__).resolve().parent
CASE_DIR    = SCRIPT_DIR.parent
INPUTS_DIR  = CASE_DIR / "inputs"
CONFIG_FILE = INPUTS_DIR / "case_config.cfg"

# Input files that behave as local (quick tests, no AMR)
LOCAL_SUFFIX = "_local"

# Files to skip entirely (templates, config itself)
SKIP_FILES = {"case_config.cfg"}


# ── Config parser ─────────────────────────────────────────────────────────────
def read_config(path: Path) -> dict[str, dict[str, str]]:
    """
    Parse a simple INI-style config file.
    Returns: {section_name: {key: value}}
    Lines starting with # are comments; inline # comments are stripped.
    """
    config: dict[str, dict[str, str]] = {}
    current: str | None = None

    with open(path) as fh:
        for raw_line in fh:
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("[") and line.endswith("]"):
                current = line[1:-1].strip()
                config[current] = {}
            elif "=" in line and current is not None:
                key, _, value = line.partition("=")
                # strip inline comment
                value_clean = value.split("#")[0].strip()
                config[current][key.strip()] = value_clean

    return config


# ── Per-line value updater ────────────────────────────────────────────────────
def update_param(content: str, key: str, new_value: str) -> tuple[str, int]:
    """
    Replace the value for ``key`` in an AMReX input file string.

    Matches lines like::
        key = old_value        # optional comment
        key     =     old_value

    Preserves the leading ``key = `` prefix and any trailing inline comment.
    Returns (new_content, number_of_replacements).
    """
    pattern = re.compile(
        r"^(" + re.escape(key) + r"[ \t]*=[ \t]*)(.*)$",
        re.MULTILINE,
    )

    def _replace(m: re.Match) -> str:
        old_rest = m.group(2)
        # Preserve inline comment if present (first # that is preceded by whitespace)
        comment_match = re.search(r"(\s+#.*)$", old_rest)
        comment = comment_match.group(1) if comment_match else ""
        return m.group(1) + new_value + comment

    new_content, n = re.subn(pattern, _replace, content)
    return new_content, n


# ── Core logic ────────────────────────────────────────────────────────────────
def classify_file(name: str) -> str:
    """Return 'local' or 'hpc' based on the filename (name = Path.name, not .stem)."""
    # e.g. "input.adaptive_local" ends with "_local" → local
    #      "input.adaptive"                           → hpc
    return "local" if name.endswith(LOCAL_SUFFIX) else "hpc"


def apply_config_to_file(
    fpath: Path,
    shared: dict[str, str],
    local: dict[str, str],
    hpc: dict[str, str],
    sections_filter: list[str] | None,
    apply: bool,
    verbose: bool = True,
) -> int:
    """
    Apply config params to one input file.
    Returns number of keys that were changed.
    """
    kind = classify_file(fpath.name)
    extra = local if kind == "local" else hpc

    # Merge: shared first, then local/hpc overrides
    params = {**shared, **extra}

    if sections_filter:
        # Rebuild filtering only the requested sections
        params = {}
        if "shared" in sections_filter:
            params.update(shared)
        if kind in sections_filter:
            params.update(extra)

    if not params:
        return 0

    content_orig = fpath.read_text()
    content = content_orig
    changes: list[tuple[str, str, str]] = []

    for key, new_value in params.items():
        content_new, n = update_param(content, key, new_value)
        if n > 0 and content_new != content:
            # Capture old value for reporting
            m = re.search(
                r"^" + re.escape(key) + r"[ \t]*=[ \t]*(.*)$",
                content_orig,
                re.MULTILINE,
            )
            old_raw = m.group(1).split("#")[0].strip() if m else "???"
            if old_raw != new_value:
                changes.append((key, old_raw, new_value))
            content = content_new

    if verbose:
        if changes:
            print(f"  {fpath.name}  [{kind}]")
            for key, old, new in changes:
                print(f"    {key:<35s}  {old!r:>20s}  →  {new!r}")
        else:
            print(f"  {fpath.name}  [{kind}]  (no changes)")

    if apply and changes:
        fpath.write_text(content)

    return len(changes)


# ── Main ──────────────────────────────────────────────────────────────────────
def main() -> None:
    parser = argparse.ArgumentParser(
        description="Propagate case_config.cfg to all solver input files"
    )
    parser.add_argument(
        "--apply", action="store_true",
        help="Write changes to disk (default: dry run, show changes only)"
    )
    parser.add_argument(
        "--section", nargs="+", choices=["shared", "local", "hpc"], default=None,
        help="Apply only the specified section(s)"
    )
    parser.add_argument(
        "--file", type=str, default=None,
        help="Update only this specific input file (basename, e.g. input.adaptive_local)"
    )
    parser.add_argument(
        "--config", type=str, default=str(CONFIG_FILE),
        help=f"Path to config file (default: {CONFIG_FILE})"
    )
    args = parser.parse_args()

    if not args.apply:
        print("DRY RUN — no files will be modified.  Pass --apply to write changes.\n")

    config_path = Path(args.config)
    if not config_path.exists():
        print(f"ERROR: config file not found: {config_path}")
        sys.exit(1)

    cfg = read_config(config_path)
    shared = cfg.get("shared", {})
    local  = cfg.get("local",  {})
    hpc    = cfg.get("hpc",    {})

    print(f"Config: {config_path}")
    print(f"  [shared]: {len(shared)} params")
    print(f"  [local]:  {len(local)} params")
    print(f"  [hpc]:    {len(hpc)} params")
    print()

    # Select files
    if args.file:
        target = INPUTS_DIR / args.file
        if not target.exists():
            print(f"ERROR: file not found: {target}")
            sys.exit(1)
        input_files = [target]
    else:
        input_files = sorted(
            p for p in INPUTS_DIR.glob("input.*")
            if p.name not in SKIP_FILES and p.is_file()
        )

    total_changes = 0
    for fpath in input_files:
        n = apply_config_to_file(
            fpath, shared, local, hpc,
            sections_filter=args.section,
            apply=args.apply,
        )
        total_changes += n

    print()
    if args.apply:
        print(f"Applied {total_changes} value change(s) across {len(input_files)} file(s).")
    else:
        print(f"Dry run: {total_changes} value change(s) would be applied across {len(input_files)} file(s).")
        print("Run with --apply to write.")


if __name__ == "__main__":
    main()
