#!/usr/bin/env python3
"""Generate a modern ACK 6.18 Bengal NoC driver from ACK's SM6115 driver.

The hardware is closely related, but the stock downstream DT uses Bengal's
global binding IDs and adds UFS/PRNG nodes. Keep ACK's current interconnect API
and data model while supplying those target-specific IDs/nodes.
"""

from __future__ import annotations

from pathlib import Path
import shutil
import sys


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if new in text:
        return text
    if old not in text:
        raise RuntimeError(f"{label}: anchor not found: {old!r}")
    return text.replace(old, new, 1)


UFS_MASTER = r'''static struct qcom_icc_node xm_ufs = {
	.name = "xm_ufs",
	.id = SM6115_MASTER_UFS_MEM,
	.channels = 1,
	.buswidth = 8,
	.qos.qos_port = 25,
	.qos.qos_mode = NOC_QOS_MODE_FIXED,
	.qos.areq_prio = 2,
	.mas_rpm_id = -1,
	.slv_rpm_id = -1,
	.num_links = ARRAY_SIZE(link_slv_anoc_snoc),
	.links = link_slv_anoc_snoc,
};

'''

UFS_SLAVES = r'''static struct qcom_icc_node qhs_ufs = {
	.name = "qhs_ufs",
	.id = SM6115_SLAVE_UFS_MEM_CFG,
	.channels = 1,
	.buswidth = 4,
	.mas_rpm_id = -1,
	.slv_rpm_id = -1,
};

static struct qcom_icc_node qhs_prng = {
	.name = "qhs_prng",
	.id = SM6115_SLAVE_PRNG,
	.channels = 1,
	.buswidth = 4,
	.mas_rpm_id = -1,
	.slv_rpm_id = -1,
};

'''


def main() -> int:
    if len(sys.argv) != 3:
        print(f"usage: {sys.argv[0]} ACK_TREE TOPAZ_TREE", file=sys.stderr)
        return 2
    ack, donor = map(Path, sys.argv[1:])
    binding_src = donor / "include/dt-bindings/interconnect/qcom,bengal.h"
    binding_dst = ack / "include/dt-bindings/interconnect/qcom,bengal.h"
    if not binding_src.is_file():
        raise FileNotFoundError(binding_src)
    binding_dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(binding_src, binding_dst)

    source = (ack / "drivers/interconnect/qcom/sm6115.c").read_text()
    text = source.replace("<dt-bindings/interconnect/qcom,sm6115.h>",
                          "<dt-bindings/interconnect/qcom,bengal.h>")
    text = replace_once(text, "\tSM6115_MASTER_USB3,\n",
                        "\tSM6115_MASTER_USB3,\n\tSM6115_MASTER_UFS_MEM,\n", "master enum")
    text = replace_once(text, "\tSM6115_SLAVE_USB3,\n",
                        "\tSM6115_SLAVE_USB3,\n\tSM6115_SLAVE_UFS_MEM_CFG,\n\tSM6115_SLAVE_PRNG,\n",
                        "slave enum")
    text = replace_once(text, "static struct qcom_icc_node xm_usb3_0 = {",
                        UFS_MASTER + "static struct qcom_icc_node xm_usb3_0 = {", "UFS master")
    text = replace_once(text, "static struct qcom_icc_node qhs_security = {",
                        UFS_SLAVES + "static struct qcom_icc_node qhs_security = {", "UFS slaves")
    text = replace_once(text, "\t[SLAVE_SDCC_2] = &qhs_sdc2,\n",
                        "\t[SLAVE_SDCC_2] = &qhs_sdc2,\n"
                        "\t[SLAVE_UFS_MEM_CFG] = &qhs_ufs,\n"
                        "\t[SLAVE_PRNG] = &qhs_prng,\n", "config NoC nodes")
    text = replace_once(text, "\t[MASTER_USB3] = &xm_usb3_0,\n",
                        "\t[MASTER_UFS_MEM] = &xm_ufs,\n"
                        "\t[MASTER_USB3] = &xm_usb3_0,\n", "system NoC nodes")

    replacements = {
        '"qcom,sm6115-bimc"': '"qcom,bengal-bimc"',
        '"qcom,sm6115-clk-virt"': '"qcom,bengal-clk_virt"',
        '"qcom,sm6115-cnoc"': '"qcom,bengal-config_noc"',
        '"qcom,sm6115-mmrt-virt"': '"qcom,bengal-mmrt_virt"',
        '"qcom,sm6115-mmnrt-virt"': '"qcom,bengal-mmnrt_virt"',
        '"qcom,sm6115-snoc"': '"qcom,bengal-system_noc"',
        'qnoc-sm6115': 'qnoc-bengal',
        'SM6115 NoC driver': 'Bengal/SM6225 NoC driver',
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    (ack / "drivers/interconnect/qcom/bengal.c").write_text(text)

    makefile = ack / "drivers/interconnect/qcom/Makefile"
    text = makefile.read_text()
    text = replace_once(text, "qnoc-sm6115-objs\t\t\t:= sm6115.o\n",
                        "qnoc-sm6115-objs\t\t\t:= sm6115.o\n"
                        "qnoc-bengal-objs\t\t\t:= bengal.o\n", "Makefile objects")
    text = replace_once(text, "obj-$(CONFIG_INTERCONNECT_QCOM_SM6115) += qnoc-sm6115.o\n",
                        "obj-$(CONFIG_INTERCONNECT_QCOM_SM6115) += qnoc-sm6115.o\n"
                        "obj-$(CONFIG_INTERCONNECT_QCOM_BENGAL) += qnoc-bengal.o\n", "Makefile target")
    makefile.write_text(text)

    kconfig = ack / "drivers/interconnect/qcom/Kconfig"
    text = kconfig.read_text()
    if "config INTERCONNECT_QCOM_BENGAL" not in text:
        text += r'''

config INTERCONNECT_QCOM_BENGAL
	tristate "Qualcomm Bengal/SM6225 interconnect driver"
	depends on INTERCONNECT_QCOM
	depends on QCOM_SMD_RPM
	select INTERCONNECT_QCOM_SMD_RPM
	help
	  Build the Bengal NoC provider used by downstream Khaje device trees.
'''
        kconfig.write_text(text)

    # Bengal's global binding IDs make each provider array sparse.
    icc = ack / "drivers/interconnect/qcom/icc-rpm.c"
    text = icc.read_text()
    old = "\tfor (i = 0; i < num_nodes; i++) {\n\t\tsize_t j;\n\n\t\tif (!qnodes[i]->ab_coeff)"
    new = "\tfor (i = 0; i < num_nodes; i++) {\n\t\tsize_t j;\n\n\t\tif (!qnodes[i])\n\t\t\tcontinue;\n\n\t\tif (!qnodes[i]->ab_coeff)"
    text = replace_once(text, old, new, "sparse node arrays")
    icc.write_text(text)

    print("k618_bengal_gki: generated modern Bengal NoC with UFS/PRNG nodes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
