#!/usr/bin/env python3
"""Import Tapas' exact downstream SMD/RPM and Bengal interconnect stack.

ACK's legacy Qualcomm drivers are useful API references, but the stock DT uses
the older resource/child regulator binding and two-clock Bengal provider. This
keeps those target ABIs while adapting provider/remove APIs to Linux 6.18.
"""

from __future__ import annotations

from pathlib import Path
import re
import shutil
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from k618_bengal_gki import port_bengal as port_bengal_provider  # noqa: E402


FILES = [
    "drivers/rpmsg/rpm-smd.c",
    "drivers/clk/qcom/clk-smd-rpm.c",
    "drivers/regulator/rpm-smd-regulator.c",
    "drivers/interconnect/qcom/bengal.c",
    "drivers/interconnect/qcom/icc-rpm.c",
    "drivers/interconnect/qcom/icc-rpm.h",
    "drivers/interconnect/qcom/qnoc-qos-rpm.c",
    "drivers/interconnect/qcom/qnoc-qos-rpm.h",
    "drivers/interconnect/qcom/rpm-ids.h",
    "include/soc/qcom/rpm-smd.h",
    "include/soc/qcom/rpm-notifier.h",
    "include/trace/events/trace_rpm_smd.h",
    "include/linux/regulator/rpm-smd-regulator.h",
    "include/dt-bindings/clock/qcom,rpmcc.h",
]

KCONFIG = r'''

config TAPAS_RPM_SMD
	tristate "Tapas downstream RPM over SMD transport"
	depends on RPMSG && ARCH_QCOM

config TAPAS_CLK_SMD_RPM
	tristate "Tapas downstream SMD RPM clocks"
	depends on TAPAS_RPM_SMD

config TAPAS_GLINK_RPM
	tristate "Tapas GLINK RPM transport"
	depends on RPMSG

config TAPAS_RPM_SMD_REGULATOR
	tristate "Tapas downstream SMD RPM regulators"
	depends on TAPAS_RPM_SMD

config TAPAS_BENGAL_QOS_RPM
	tristate "Tapas Bengal RPM QoS helpers"

config TAPAS_BENGAL_ICC_RPM
	tristate "Tapas Bengal RPM vote helpers"
	depends on TAPAS_RPM_SMD && TAPAS_BENGAL_QOS_RPM

config TAPAS_BENGAL_INTERCONNECT
	tristate "Tapas exact Bengal interconnect"
	depends on TAPAS_BENGAL_ICC_RPM && TAPAS_BENGAL_QOS_RPM
'''

