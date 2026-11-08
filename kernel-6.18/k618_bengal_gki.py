#!/usr/bin/env python3
"""Port MiCode's exact Bengal NoC tables to ACK 6.18.

The target DT uses downstream global interconnect IDs, QoS register offsets,
RPM IDs and two-clock voting. Keep those exact tables and adapt only the Linux
interconnect-provider registration and RPM transport APIs.
"""

from __future__ import annotations

from pathlib import Path
import re
import shutil
import sys


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise RuntimeError(f"{label}: anchor not found: {old!r}")
    return text.replace(old, new, 1)


def donor_text(donor: Path, relative: str) -> str:
    path = donor / relative
    if not path.is_file():
        raise FileNotFoundError(path)
    return path.read_text()


def port_bengal(text: str) -> str:
    if "#include <linux/of.h>" not in text:
        text = text.replace("#include <linux/module.h>\n",
                            "#include <linux/module.h>\n#include <linux/of.h>\n", 1)
    text = text.replace("#include <soc/qcom/rpm-smd.h>\n", "")
    text = text.replace('#include "icc-rpm.h"', '#include "icc-rpm-bengal.h"')
    text = text.replace('#include "rpm-ids.h"', '#include "rpm-ids-bengal.h"')
    text = text.replace('#include "qnoc-qos-rpm.h"', '#include "qnoc-qos-bengal.h"')
    text = replace_once(
        text,
        "\tINIT_LIST_HEAD(&provider->nodes);\n\tprovider->data = data;",
        "\tprovider->data = data;\n\ticc_provider_init(provider);",
        "provider initialization",
    )
    text = replace_once(
        text,
        '''\tret = icc_provider_add(provider);
\tif (ret) {
\t\tdev_err(dev, "error adding interconnect provider: %d\\n", ret);
\t\tclk_bulk_disable_unprepare(qp->num_clks, qp->bus_clks);
\t\treturn ret;
\t}

''',
        "",
        "legacy provider add",
    )
    text = replace_once(
        text,
        "\tdata->num_nodes = num_nodes;\n\n\tclk_bulk_disable_unprepare",
        '''\tdata->num_nodes = num_nodes;

\tret = icc_provider_register(provider);
\tif (ret) {
\t\tdev_err(dev, "error registering interconnect provider: %d\\n", ret);
\t\tgoto err;
\t}

\tclk_bulk_disable_unprepare''',
        "provider registration",
    )
    text = text.replace("\ticc_provider_del(provider);\n", "")
    remove_pattern = re.compile(
        r"static int qnoc_remove\(struct platform_device \*pdev\)\n"
        r"\{.*?\n\}\n\nstatic const struct of_device_id",
        re.S,
    )
    remove_replacement = '''static void qnoc_remove(struct platform_device *pdev)
{
\tstruct qcom_icc_provider *qp = platform_get_drvdata(pdev);
\tstruct icc_provider *provider = &qp->provider;

\tmutex_lock(&probe_list_lock);
\tlist_del(&qp->probe_list);
\tmutex_unlock(&probe_list_lock);
\ticc_provider_deregister(provider);
\ticc_nodes_remove(provider);
\tclk_bulk_disable_unprepare(qp->num_clks, qp->bus_clks);
}

static const struct of_device_id'''
    text, count = remove_pattern.subn(remove_replacement, text, count=1)
    if count != 1:
        raise RuntimeError("remove callback: expected one match")
    return text


def port_rpm_header(text: str) -> str:
    text = text.replace("__DRIVERS_INTERCONNECT_QCOM_ICC_RPM_H",
                        "__DRIVERS_INTERCONNECT_QCOM_ICC_BENGAL_RPM_H")
    text = text.replace("#include <soc/qcom/rpm-smd.h>",
                        "#include <linux/soc/qcom/smd-rpm.h>")
    text = text.replace("MSM_RPM_CTX_SLEEP_SET", "QCOM_SMD_RPM_SLEEP_STATE")
    text = text.replace("MSM_RPM_CTX_ACTIVE_SET", "QCOM_SMD_RPM_ACTIVE_STATE")
    anchor = "int qcom_icc_rpm_aggregate(struct icc_node *node, u32 tag, u32 avg_bw,"
    prototype = ("int qcom_icc_rpm_smd_send(int ctx, int rsc_type, int id, u32 val);\n"
                 + anchor)
    return replace_once(text, anchor, prototype, "RPM transport prototype")


