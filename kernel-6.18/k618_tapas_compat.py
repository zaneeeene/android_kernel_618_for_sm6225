#!/usr/bin/env python3
"""Import the public/custom Xiaomi first-stage compatibility modules.

These modules expose userspace-facing diagnostics or simple GPIO state. They
are kept separate from the boot-critical Qualcomm platform stack so they can be
audited and omitted independently during early bring-up.
"""

from __future__ import annotations

import os
from pathlib import Path
import re
import shutil
import sys


DONOR_FILES = {
    "drivers/misc/simtray/simtray.c": "simtray.c",
    "drivers/misc/ant_check.c": "ant_check.c",
    "drivers/misc/ant_check_div.c": "ant_check_div.c",
}

CUSTOM_FILES = {
    "k618_mi_memory.c": "mi_memory.c",
    "k618_perf_helper.c": "perf_helper.c",
}

MODULES = [
    ("mi_memory", "CONFIG_TAPAS_MI_MEMORY"),
    ("perf_helper", "CONFIG_TAPAS_PERF_HELPER"),
    ("simtray", "CONFIG_TAPAS_SIMTRAY"),
    ("ant_check", "CONFIG_TAPAS_ANT_CHECK"),
    ("ant_check_div", "CONFIG_TAPAS_ANT_CHECK_DIV"),
]

KCONFIG = r'''

# Redmi Note 12 4G userspace compatibility
config TAPAS_MI_MEMORY
	tristate "Xiaomi mi_memory compatibility interface"
	depends on SCSI_UFSHCD

config TAPAS_PERF_HELPER
	tristate "Xiaomi perf_helper compatibility interface"
	depends on MEMCG

config TAPAS_SIMTRAY
	tristate "Xiaomi SIM tray status"
	depends on GPIOLIB

config TAPAS_ANT_CHECK
	tristate "Xiaomi antenna GPIO status"
	depends on INPUT && GPIOLIB

config TAPAS_ANT_CHECK_DIV
	tristate "Xiaomi diversity antenna GPIO status"
	depends on INPUT && GPIOLIB
'''


def module_registry() -> str:
    registrations = []
    for name, config in MODULES:
        registrations.append(
            f'''    registry.register(
        name = "drivers/soc/qcom/tapas-compat/{name}",
        out = "{name}.ko",
        config = "{config}",
        srcs = [
            "drivers/soc/qcom/tapas-compat/{name}.c",
        ],
    )
'''
        )
    return "def register_modules(registry):\n" + "\n".join(registrations)


def port_gpio_module(path: Path, function: str) -> None:
    text = path.read_text()
    text = text.replace("class_create(THIS_MODULE, ", "class_create(")
    text = re.sub(
        rf"static int ({re.escape(function)}\(struct platform_device \*pdev\)\n\{{.*?)(\n\treturn 0;\n\}})",
        lambda match: "static void " + match.group(1) + "\n}",
        text,
        count=1,
        flags=re.S,
    )
    path.write_text(text)


def main() -> int:
    if len(sys.argv) != 3:
        print(f"usage: {sys.argv[0]} TOPAZ_TREE SOC_TREE", file=sys.stderr)
        return 2
    donor = Path(sys.argv[1])
    soc = Path(sys.argv[2])
    here = Path(__file__).resolve().parent
    target = soc / "drivers/soc/qcom/tapas-compat"
    target.mkdir(parents=True, exist_ok=True)

    for source_name, output_name in DONOR_FILES.items():
        source = donor / source_name
        if not source.is_file():
            raise FileNotFoundError(source)
        shutil.copyfile(source, target / output_name)
    for source_name, output_name in CUSTOM_FILES.items():
        shutil.copyfile(here / source_name, target / output_name)

    # Linux 6.18 platform remove callbacks return void and class_create() no
    # longer accepts THIS_MODULE. Preserve Xiaomi's event numbers locally;
    # upstream assigned names to those numeric slots later.
    port_gpio_module(target / "simtray.c", "simtray_remove")
    port_gpio_module(target / "ant_check.c", "ant_remove")
    port_gpio_module(target / "ant_check_div.c", "ant_div_remove")
    for name, definitions in {
        "ant_check.c": "#define KEY_ANT_CONNECT 0x292\n#define KEY_ANT_UNCONNECT 0x293\n",
        "ant_check_div.c": "#define DIV_ANT_CONNECT 0x294\n#define DIV_ANT_UNCONNECT 0x295\n",
    }.items():
        path = target / name
        text = path.read_text()
        marker = "/* Tapas stock userspace event codes. */"
        if marker not in text:
            anchor = "#define CONFIG_ANT_"
            index = text.index(anchor)
            text = text[:index] + marker + "\n" + definitions + text[index:]
            path.write_text(text)

    (target / "modules.bzl").write_text(module_registry())

    parent = soc / "drivers/soc/qcom/modules.bzl"
    text = parent.read_text()
    load = ('load(":drivers/soc/qcom/tapas-compat/modules.bzl", '
            'register_tapas_compat = "register_modules")\n')
    if load not in text:
        text = load + text
    call = "    register_tapas_compat(registry)\n"
    anchor = "def register_modules(registry):\n"
    if call not in text:
        text = text.replace(anchor, anchor + call, 1)
    parent.write_text(text)

    kconfig = soc / "drivers/soc/qcom/Kconfig"
    text = kconfig.read_text()
    if "config TAPAS_MI_MEMORY" not in text:
        kconfig.write_text(text + KCONFIG)

    print("k618_tapas_compat: imported five public/source-backed compatibility modules")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
