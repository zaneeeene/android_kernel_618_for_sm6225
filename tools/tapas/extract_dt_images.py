#!/usr/bin/env python3
"""Extract concatenated vendor DTBs and Android DTBO entries without mkdtimg."""

from __future__ import annotations

import argparse
import json
import struct
from pathlib import Path

FDT_MAGIC = b"\xd0\x0d\xfe\xed"
DTBO_MAGIC = b"\xd7\xb7\xab\x1e"


def fdt_info(data: bytes, offset: int) -> dict[str, int] | None:
    if offset + 40 > len(data) or data[offset : offset + 4] != FDT_MAGIC:
        return None
    values = struct.unpack_from(">10I", data, offset)
    _, total, struct_off, strings_off, reserve_off, version, last, _, strings_size, struct_size = values
    if not 40 <= total <= len(data) - offset:
        return None
    if not 16 <= version <= 100:
        return None
    if max(struct_off + struct_size, strings_off + strings_size, reserve_off) > total:
        return None
    return {
        "offset": offset,
        "size": total,
        "version": version,
        "last_comp_version": last,
    }


def extract_vendor_dtbs(image: Path, output: Path) -> list[dict[str, int | str]]:
    data = image.read_bytes()
    output.mkdir(parents=True, exist_ok=True)
    entries: list[dict[str, int | str]] = []
    position = 0
    while True:
        position = data.find(FDT_MAGIC, position)
        if position < 0:
            break
        info = fdt_info(data, position)
        if info is None:
            position += 4
            continue
        filename = f"{len(entries):03d}.dtb"
        (output / filename).write_bytes(data[position : position + info["size"]])
        entries.append({**info, "file": filename})
        position += info["size"]
    if sum(int(entry["size"]) for entry in entries) != len(data):
        raise ValueError("vendor DTB payload contains unaccounted bytes")
    (output / "index.json").write_text(json.dumps(entries, indent=2) + "\n")
    return entries


def extract_dtbo(image: Path, output: Path) -> dict[str, object]:
    data = image.read_bytes()
    output.mkdir(parents=True, exist_ok=True)
    if data[:4] != DTBO_MAGIC:
        raise ValueError(f"invalid DTBO magic: {data[:4].hex()}")
    magic, total, header_size, entry_size, count, entries_offset, page_size, version = struct.unpack_from(
        ">8I", data, 0
    )
    if magic != int.from_bytes(DTBO_MAGIC, "big") or total > len(data):
        raise ValueError("invalid DTBO header")
    if header_size < 32 or entry_size < 32 or entries_offset + count * entry_size > total:
        raise ValueError("invalid DTBO entry table")
    entries = []
    for index in range(count):
        values = struct.unpack_from(">8I", data, entries_offset + index * entry_size)
        size, offset, identifier, revision, *custom = values
        info = fdt_info(data, offset)
        if info is None or info["size"] != size:
            raise ValueError(f"entry {index} is not a valid FDT")
        filename = f"{index:03d}.dtbo"
        (output / filename).write_bytes(data[offset : offset + size])
        entries.append(
            {
                "index": index,
                "offset": offset,
                "size": size,
                "id": identifier,
                "revision": revision,
                "custom": custom,
                "file": filename,
            }
        )
    result = {
        "header": {
            "total_size": total,
            "header_size": header_size,
            "entry_size": entry_size,
            "entry_count": count,
            "entries_offset": entries_offset,
            "page_size": page_size,
            "version": version,
        },
        "entries": entries,
    }
    (output / "index.json").write_text(json.dumps(result, indent=2) + "\n")
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("vendor_dtb", type=Path, help="dtb payload extracted from vendor_boot")
    parser.add_argument("dtbo", type=Path, help="stock dtbo.img")
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    vendor = extract_vendor_dtbs(args.vendor_dtb, args.output / "vendor-dtbs")
    overlays = extract_dtbo(args.dtbo, args.output / "dtbo")
    print(f"extracted {len(vendor)} base DTBs and {overlays['header']['entry_count']} overlays")


if __name__ == "__main__":
    main()
