#!/usr/bin/env python3
"""Print soc-repo registry targets matching an ordered stock modules list."""

from __future__ import annotations

import re
import os
import sys
import json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import k618_soc_kbuild as kb


def normalize(name: str) -> str:
    return re.sub(r"[-_]", "", name.removesuffix(".ko").lower())


def main() -> int:
    if len(sys.argv) not in (3, 4):
        print(f"usage: {sys.argv[0]} SOC_TREE MODULES.LOAD [NAME_MAP.json]", file=sys.stderr)
        return 2
    soc, load = sys.argv[1:3]
    aliases = {}
    if len(sys.argv) == 4:
        soc, load, name_map = sys.argv[1:]
        aliases = json.load(open(name_map, encoding="utf-8")).get("aliases", {})
    modules = kb.load_registry(soc)
    by_output = {normalize(module["out"]): name for name, module in modules.items()}
    selected = []
    for line in open(load, encoding="utf-8"):
        module = line.strip()
        if not module.endswith(".ko"):
            continue
        target = by_output.get(normalize(module))
        if not target:
            target = next((by_output.get(normalize(alias))
                           for alias in aliases.get(module, [])
                           if by_output.get(normalize(alias))), None)
        if target and target not in selected:
            selected.append(target)
    print(" ".join(selected))
    print(f"k618_soc_stock_select: {len(selected)} registry matches", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
