#!/usr/bin/env python3
"""Import public/custom Xiaomi first-stage compatibility modules.

This includes the exact downstream Khaje MPM implementation and target-only
userspace/GPIO interfaces that are not present in the newer SM8850 tree.
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

PLATFORM_FILES = [
    "drivers/irqchip/qcom-mpm.c",
    "include/linux/msm_rtb.h",
    "include/soc/qcom/mpm.h",
    "include/trace/events/mpm.h",
]

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

KHAJE_PAS = r'''
/* Khaje PAS metadata from MiCode topaz-t-oss. */
static const struct adsp_data khaje_adsp_resource = {
	.crash_reason_smem = 423,
	.firmware_name = "adsp.mdt",
	.pas_id = 1,
	.minidump_id = 5,
	.uses_elf64 = false,
	.auto_boot = false,
	.ssr_name = "lpass",
	.sysmon_name = "adsp",
	.ssctl_id = 0x14,
};

static const struct adsp_data khaje_cdsp_resource = {
	.crash_reason_smem = 601,
	.firmware_name = "cdsp.mdt",
	.pas_id = 18,
	.minidump_id = 7,
	.uses_elf64 = false,
	.auto_boot = false,
	.ssr_name = "cdsp",
	.sysmon_name = "cdsp",
	.ssctl_id = 0x17,
};

static const struct adsp_data khaje_mpss_resource = {
	.crash_reason_smem = 421,
	.firmware_name = "modem.mdt",
	.pas_id = 4,
	.minidump_id = 3,
	.uses_elf64 = true,
	.auto_boot = false,
	.ssr_name = "mpss",
	.sysmon_name = "modem",
	.ssctl_id = 0x12,
};
'''

MPM_KCONFIG = r'''

config TAPAS_QCOM_MPM
	tristate "Qualcomm downstream Khaje MPM"
	depends on ARCH_QCOM
	select IRQ_DOMAIN
	select IRQ_DOMAIN_HIERARCHY
'''

MPM_REGISTRY = r'''

    registry.register(
        name = "drivers/irqchip/qcom-mpm-khaje",
        out = "qcom-mpm.ko",
        config = "CONFIG_TAPAS_QCOM_MPM",
        srcs = [
            "drivers/irqchip/qcom-mpm.c",
            "include/linux/msm_rtb.h",
            "include/soc/qcom/mpm.h",
            "include/trace/events/mpm.h",
        ],
    )
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


def insert_before(path: Path, marker: str, anchor: str, addition: str) -> None:
    text = path.read_text()
    if marker in text:
        return
    if anchor not in text:
        raise RuntimeError(f"{path}: anchor not found: {anchor!r}")
    path.write_text(text.replace(anchor, addition + "\n" + anchor, 1))


def port_gpio_module(path: Path, function: str) -> None:
    text = path.read_text()
    text = text.replace("class_create(THIS_MODULE, ", "class_create(")
    text = re.sub(
        r'of_get_named_gpio_flags\((np,\s*"[^"]+",\s*0),\s*&\w+->irq_gpio_flags\)',
        r"of_get_named_gpio(\1)",
        text,
    )
    text = text.replace("struct class *class", "const struct class *class")
    text = text.replace("struct class_attribute *attr", "const struct class_attribute *attr")
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
    for relative in PLATFORM_FILES:
        source = donor / relative
        if not source.is_file():
            raise FileNotFoundError(source)
        output = soc / relative
        output.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, output)
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

    irq_kconfig = soc / "drivers/irqchip/Kconfig"
    text = irq_kconfig.read_text()
    if "config TAPAS_QCOM_MPM" not in text:
        irq_kconfig.write_text(text + MPM_KCONFIG)
    irq_registry = soc / "drivers/irqchip/modules.bzl"
    text = irq_registry.read_text()
    if 'out = "qcom-mpm.ko"' not in text:
        irq_registry.write_text(text.rstrip() + MPM_REGISTRY + "\n")

    mpm_header = soc / "include/soc/qcom/mpm.h"
    text = mpm_header.read_text().replace(
        "#if IS_ENABLED(CONFIG_QCOM_MPM)",
        "#if IS_ENABLED(CONFIG_QCOM_MPM) || IS_ENABLED(CONFIG_TAPAS_QCOM_MPM)",
    )
    mpm_header.write_text(text)

    pas = soc / "drivers/remoteproc/qcom_q6v5_pas.c"
    insert_before(pas, "static const struct adsp_data khaje_adsp_resource",
                  "static const struct adsp_data adsp_resource_init", KHAJE_PAS)
    for compatible, resource, before in [
        ("qcom,khaje-adsp-pas", "khaje_adsp_resource", "qcom,sm6115-adsp-pas"),
        ("qcom,khaje-cdsp-pas", "khaje_cdsp_resource", "qcom,sm6115-cdsp-pas"),
        ("qcom,khaje-modem-pas", "khaje_mpss_resource", "qcom,sm6115-mpss-pas"),
    ]:
        insert_before(pas, f'compatible = "{compatible}"',
                      f'\t{{ .compatible = "{before}",',
                      f'\t{{ .compatible = "{compatible}", .data = &{resource}}},')

    # The target intentionally replaces downstream WALT with schedutilmium.
    # Registry dependencies are unconditional build-graph edges even when
    # CONFIG_SCHED_WALT=n, so remove those edges while retaining each driver's
    # normal Kconfig/IS_ENABLED guards.
    stripped = 0
    for registry in soc.rglob("modules.bzl"):
        text = registry.read_text()
        updated, count = re.subn(
            r'^\s*"kernel/sched/walt/sched-walt",\n', "", text, flags=re.M
        )
        if count:
            registry.write_text(updated)
            stripped += count

    print("k618_tapas_compat: imported exact Khaje MPM/PAS and five source-backed "
          f"compatibility modules; removed {stripped} WALT dependency edges")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