REGISTRY = r'''def register_modules(registry):
    registry.register(
        name = "drivers/rpmsg/rpm-smd-tapas",
        out = "rpm-smd.ko",
        config = "CONFIG_TAPAS_RPM_SMD",
        srcs = [
            "drivers/rpmsg/rpm-smd.c",
            "include/soc/qcom/rpm-smd.h",
            "include/soc/qcom/rpm-notifier.h",
            "include/trace/events/trace_rpm_smd.h",
        ],
        deps = [
            "drivers/irqchip/qcom-mpm-khaje",
        ],
    )

    registry.register(
        name = "drivers/clk/qcom/clk-smd-rpm-tapas",
        out = "clk-smd-rpm.ko",
        config = "CONFIG_TAPAS_CLK_SMD_RPM",
        srcs = [
            "drivers/clk/qcom/clk-smd-rpm.c",
        ],
        deps = [
            "drivers/rpmsg/rpm-smd-tapas",
        ],
    )

    registry.register(
        name = "drivers/rpmsg/qcom-glink-rpm-tapas",
        out = "qcom_glink_rpm.ko",
        config = "CONFIG_TAPAS_GLINK_RPM",
        srcs = [
            "drivers/rpmsg/qcom_glink_rpm.c",
            "drivers/rpmsg/qcom_glink_native.h",
            "drivers/rpmsg/rpmsg_internal.h",
        ],
        deps = [
            "drivers/rpmsg/qcom_glink",
        ],
    )

    registry.register(
        name = "drivers/regulator/rpm-smd-regulator-tapas",
        out = "rpm-smd-regulator.ko",
        config = "CONFIG_TAPAS_RPM_SMD_REGULATOR",
        srcs = [
            "drivers/regulator/rpm-smd-regulator.c",
            "include/linux/regulator/rpm-smd-regulator.h",
        ],
        deps = [
            "drivers/rpmsg/rpm-smd-tapas",
            "drivers/regulator/proxy-consumer",
            "drivers/regulator/debug-regulator",
        ],
    )

    registry.register(
        name = "drivers/interconnect/qcom/qnoc-qos-rpm-tapas",
        out = "qnoc-qos-rpm.ko",
        config = "CONFIG_TAPAS_BENGAL_QOS_RPM",
        srcs = [
            "drivers/interconnect/qcom/qnoc-qos-rpm.c",
            "drivers/interconnect/qcom/qnoc-qos-rpm.h",
        ],
    )

    registry.register(
        name = "drivers/interconnect/qcom/icc-rpm-tapas",
        out = "icc-rpm.ko",
        config = "CONFIG_TAPAS_BENGAL_ICC_RPM",
        srcs = [
            "drivers/interconnect/qcom/icc-rpm.c",
            "drivers/interconnect/qcom/icc-rpm.h",
        ],
        deps = [
            "drivers/rpmsg/rpm-smd-tapas",
            "drivers/interconnect/qcom/qnoc-qos-rpm-tapas",
        ],
    )

    registry.register(
        name = "drivers/interconnect/qcom/qnoc-bengal-tapas",
        out = "qnoc-bengal.ko",
        config = "CONFIG_TAPAS_BENGAL_INTERCONNECT",
        srcs = [
            "drivers/interconnect/qcom/bengal.c",
            "drivers/interconnect/qcom/rpm-ids.h",
            "include/dt-bindings/interconnect/qcom,bengal.h",
        ],
        deps = [
            "drivers/clk/qcom/clk-smd-rpm-tapas",
            "drivers/interconnect/qcom/icc-rpm-tapas",
            "drivers/interconnect/qcom/qnoc-qos-rpm-tapas",
        ],
    )
'''


def port_remove(path: Path, function: str) -> None:
    text = path.read_text()
    signature = f"static int {function}(struct platform_device *pdev)"
    start = text.find(signature)
    if start < 0:
        raise RuntimeError(f"{path}: remove callback {function} not found")
    brace = text.index("{", start)
    depth = 0
    end = None
    for index in range(brace, len(text)):
        if text[index] == "{":
            depth += 1
        elif text[index] == "}":
            depth -= 1
            if depth == 0:
                end = index + 1
                break
    if end is None:
        raise RuntimeError(f"{path}: unterminated callback {function}")
    block = text[start:end].replace(signature, signature.replace("static int", "static void"), 1)
    block = block.replace("return -EINVAL;", "return;")
    block = re.sub(r"\n\treturn 0;\n\}$", "\n}", block)
    text = text[:start] + block + text[end:]
    path.write_text(text)


