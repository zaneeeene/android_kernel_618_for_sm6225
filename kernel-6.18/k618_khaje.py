#!/usr/bin/env python3
"""Import the first build-only Khaje platform drivers into the 6.11 soc tree.

Usage: k618_khaje.py <MiCode topaz-t-oss tree> <patched SM8850 soc tree>

This first gate intentionally covers only standalone clocks, TLMM and UFS PHY.
Legacy SMD/RPM, Bengal NoC and remoteproc integration are separate work; an
image made after only this import is not bootable.
"""

from __future__ import annotations

import os
import re
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import k618_soc_kbuild as kb  # noqa: E402


FILES = [
    "drivers/clk/qcom/gcc-khaje.c",
    "drivers/clk/qcom/dispcc-khaje.c",
    "drivers/clk/qcom/gpucc-khaje.c",
    "drivers/clk/qcom/debugcc-khaje.c",
    "drivers/clk/qcom/vdd-level-bengal.h",
    "include/dt-bindings/clock/qcom,gcc-khaje.h",
    "include/dt-bindings/clock/qcom,dispcc-khaje.h",
    "include/dt-bindings/clock/qcom,gpucc-khaje.h",
    "include/dt-bindings/regulator/qcom,rpm-smd-regulator.h",
    "drivers/pinctrl/qcom/pinctrl-khaje.c",
    "drivers/pinctrl/qcom/pinctrl-bengal.c",
    "drivers/phy/qualcomm/phy-qcom-ufs-qmp-v4-khaje.c",
    "drivers/phy/qualcomm/phy-qcom-ufs-qmp-v4-khaje.h",
    "include/dt-bindings/phy/qcom,khaje-qmp-usb3.h",
]

KCONFIG_FROM_DONOR = [
    ("arch/arm64/Kconfig.platforms", "ARCH_BENGAL"),
    ("arch/arm64/Kconfig.platforms", "ARCH_KHAJE"),
    ("drivers/clk/qcom/Kconfig", "SM_GCC_KHAJE"),
    ("drivers/clk/qcom/Kconfig", "SM_DISPCC_KHAJE"),
    ("drivers/clk/qcom/Kconfig", "SM_GPUCC_KHAJE"),
    ("drivers/clk/qcom/Kconfig", "SM_DEBUGCC_KHAJE"),
    ("drivers/pinctrl/qcom/Kconfig", "PINCTRL_KHAJE"),
    ("drivers/pinctrl/qcom/Kconfig", "PINCTRL_BENGAL"),
]

KCONFIG_NEW = [
    (
        "drivers/phy/qualcomm/Kconfig",
        "PHY_QCOM_UFS_V4_KHAJE",
        """config PHY_QCOM_UFS_V4_KHAJE
\ttristate "Qualcomm Technologies, Inc. UFS Khaje PHY driver"
\tdepends on PHY_QCOM_UFS
\thelp
\t  Support the QMP v4 UFS PHY present on Khaje/SM6225.
\t  This is required for the stock downstream Khaje device tree.
""",
    ),
]

# New module, existing 6.11 module used as registry/API template, substitutions.
MODULES = [
    (
        f"drivers/clk/qcom/{controller}-khaje",
        f"drivers/clk/qcom/{controller}-sun",
        [(f"{controller}-sun", f"{controller}-khaje"), ("_SUN", "_KHAJE")],
    )
    for controller in ("gcc", "dispcc", "gpucc", "debugcc")
] + [
    (
        "drivers/pinctrl/qcom/pinctrl-khaje",
        "drivers/pinctrl/qcom/pinctrl-sun",
        [("pinctrl-sun", "pinctrl-khaje"), ("_SUN", "_KHAJE")],
    ),
    (
        "drivers/pinctrl/qcom/pinctrl-bengal",
        "drivers/pinctrl/qcom/pinctrl-sun",
        [("pinctrl-sun", "pinctrl-bengal"), ("_SUN", "_BENGAL")],
    ),
    (
        "drivers/phy/qualcomm/phy-qcom-ufs-qmp-v4-khaje",
        "drivers/phy/qualcomm/phy-qcom-ufs-qmp-v4-waipio",
        [("waipio", "khaje"), ("WAIPIO", "KHAJE")],
    ),
]

PORT_EDITS = [
    (
        r"drivers/clk/qcom/debugcc-khaje\.c",
        r'"Unable to register %s, err:\(%d\)\\n"',
        r'"Unable to register %s, err:(%ld)\\n"',
    ),
    # The 6.11 soc-repo clock core takes struct device rather than platform_device.
    (
        r"drivers/clk/qcom/\w+-khaje\.c",
        r"\bqcom_cc_really_probe\(pdev,",
        "qcom_cc_really_probe(&pdev->dev,",
    ),
    # The newer shared pinctrl core renamed msm_function and reads group data via .grp.
    (
        r"drivers/pinctrl/qcom/pinctrl-(?:khaje|bengal)\.c",
        r"static const struct msm_function (\w+_functions\[\])",
        r"static const struct pinfunction \1",
    ),
    (
        r"drivers/pinctrl/qcom/pinctrl-(?:khaje|bengal)\.c",
        r"(\t\t\.npins = \(unsigned int\)ARRAY_SIZE\(gpio##id##_pins\),[ \t]*\\\n)(?![ \t]*\.grp)",
        r'\1\t\t.grp = PINCTRL_PINGROUP("gpio" #id, gpio##id##_pins, ARRAY_SIZE(gpio##id##_pins)), \\\n',
    ),
    (
        r"drivers/pinctrl/qcom/pinctrl-(?:khaje|bengal)\.c",
        r"(\t\t\.npins = \(unsigned int\)ARRAY_SIZE\(pg_name##_pins\),[ \t]*\\\n)(?![ \t]*\.grp)",
        r"\1\t\t.grp = PINCTRL_PINGROUP(#pg_name, pg_name##_pins, ARRAY_SIZE(pg_name##_pins)), \\\n",
    ),
    (
        r"drivers/phy/qualcomm/phy-qcom-ufs-qmp-v4-khaje\.c",
        r'"%s: unsupported submode\.\\n"\);',
        r'"%s: unsupported submode.\\n", __func__);',
    ),
]


