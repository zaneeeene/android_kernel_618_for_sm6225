#!/usr/bin/env python3
"""Assemble a dependency-closed SM6225 module payload from Gate 4 outputs.

The default provider is the newer Qualcomm soc-repo, while explicitly listed
kernel-core modules come from ACK. Duplicate implementations are never copied.
This only creates a module directory; it does not create a flashable image.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess


def normalize(name: str) -> str:
    return re.sub(r"[-_]", "", Path(name).name.removesuffix(".ko").lower())


def modinfo(path: Path, field: str) -> str:
    result = subprocess.run(
        ["modinfo", "-F", field, str(path)], capture_output=True, text=True
    )
    if result.returncode:
        raise RuntimeError(f"modinfo {field} failed for {path}: {result.stderr.strip()}")
    return result.stdout.strip()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--coverage", required=True, type=Path)
    parser.add_argument("--rules", required=True, type=Path)
    parser.add_argument("--root", action="append", default=[], metavar="LABEL=PATH")
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--release", required=True)
    parser.add_argument("--system-map", type=Path)
    parser.add_argument("--strip", type=Path)
    args = parser.parse_args()

    coverage = json.loads(args.coverage.read_text())
    rules = json.loads(args.rules.read_text())
    if coverage.get("missing_count"):
        raise RuntimeError("coverage report still has blocking missing modules")

    roots: dict[str, Path] = {}
    for item in args.root:
        label, separator, path = item.partition("=")
        if not separator:
            parser.error(f"invalid --root {item!r}; expected LABEL=PATH")
        roots[label] = Path(path)

    records = []
    by_provider_path = {}
    by_filename: dict[str, list[dict]] = {}
    by_internal: dict[str, list[dict]] = {}
    for label, root in roots.items():
        for path in sorted(root.rglob("*.ko")):
            record = {
                "source": label,
                "path": str(path.relative_to(root)),
                "file": path,
                "filename": path.name,
                "name": modinfo(path, "name"),
                "depends": [name.strip() for name in modinfo(path, "depends").split(",")
                            if name.strip()],
            }
            records.append(record)
            by_provider_path[(label, record["path"])] = record
            by_filename.setdefault(normalize(path.name), []).append(record)
            by_internal.setdefault(normalize(record["name"]), []).append(record)

    prefer_gki = {normalize(name) for name in rules.get("prefer_gki", [])}

    def choose(candidates: list[dict], requested: str, parent: dict | None = None) -> dict:
        if not candidates:
            raise RuntimeError(f"no candidate for {requested}")
        wanted = "gki" if normalize(requested) in prefer_gki else "soc"
        return sorted(
            candidates,
            key=lambda record: (
                record["source"] != (parent["source"] if parent else wanted),
                record["source"] != wanted,
                record["path"],
            ),
        )[0]

    seeds: list[dict] = []
    for entry in coverage["entries"]:
        status = entry["status"]
        if status == "module":
            candidates = [
                by_provider_path[(item["source"], item["path"])]
                for item in entry["candidates"]
                if (item["source"], item["path"]) in by_provider_path
            ]
            seeds.append(choose(candidates, entry["stock"]))
        elif status == "replacement":
            for requested, items in entry["requires"].items():
                candidates = [
                    by_provider_path[(item["source"], item["path"])]
                    for item in items
                    if (item["source"], item["path"]) in by_provider_path
                ]
                seeds.append(choose(candidates, requested))
        elif status not in ("builtin-policy", "optional-omission"):
            raise RuntimeError(f"unsupported coverage state for {entry['stock']}: {status}")

    for requested in rules.get("payload_extras", []):
        seeds.append(choose(by_filename.get(normalize(requested), []), requested))

    selected: dict[str, dict] = {}
    visiting = set()
    ordered: list[dict] = []

    def add(record: dict) -> None:
        key = normalize(record["name"])
        existing = selected.get(key)
        if existing:
            if existing["file"] != record["file"] and existing["source"] != record["source"]:
                # Provider choice made by the first stock-order seed is authoritative.
                return
            return
        if key in visiting:
            raise RuntimeError(f"module dependency cycle at {record['name']}")
        visiting.add(key)
        for dependency in record["depends"]:
            candidate = choose(by_internal.get(normalize(dependency), []), dependency, record)
            add(candidate)
        visiting.remove(key)
        selected[key] = record
        ordered.append(record)

    for seed in seeds:
        add(seed)

    module_dir = args.output / "lib/modules" / args.release
    if args.output.exists():
        shutil.rmtree(args.output)
    module_dir.mkdir(parents=True)
    copied = []
    filenames = set()
    for record in ordered:
        if record["filename"] in filenames:
            raise RuntimeError(f"duplicate payload filename: {record['filename']}")
        filenames.add(record["filename"])
        destination = module_dir / record["filename"]
        shutil.copyfile(record["file"], destination)
        if args.strip:
            subprocess.run([str(args.strip), "--strip-debug", str(destination)], check=True)
        copied.append({
            "name": record["name"],
            "filename": record["filename"],
            "source": record["source"],
            "input_path": record["path"],
            "depends": record["depends"],
            "size": destination.stat().st_size,
            "sha256": hashlib.sha256(destination.read_bytes()).hexdigest(),
        })

    (module_dir / "modules.load").write_text(
        "".join(record["filename"] + "\n" for record in ordered)
    )
    for metadata in ("modules.order", "modules.builtin", "modules.builtin.modinfo"):
        (module_dir / metadata).write_text("")
    depmod = ["depmod", "-b", str(args.output)]
    if args.system_map:
        depmod += ["-F", str(args.system_map)]
    depmod.append(args.release)
    subprocess.run(depmod, check=True)
    report = {
        "flashable": False,
        "kernel_release": args.release,
        "module_count": len(copied),
        "modules": copied,
    }
    (args.output / "payload-report.json").write_text(json.dumps(report, indent=2) + "\n")
    (args.output / "NOT_FLASHABLE").write_text(
        "Compile/dependency artifact only; runtime hardware gates have not passed.\n"
    )
    print(f"assembled {len(copied)} dependency-closed modules; output is NOT FLASHABLE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
