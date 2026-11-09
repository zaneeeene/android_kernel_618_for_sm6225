#!/usr/bin/env python3
"""Import public Tapas daily-hardware modules absent from the SM8850 tree."""

from __future__ import annotations

from pathlib import Path
import shutil
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from k618_tapas_legacy import port_remove  # noqa: E402


FILES = [
    "drivers/cpufreq/cpumaxfreq.c",
    "drivers/soc/qcom/cx_ipeak.c",
    "drivers/soc/qcom/qdsp6v2/cdsp-loader.c",
    "drivers/soc/qcom/rpm-smd-debug.c",
    "drivers/soc/qcom/rpm_master_stat.c",
    "drivers/soc/qcom/serial_num.c",
    "drivers/thermal/qcom/lmh_cpu_vdd_cdev.c",
    "drivers/thermal/qcom/cx_ipeak_cdev.c",
    "drivers/thermal/qcom/regulator_cdev.c",
    "drivers/thermal/qcom/rpm_smd_cooling_device.c",
    "drivers/thermal/qcom/qmi_sensors.c",
    "drivers/thermal/qcom/qmi_sensors.h",
    "drivers/thermal/qcom/thermal_sensor_service_v01.c",
    "drivers/thermal/qcom/thermal_sensor_service_v01.h",
    "drivers/thermal/mi_thermal_interface.c",
    "include/soc/qcom/cx_ipeak.h",
]

KCONFIG = r'''

config TAPAS_LMH_CPU_VDD_CDEV
	tristate "Tapas LMH CPU VDD cooling device"
	depends on THERMAL && THERMAL_OF

config TAPAS_CX_IPEAK_CDEV
	tristate "Tapas CX IPeak cooling device"
	depends on THERMAL && THERMAL_OF

config TAPAS_REGULATOR_CDEV
	tristate "Tapas regulator cooling device"
	depends on REGULATOR && THERMAL_OF

config TAPAS_RPM_SMD_COOLING
	tristate "Tapas RPM SMD cooling device"
	depends on TAPAS_RPM_SMD && THERMAL_OF

config TAPAS_QMI_THERMAL_SENSOR
	tristate "Tapas remote QMI thermal sensors"
	depends on QCOM_QMI_HELPERS && THERMAL

config TAPAS_MI_THERMAL_INTERFACE
	tristate "Tapas Xiaomi thermal userspace interface"
	depends on THERMAL

config TAPAS_CPUMAXFREQ
	tristate "Tapas cpumaxfreq userspace interface"

config TAPAS_CX_IPEAK
	tristate "Tapas CX IPeak hardware"

config TAPAS_CDSP_LOADER
	tristate "Tapas CDSP userspace loader"

config TAPAS_RPM_SMD_DEBUG
	tristate "Tapas RPM SMD debug interface"
	depends on TAPAS_RPM_SMD

config TAPAS_RPM_MASTER_STAT
	tristate "Tapas RPM master statistics"

config TAPAS_SERIAL_NUM
	tristate "Tapas serial-number fuse interface"
'''