def kconfig_block(text: str, option: str) -> str | None:
    lines = text.split("\n")
    for index, line in enumerate(lines):
        if line.strip() not in (f"config {option}", f"menuconfig {option}"):
            continue
        end = index + 1
        while end < len(lines) and not lines[end].startswith(
            ("config ", "menuconfig ", "endif", "endmenu", "menu ", "if ", "source ", "choice", "comment ")
        ):
            end += 1
        return "\n".join(lines[index:end]).rstrip() + "\n"
    return None


def starlark(module: dict[str, object]) -> str:
    def values(key: str, items: list[str]) -> str:
        if not items:
            return ""
        body = "".join(f'            "{item}",\n' for item in items)
        return f"        {key} = [\n            # do not sort\n{body}        ],\n"

    return (
        "\n    registry.register(\n"
        f'        name = "{module["name"]}",\n'
        f'        out = "{module["out"]}",\n'
        f'        config = "{module["config"]}",\n'
        + values("srcs", module["srcs"])
        + values("deps", module["deps"])
        + "    )\n"
    )


def register_modules(soc: str) -> None:
    modules = kb.load_registry(soc)
    for name, template, substitutions in MODULES:
        if name in modules:
            continue
        if template not in modules:
            raise RuntimeError(f"missing module template {template}")
        source = modules[template]

        def substitute(value: str) -> str:
            for old, new in substitutions:
                value = value.replace(old, new)
            return value

        module = {
            "name": name,
            "out": substitute(source["out"]),
            "config": substitute(source["config"]),
            "srcs": [substitute(item) for item in source["srcs"]],
            "deps": list(source["deps"]),
        }
        if name.startswith("drivers/clk/qcom/"):
            header = "drivers/clk/qcom/vdd-level-bengal.h"
            if header not in module["srcs"]:
                module["srcs"].append(header)
        registry = None
        for directory, _, filenames in os.walk(soc):
            if "modules.bzl" not in filenames or "/.git" in directory:
                continue
            candidate = os.path.join(directory, "modules.bzl")
            if f'name = "{template}",' in open(candidate, encoding="utf-8").read():
                registry = candidate
                break
        if registry is None:
            raise RuntimeError(f"registry for template {template} not found")
        with open(registry, "a", encoding="utf-8", newline="\n") as stream:
            stream.write(starlark(module))
        print(f"k618_khaje: registered {name} like {template}")


def main() -> int:
    if len(sys.argv) != 3:
        print(__doc__, file=sys.stderr)
        return 2
    donor, soc = (value.rstrip("/") for value in sys.argv[1:])
    for relative in FILES:
        source = os.path.join(donor, relative)
        if not os.path.isfile(source):
            raise FileNotFoundError(source)
        target = os.path.join(soc, relative)
        os.makedirs(os.path.dirname(target), exist_ok=True)
        shutil.copyfile(source, target)
        print(f"k618_khaje: copied {relative}")

    for relative, option in KCONFIG_FROM_DONOR:
        target = os.path.join(soc, relative)
        target_text = open(target, encoding="utf-8").read()
        if kconfig_block(target_text, option):
            continue
        donor_text = open(os.path.join(donor, relative), encoding="utf-8").read()
        block = kconfig_block(donor_text, option)
        if block is None:
            raise RuntimeError(f"{option} not present in donor {relative}")
        with open(target, "a", encoding="utf-8", newline="\n") as stream:
            stream.write(f"\n# Khaje/SM6225, from MiCode topaz-t-oss\n{block}")
        print(f"k618_khaje: added {option} to {relative}")

    for relative, option, block in KCONFIG_NEW:
        target = os.path.join(soc, relative)
        text = open(target, encoding="utf-8").read()
        if not kconfig_block(text, option):
            with open(target, "a", encoding="utf-8", newline="\n") as stream:
                stream.write(f"\n# Khaje/SM6225\n{block}")
            print(f"k618_khaje: added {option} to {relative}")

    register_modules(soc)
    for relative in FILES:
        target = os.path.join(soc, relative)
        if not target.endswith((".c", ".h")):
            continue
        text = open(target, encoding="utf-8", errors="surrogateescape").read()
        updated = text
        for file_pattern, pattern, replacement in PORT_EDITS:
            if re.fullmatch(file_pattern, relative):
                updated = re.sub(pattern, replacement, updated)
        if updated != text:
            open(target, "w", encoding="utf-8", errors="surrogateescape", newline="").write(updated)
            print(f"k618_khaje: ported {relative}")

    print("k618_khaje: build-only gate imported; SMD/RPM, NoC and remoteproc remain TODO")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
