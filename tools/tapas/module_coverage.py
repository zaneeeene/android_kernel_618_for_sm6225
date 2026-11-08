#!/usr/bin/env python3
"""Compare rebuilt module outputs with an ordered stock modules.load file."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re


def normalize(name: str) -> str:
    return re.sub(r"[-_]", "", name.removesuffix(".ko").lower())


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stock", required=True, type=Path)
    parser.add_argument("--map", required=True, type=Path)
    parser.add_argument("--config", type=Path)
    parser.add_argument("--root", action="append", default=[], metavar="LABEL=PATH")
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--require-complete", action="store_true")
    args = parser.parse_args()

    rules = json.loads(args.map.read_text())
    aliases = rules.get("aliases", {})
    builtins = rules.get("builtins", {})
    replacements = rules.get("replacements", {})
    optional_omissions = rules.get("optional_omissions", {})
    config_lines = set(args.config.read_text().splitlines()) if args.config else set()
    stock = [line.strip() for line in args.stock.read_text().splitlines()
             if line.strip().endswith(".ko")]
    wanted = {normalize(name) for name in stock}
    wanted.update(normalize(alias) for names in aliases.values() for alias in names)
    wanted.update(normalize(module) for rule in replacements.values()
                  for module in rule.get("modules", []))
    available: dict[str, list[dict[str, object]]] = {}
    all_outputs = []
    for item in args.root:
        label, separator, raw_path = item.partition("=")
        if not separator:
            parser.error(f"invalid --root {item!r}; expected LABEL=PATH")
        root = Path(raw_path)
        if not root.is_dir():
            continue
        for path in sorted(root.rglob("*.ko")):
            if normalize(path.name) not in wanted:
                continue
            record = {
                "name": path.name,
                "source": label,
                "path": str(path.relative_to(root)),
                "size": path.stat().st_size,
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            }
            all_outputs.append(record)
            available.setdefault(normalize(path.name), []).append(record)

    entries = []
    missing = []
    for position, name in enumerate(stock):
        candidates = list(available.get(normalize(name), []))
        matched_as = name
        if not candidates:
            for alias in aliases.get(name, []):
                candidates.extend(available.get(normalize(alias), []))
            if candidates:
                matched_as = ",".join(aliases[name])
        if candidates:
            entries.append({"position": position, "stock": name, "status": "module",
                            "matched_as": matched_as, "candidates": candidates})
        elif name in replacements:
            rule = replacements[name]
            required = rule.get("modules", [])
            present = {module: available.get(normalize(module), []) for module in required}
            if required and all(present.values()):
                entries.append({"position": position, "stock": name, "status": "replacement",
                                "reason": rule["reason"], "requires": present})
            else:
                entries.append({"position": position, "stock": name, "status": "missing",
                                "unsatisfied_replacement": rule})
                missing.append(name)
        elif name in builtins:
            rule = builtins[name]
            if isinstance(rule, str):
                rule = {"reason": rule}
            required = rule.get("config")
            if not required or required in config_lines:
                entries.append({"position": position, "stock": name,
                                "status": "builtin-policy", **rule})
            else:
                entries.append({"position": position, "stock": name, "status": "missing",
                                "unsatisfied_builtin": rule})
                missing.append(name)
        elif name in optional_omissions:
            entries.append({"position": position, "stock": name, "status": "optional-omission",
                            "reason": optional_omissions[name]})
        else:
            entries.append({"position": position, "stock": name, "status": "missing"})
            missing.append(name)

    report = {
        "stock_entries": len(stock),
        "rebuilt_outputs": len(all_outputs),
        "covered_by_module": sum(item["status"] == "module" for item in entries),
        "covered_by_builtin_policy": sum(item["status"] == "builtin-policy" for item in entries),
        "covered_by_replacement": sum(item["status"] == "replacement" for item in entries),
        "optional_omissions_count": sum(item["status"] == "optional-omission" for item in entries),
        "optional_omissions": [item["stock"] for item in entries
                               if item["status"] == "optional-omission"],
        "missing_count": len(missing),
        "missing": missing,
        "entries": entries,
    }
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(f"coverage: {report['covered_by_module']} modules + "
          f"{report['covered_by_builtin_policy']} built-in policies + "
          f"{report['covered_by_replacement']} replacements + "
          f"{report['optional_omissions_count']} optional omissions / {len(stock)}; "
          f"missing {len(missing)}")
    if missing:
        print("missing: " + " ".join(missing))
    return 1 if args.require_complete and missing else 0


if __name__ == "__main__":
    raise SystemExit(main())