def port_rpm_source(text: str) -> str:
    text = text.replace('#include "icc-rpm.h"', '#include "icc-rpm-bengal.h"')
    text = text.replace('#include "qnoc-qos.h"', '#include "qnoc-qos-bengal.h"')
    text = text.replace("qcom_icc_rpm_smd_send_msg slv %s error %d",
                        "qcom_icc_rpm_smd_send_msg slv %d error %d")
    pattern = re.compile(
        r"static int qcom_icc_rpm_smd_send_msg\(int ctx, int rsc_type, int rpm_id, u64 val\)\n"
        r"\{.*?\n\}\n",
        re.S,
    )
    replacement = '''static int qcom_icc_rpm_smd_send_msg(int ctx, int rsc_type, int rpm_id, u64 val)
{
\tif (val > U32_MAX)
\t\tval = U32_MAX;

\treturn qcom_icc_rpm_smd_send(ctx, rsc_type, rpm_id, (u32)val);
}
'''
    text, count = pattern.subn(replacement, text, count=1)
    if count != 1:
        raise RuntimeError("RPM send bridge: expected one match")
    return text


def port_qos_header(text: str) -> str:
    return text.replace("__DRIVERS_INTERCONNECT_QCOM_QNOC_QOS_RPM_H__",
                        "__DRIVERS_INTERCONNECT_QCOM_QNOC_QOS_BENGAL_H__")


def port_qos_source(text: str) -> str:
    text = text.replace('#include "icc-rpm.h"', '#include "icc-rpm-bengal.h"')
    return text.replace('#include "qnoc-qos-rpm.h"', '#include "qnoc-qos-bengal.h"')


def update_build_files(ack: Path) -> None:
    makefile = ack / "drivers/interconnect/qcom/Makefile"
    text = makefile.read_text()
    object_anchor = "qnoc-sm6115-objs\t\t\t:= sm6115.o\n"
    object_lines = (object_anchor
                    + "qnoc-bengal-objs\t\t\t:= bengal.o\n"
                    + "icc-bengal-rpm-objs\t\t\t:= icc-rpm-bengal.o\n")
    if "qnoc-bengal-objs" not in text:
        text = replace_once(text, object_anchor, object_lines, "Makefile objects")
    target_anchor = "obj-$(CONFIG_INTERCONNECT_QCOM_SM6115) += qnoc-sm6115.o\n"
    target_lines = (target_anchor
                    + "obj-$(CONFIG_INTERCONNECT_QCOM_BENGAL) += qnoc-bengal.o\n"
                    + "obj-$(CONFIG_INTERCONNECT_QCOM_BENGAL) += icc-bengal-rpm.o\n"
                    + "obj-$(CONFIG_INTERCONNECT_QCOM_BENGAL) += qnoc-qos-bengal.o\n")
    if "icc-bengal-rpm.o" not in text.split(target_anchor, 1)[-1]:
        text = replace_once(text, target_anchor, target_lines, "Makefile targets")
    makefile.write_text(text)

    kconfig = ack / "drivers/interconnect/qcom/Kconfig"
    text = kconfig.read_text()
    if "config INTERCONNECT_QCOM_BENGAL" not in text:
        text += '''

config INTERCONNECT_QCOM_BENGAL
\ttristate "Qualcomm Bengal/SM6225 downstream interconnect"
\tdepends on INTERCONNECT_QCOM
\tdepends on QCOM_SMD_RPM
\tselect INTERCONNECT_QCOM_SMD_RPM
\thelp
\t  Exact Bengal topology, RPM IDs and QoS offsets used by Khaje DTs.
'''
        kconfig.write_text(text)


def main() -> int:
    if len(sys.argv) != 3:
        print(f"usage: {sys.argv[0]} ACK_TREE TOPAZ_TREE", file=sys.stderr)
        return 2
    ack, donor = map(Path, sys.argv[1:])
    qcom = ack / "drivers/interconnect/qcom"

    binding = donor / "include/dt-bindings/interconnect/qcom,bengal.h"
    binding_out = ack / "include/dt-bindings/interconnect/qcom,bengal.h"
    binding_out.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(binding, binding_out)

    outputs = {
        "bengal.c": port_bengal(donor_text(donor, "drivers/interconnect/qcom/bengal.c")),
        "icc-rpm-bengal.c": port_rpm_source(
            donor_text(donor, "drivers/interconnect/qcom/icc-rpm.c")
        ),
        "icc-rpm-bengal.h": port_rpm_header(
            donor_text(donor, "drivers/interconnect/qcom/icc-rpm.h")
        ),
        "qnoc-qos-bengal.c": port_qos_source(
            donor_text(donor, "drivers/interconnect/qcom/qnoc-qos-rpm.c")
        ),
        "qnoc-qos-bengal.h": port_qos_header(
            donor_text(donor, "drivers/interconnect/qcom/qnoc-qos-rpm.h")
        ),
        "rpm-ids-bengal.h": donor_text(donor, "drivers/interconnect/qcom/rpm-ids.h"),
    }
    for name, text in outputs.items():
        (qcom / name).write_text(text)
    update_build_files(ack)
    print("k618_bengal_gki: ported exact downstream Bengal topology to ACK 6.18 APIs")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
