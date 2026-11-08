#!/usr/bin/env python3
"""Verify that every boot-critical stock compatible has a selected provider."""

from __future__ import annotations

import argparse
import fnmatch
import json
from pathlib import Path
import re
import subprocess


def normalize(name: str) -> str:
    return re.sub(r"[-_]", "", Path(name).name.removesuffix(".ko").lower())


def aliases(path: Path) -> list[str]:
    result = subprocess.run(
        ["modinfo", "-F", "alias", str(path)], capture_output=True, text=True
    )
    if result.returncode:
        raise RuntimeError(f"modinfo failed for {path}: {result.stderr.strip()}")
    return [line for line in result.stdout.splitlines() if line]


def alias_matches(pattern: str, compatible: str) -> bool:
    modaliases = [f"of:N*T*C{compatible}", f"of:N*T*C{compatible}C"]
    return any(fnmatch.fnmatchcase(modalias, pattern) for modalias in modaliases)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--payload", required=True, type=Path)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    manifest = json.loads(args.manifest.read_text())
    config = set(args.config.read_text().splitlines())
    modules = {}
    for path in args.payload.rglob("*.ko"):
        modules.setdefault(normalize(path.name), path)

    entries = []
    failures = []
    for expected in manifest["modules"]:
        module = modules.get(normalize(expected["module"]))
        entry = dict(expected)
        if not module:
            entry["status"] = "missing-module"
            failures.append(entry)
        else:
            module_aliases = aliases(module)
            entry["path"] = str(module.relative_to(args.payload))
            entry["aliases"] = module_aliases
            entry["status"] = (
                "passed" if any(alias_matches(pattern, expected["compatible"])
                                for pattern in module_aliases)
                else "missing-alias"
            )
            if entry["status"] != "passed":
                failures.append(entry)
        entries.append(entry)

    for expected in manifest.get("builtins", []):
        entry = dict(expected)
        entry["status"] = "passed" if expected["config"] in config else "missing-config"
        if entry["status"] != "passed":
            failures.append(entry)
        entries.append(entry)

    report = {
        "status": "passed" if not failures else "failed",
        "checked": len(entries),
        "failure_count": len(failures),
        "failures": failures,
        "entries": entries,
    }
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(f"DT binding audit: {len(entries) - len(failures)}/{len(entries)} passed")
    for failure in failures:
        print(f"missing {failure['compatible']}: {failure['status']}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