REGISTRY = r'''def register_modules(registry):
    registry.register(
        name = "drivers/thermal/qcom/lmh_cpu_vdd_cdev-tapas",
        out = "lmh_cpu_vdd_cdev.ko",
        config = "CONFIG_TAPAS_LMH_CPU_VDD_CDEV",
        srcs = ["drivers/thermal/qcom/lmh_cpu_vdd_cdev.c"],
    )
    registry.register(
        name = "drivers/thermal/qcom/cx_ipeak_cdev-tapas",
        out = "cx_ipeak_cdev.ko",
        config = "CONFIG_TAPAS_CX_IPEAK_CDEV",
        srcs = ["drivers/thermal/qcom/cx_ipeak_cdev.c"],
    )
    registry.register(
        name = "drivers/thermal/qcom/regulator_cdev-tapas",
        out = "regulator_cdev.ko",
        config = "CONFIG_TAPAS_REGULATOR_CDEV",
        srcs = ["drivers/thermal/qcom/regulator_cdev.c"],
    )
    registry.register(
        name = "drivers/thermal/qcom/rpm_smd_cooling_device-tapas",
        out = "rpm_smd_cooling_device.ko",
        config = "CONFIG_TAPAS_RPM_SMD_COOLING",
        srcs = ["drivers/thermal/qcom/rpm_smd_cooling_device.c"],
        deps = ["drivers/rpmsg/rpm-smd-tapas"],
    )
    registry.register(
        name = "drivers/thermal/qcom/qti_qmi_sensor-tapas",
        out = "qti_qmi_sensor.ko",
        config = "CONFIG_TAPAS_QMI_THERMAL_SENSOR",
        srcs = [
            "drivers/thermal/qcom/thermal_sensor_service_v01.c",
            "drivers/thermal/qcom/thermal_sensor_service_v01.h",
            "drivers/thermal/qcom/qmi_sensors.c",
            "drivers/thermal/qcom/qmi_sensors.h",
        ],
        deps = ["drivers/soc/qcom/qmi_helpers"],
    )
    registry.register(
        name = "drivers/thermal/mi_thermal_interface-tapas",
        out = "mi_thermal_interface.ko",
        config = "CONFIG_TAPAS_MI_THERMAL_INTERFACE",
        srcs = ["drivers/thermal/mi_thermal_interface.c"],
        deps = ["drivers/soc/qcom/panel_event_notifier"],
    )
    registry.register(
        name = "drivers/cpufreq/cpumaxfreq-tapas",
        out = "cpumaxfreq.ko",
        config = "CONFIG_TAPAS_CPUMAXFREQ",
        srcs = ["drivers/cpufreq/cpumaxfreq.c"],
    )
    registry.register(
        name = "drivers/soc/qcom/cx_ipeak-tapas",
        out = "cx_ipeak.ko",
        config = "CONFIG_TAPAS_CX_IPEAK",
        srcs = ["drivers/soc/qcom/cx_ipeak.c", "include/soc/qcom/cx_ipeak.h"],
    )
    registry.register(
        name = "drivers/soc/qcom/cdsp-loader-tapas",
        out = "cdsp-loader.ko",
        config = "CONFIG_TAPAS_CDSP_LOADER",
        srcs = ["drivers/soc/qcom/qdsp6v2/cdsp-loader.c"],
        deps = ["drivers/remoteproc/qcom_q6v5_pas"],
    )
    registry.register(
        name = "drivers/soc/qcom/rpm-smd-debug-tapas",
        out = "rpm-smd-debug.ko",
        config = "CONFIG_TAPAS_RPM_SMD_DEBUG",
        srcs = ["drivers/soc/qcom/rpm-smd-debug.c"],
        deps = ["drivers/rpmsg/rpm-smd-tapas"],
    )
    registry.register(
        name = "drivers/soc/qcom/rpm-master-stat-tapas",
        out = "rpm_master_stat.ko",
        config = "CONFIG_TAPAS_RPM_MASTER_STAT",
        srcs = ["drivers/soc/qcom/rpm_master_stat.c"],
    )
    registry.register(
        name = "drivers/soc/qcom/serial-num-tapas",
        out = "serial_num.ko",
        config = "CONFIG_TAPAS_SERIAL_NUM",
        srcs = ["drivers/soc/qcom/serial_num.c"],
    )
'''


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

    for relative, function in [
        ("drivers/thermal/qcom/lmh_cpu_vdd_cdev.c", "lmh_cpu_vdd_remove"),
        ("drivers/thermal/qcom/cx_ipeak_cdev.c", "cxip_lm_cdev_remove"),
        ("drivers/thermal/qcom/rpm_smd_cooling_device.c", "rpm_smd_cdev_remove"),
        ("drivers/thermal/qcom/qmi_sensors.c", "qmi_sens_device_remove"),
        ("drivers/soc/qcom/qdsp6v2/cdsp-loader.c", "cdsp_loader_remove"),
        ("drivers/soc/qcom/rpm_master_stat.c", "msm_rpm_master_stats_remove"),
        ("drivers/soc/qcom/serial_num.c", "sn_fuse_remove"),
    ]:
        port_remove(soc / relative, function)

    mi_thermal = soc / "drivers/thermal/mi_thermal_interface.c"
    text = mi_thermal.read_text()
    text = text.replace('#include "../base/base.h"', '#include "drivers/base/base.h"')
    text = text.replace('#include "thermal_core.h"',
                        '#include "drivers/thermal/thermal_core.h"')
    mi_thermal.write_text(text)

    lmh = soc / "drivers/thermal/qcom/lmh_cpu_vdd_cdev.c"
    text = lmh.read_text()
    if "#include <linux/platform_device.h>" not in text:
        text = text.replace("#include <linux/module.h>\n",
                            "#include <linux/module.h>\n#include <linux/platform_device.h>\n", 1)
    lmh.write_text(text)

    qmi = soc / "drivers/thermal/qcom/qmi_sensors.c"
    text = qmi.read_text()
    if '#include "drivers/thermal/thermal_core.h"' not in text:
        text = text.replace("#include <linux/thermal.h>\n",
                            '#include <linux/thermal.h>\n#include "drivers/thermal/thermal_core.h"\n', 1)
    text = text.replace(
        "static int qmi_sensor_read(void *data, int *temp)\n{\n"
        "\tstruct qmi_sensor *qmi_sens = (struct qmi_sensor *)data;",
        "static int qmi_sensor_read(struct thermal_zone_device *tz, int *temp)\n{\n"
        "\tstruct qmi_sensor *qmi_sens = tz->devdata;",
    )
    text = text.replace(
        "static int qmi_sensor_set_trips(void *data, int low, int high)\n{\n"
        "\tstruct qmi_sensor *qmi_sens = (struct qmi_sensor *)data;",
        "static int qmi_sensor_set_trips(struct thermal_zone_device *tz, int low, int high)\n{\n"
        "\tstruct qmi_sensor *qmi_sens = tz->devdata;",
    )
    text = text.replace("struct thermal_zone_of_device_ops qmi_sensor_ops",
                        "struct thermal_zone_device_ops qmi_sensor_ops")
    text = text.replace("thermal_zone_of_sensor_register(",
                        "devm_thermal_of_zone_register(")
    text = text.replace("thermal_zone_of_sensor_unregister(",
                        "devm_thermal_of_zone_unregister(")
    qmi.write_text(text)

    registry_dir = soc / "drivers/soc/qcom/tapas-daily"
    registry_dir.mkdir(parents=True, exist_ok=True)
    (registry_dir / "modules.bzl").write_text(REGISTRY)
    parent = soc / "drivers/soc/qcom/modules.bzl"
    text = parent.read_text()
    load = ('load(":drivers/soc/qcom/tapas-daily/modules.bzl", '
            'register_tapas_daily = "register_modules")\n')
    if load not in text:
        text = load + text
    call = "    register_tapas_daily(registry)\n"
    anchor = "def register_modules(registry):\n"
    if call not in text:
        text = text.replace(anchor, anchor + call, 1)
    parent.write_text(text)

    kconfig = soc / "drivers/soc/qcom/Kconfig"
    text = kconfig.read_text()
    if "config TAPAS_LMH_CPU_VDD_CDEV" not in text:
        kconfig.write_text(text + KCONFIG)
    print("k618_tapas_daily: imported six thermal and six platform compatibility modules")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
