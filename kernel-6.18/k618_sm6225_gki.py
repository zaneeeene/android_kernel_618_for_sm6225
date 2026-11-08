#!/usr/bin/env python3
"""Add Khaje-compatible match data to ACK's native SM6115-era drivers."""

from __future__ import annotations

from pathlib import Path
import sys


KHAJE_CLOCKS = r'''
/*
 * Khaje/SM6225 downstream RPM clock map, expressed with ACK 6.18's
 * clk-smd-rpm objects. The resource IDs match MiCode topaz-t-oss.
 */
static struct clk_smd_rpm *khaje_clks[] = {
	[RPM_SMD_XO_CLK_SRC] = &clk_smd_rpm_branch_bi_tcxo,
	[RPM_SMD_XO_A_CLK_SRC] = &clk_smd_rpm_branch_bi_tcxo_a,
	[RPM_SMD_SNOC_CLK] = &clk_smd_rpm_bus_2_snoc_clk,
	[RPM_SMD_SNOC_A_CLK] = &clk_smd_rpm_bus_2_snoc_a_clk,
	[RPM_SMD_BIMC_CLK] = &clk_smd_rpm_bimc_clk,
	[RPM_SMD_BIMC_A_CLK] = &clk_smd_rpm_bimc_a_clk,
	[RPM_SMD_QDSS_CLK] = &clk_smd_rpm_branch_qdss_clk,
	[RPM_SMD_QDSS_A_CLK] = &clk_smd_rpm_branch_qdss_a_clk,
	[RPM_SMD_RF_CLK1] = &clk_smd_rpm_rf_clk1,
	[RPM_SMD_RF_CLK1_A] = &clk_smd_rpm_rf_clk1_a,
	[RPM_SMD_RF_CLK2] = &clk_smd_rpm_rf_clk2,
	[RPM_SMD_RF_CLK2_A] = &clk_smd_rpm_rf_clk2_a,
	[RPM_SMD_CNOC_CLK] = &clk_smd_rpm_bus_1_cnoc_clk,
	[RPM_SMD_CNOC_A_CLK] = &clk_smd_rpm_bus_1_cnoc_a_clk,
	[RPM_SMD_IPA_CLK] = &clk_smd_rpm_ipa_clk,
	[RPM_SMD_IPA_A_CLK] = &clk_smd_rpm_ipa_a_clk,
	[RPM_SMD_QUP_CLK] = &clk_smd_rpm_qup_clk,
	[RPM_SMD_QUP_A_CLK] = &clk_smd_rpm_qup_a_clk,
	[RPM_SMD_MMRT_CLK] = &clk_smd_rpm_mmrt_clk,
	[RPM_SMD_MMRT_A_CLK] = &clk_smd_rpm_mmrt_a_clk,
	[RPM_SMD_MMNRT_CLK] = &clk_smd_rpm_mmnrt_clk,
	[RPM_SMD_MMNRT_A_CLK] = &clk_smd_rpm_mmnrt_a_clk,
	[RPM_SMD_SNOC_PERIPH_CLK] = &clk_smd_rpm_bus_0_snoc_periph_clk,
	[RPM_SMD_SNOC_PERIPH_A_CLK] = &clk_smd_rpm_bus_0_snoc_periph_a_clk,
	[RPM_SMD_SNOC_LPASS_CLK] = &clk_smd_rpm_bus_5_snoc_lpass_clk,
	[RPM_SMD_SNOC_LPASS_A_CLK] = &clk_smd_rpm_bus_5_snoc_lpass_a_clk,
	[RPM_SMD_CE1_CLK] = &clk_smd_rpm_ce1_clk,
	[RPM_SMD_CE1_A_CLK] = &clk_smd_rpm_ce1_a_clk,
};

static const struct rpm_smd_clk_desc rpm_clk_khaje = {
	.clks = khaje_clks,
	.num_clks = ARRAY_SIZE(khaje_clks),
	.icc_clks = sm_qnoc_icc_clks,
	.num_icc_clks = ARRAY_SIZE(sm_qnoc_icc_clks),
};
'''


def insert_before(path: Path, marker: str, anchor: str, addition: str) -> None:
    text = path.read_text()
    if marker in text:
        return
    if anchor not in text:
        raise RuntimeError(f"{path}: anchor not found: {anchor!r}")
    path.write_text(text.replace(anchor, addition + "\n" + anchor, 1))
    print(f"k618_sm6225_gki: updated {path}")


def main() -> int:
    if len(sys.argv) != 2:
        print(f"usage: {sys.argv[0]} ACK_TREE", file=sys.stderr)
        return 2
    root = Path(sys.argv[1])

    clocks = root / "drivers/clk/qcom/clk-smd-rpm.c"
    insert_before(clocks, "static struct clk_smd_rpm *khaje_clks[]", 
                  "static struct clk_smd_rpm *sm6375_clks[]", KHAJE_CLOCKS)
    insert_before(clocks, 'compatible = "qcom,rpmcc-khaje"',
                  '\t{ .compatible = "qcom,rpmcc-sm6115",  .data = &rpm_clk_sm6115  },',
                  '\t{ .compatible = "qcom,rpmcc-khaje",  .data = &rpm_clk_khaje  },')

    apcs = root / "drivers/mailbox/qcom-apcs-ipc-mailbox.c"
    insert_before(apcs, 'compatible = "qcom,bengal-apcs-hmss-global"',
                  '\t{ .compatible = "qcom,qcm2290-apcs-hmss-global", .data = &msm8994_apcs_data },',
                  '\t{ .compatible = "qcom,bengal-apcs-hmss-global", .data = &msm8994_apcs_data },')

    pas = root / "drivers/remoteproc/qcom_q6v5_pas.c"
    aliases = [
        ("qcom,khaje-adsp-pas", "adsp_resource_init", "qcom,sm6115-adsp-pas"),
        ("qcom,khaje-cdsp-pas", "cdsp_resource_init", "qcom,sm6115-cdsp-pas"),
        ("qcom,khaje-modem-pas", "sc8180x_mpss_resource", "qcom,sm6115-mpss-pas"),
    ]
    for compatible, data, before in aliases:
        insert_before(pas, f'compatible = "{compatible}"',
                      f'\t{{ .compatible = "{before}",',
                      f'\t{{ .compatible = "{compatible}", .data = &{data}}},')

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