def main() -> int:
    if len(sys.argv) != 3:
        print(f"usage: {sys.argv[0]} TOPAZ_TREE SOC_TREE", file=sys.stderr)
        return 2
    donor, soc = map(Path, sys.argv[1:])

    for relative in FILES:
        source = donor / relative
        if not source.is_file():
            raise FileNotFoundError(source)
        output = soc / relative
        output.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, output)

    # Keep the old names local to this external stack rather than enabling the
    # unrelated same-name options in ACK's native Kconfig.
    for relative in FILES:
        output = soc / relative
        if output.suffix not in (".c", ".h"):
            continue
        text = output.read_text()
        text = text.replace("CONFIG_MSM_RPM_SMD", "CONFIG_TAPAS_RPM_SMD")
        text = text.replace("CONFIG_RPM_SMD_REGULATOR", "CONFIG_TAPAS_RPM_SMD_REGULATOR")
        output.write_text(text)

    rpm = soc / "drivers/rpmsg/rpm-smd.c"
    text = rpm.read_text()
    if "struct smd_channel;" not in text:
        text = text.replace("#define DEFAULT_BUFFER_SIZE", "struct smd_channel;\n\n#define DEFAULT_BUFFER_SIZE", 1)
    if "MODULE_DEVICE_TABLE(of, rpm_of_match);" not in text:
        text = text.replace(
            '''static const struct of_device_id rpm_of_match[] = {
\t{ .compatible = "qcom,rpm-smd" },
\t{},
};''',
            '''static const struct of_device_id rpm_of_match[] = {
\t{ .compatible = "qcom,rpm-smd" },
\t{},
};
MODULE_DEVICE_TABLE(of, rpm_of_match);''',
            1,
        )
    rpm.write_text(text)

    clock = soc / "drivers/clk/qcom/clk-smd-rpm.c"
    port_remove(clock, "rpm_smd_clk_remove")
    text = clock.read_text()
    text = re.sub(
        r"\nstruct clk_smd_rpm_req \{\n.*?\n\};\n",
        "\n",
        text,
        count=1,
        flags=re.S,
    )
    text = text.replace("QCOM_SMD_RPM_MMXI_CLK", "QCOM_SMD_RPM_MMAXI_CLK")
    text = text.replace("\tdevm_of_clk_del_provider(&pdev->dev);\n", "")
    clock.write_text(text)

    regulator = soc / "drivers/regulator/rpm-smd-regulator.c"
    port_remove(regulator, "rpm_vreg_device_remove")
    port_remove(regulator, "rpm_vreg_resource_remove")
    text = regulator.read_text()
    if "#include <linux/of_platform.h>" not in text:
        text = text.replace("#include <linux/of_device.h>\n",
                            "#include <linux/of_device.h>\n#include <linux/of_platform.h>\n", 1)
    text = text.replace("regulator_register(&reg->rdesc, &reg_config)",
                        "regulator_register(dev, &reg->rdesc, &reg_config)")
    resource_anchor = '''static const struct of_device_id rpm_vreg_match_table_resource[] = {
\t{ .compatible = "qcom,rpm-smd-regulator-resource", },
\t{}
};'''
    if "MODULE_DEVICE_TABLE(of, rpm_vreg_match_table_device);" not in text:
        text = text.replace(
            resource_anchor,
            resource_anchor
            + "\nMODULE_DEVICE_TABLE(of, rpm_vreg_match_table_device);"
            + "\nMODULE_DEVICE_TABLE(of, rpm_vreg_match_table_resource);",
            1,
        )
    regulator.write_text(text)

    bengal = soc / "drivers/interconnect/qcom/bengal.c"
    text = port_bengal_provider(bengal.read_text())
    text = text.replace('#include "icc-rpm-bengal.h"', '#include "icc-rpm.h"')
    text = text.replace('#include "rpm-ids-bengal.h"', '#include "rpm-ids.h"')
    text = text.replace('#include "qnoc-qos-bengal.h"', '#include "qnoc-qos-rpm.h"')
    include_anchor = "#include <linux/soc/qcom/smd-rpm.h>\n"
    if "#include <soc/qcom/rpm-smd.h>" not in text:
        text = text.replace(include_anchor, include_anchor + "#include <soc/qcom/rpm-smd.h>\n", 1)
    bengal.write_text(text)

    icc = soc / "drivers/interconnect/qcom/icc-rpm.c"
    text = icc.read_text().replace('#include "qnoc-qos.h"',
                                   '#include "qnoc-qos-rpm.h"').replace(
        "qcom_icc_rpm_smd_send_msg slv %s error %d",
        "qcom_icc_rpm_smd_send_msg slv %d error %d",
    )
    icc.write_text(text)

    registry_dir = soc / "drivers/soc/qcom/tapas-legacy"
    registry_dir.mkdir(parents=True, exist_ok=True)
    (registry_dir / "modules.bzl").write_text(REGISTRY)
    parent = soc / "drivers/soc/qcom/modules.bzl"
    text = parent.read_text()
    load = ('load(":drivers/soc/qcom/tapas-legacy/modules.bzl", '
            'register_tapas_legacy = "register_modules")\n')
    if load not in text:
        text = load + text
    call = "    register_tapas_legacy(registry)\n"
    anchor = "def register_modules(registry):\n"
    if call not in text:
        text = text.replace(anchor, anchor + call, 1)
    parent.write_text(text)

    kconfig = soc / "drivers/soc/qcom/Kconfig"
    text = kconfig.read_text()
    if "config TAPAS_RPM_SMD" not in text:
        kconfig.write_text(text + KCONFIG)

    print("k618_tapas_legacy: imported exact RPM clocks, regulators and Bengal NoC")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
