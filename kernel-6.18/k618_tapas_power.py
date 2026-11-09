#!/usr/bin/env python3
"""Import the public MiCode non-PMI charging/Type-C stack for Tapas."""

from __future__ import annotations

from pathlib import Path
import re
import shutil
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from k618_tapas_legacy import port_remove  # noqa: E402


TCPC_CLASS_SOURCES = [
    "pd_core.c", "pd_dbg_info.c", "pd_dpm_alt_mode_dc.c", "pd_dpm_alt_mode_dp.c",
    "pd_dpm_core.c", "pd_dpm_pdo_select.c", "pd_dpm_reaction.c", "pd_dpm_uvdm.c",
    "pd_policy_engine.c", "pd_policy_engine_com.c", "pd_policy_engine_dbg.c",
    "pd_policy_engine_dfp.c", "pd_policy_engine_dr.c", "pd_policy_engine_drs.c",
    "pd_policy_engine_prs.c", "pd_policy_engine_snk.c", "pd_policy_engine_src.c",
    "pd_policy_engine_ufp.c", "pd_policy_engine_vcs.c", "pd_process_evt.c",
    "pd_process_evt_com.c", "pd_process_evt_dbg.c", "pd_process_evt_drs.c",
    "pd_process_evt_prs.c", "pd_process_evt_snk.c", "pd_process_evt_src.c",
    "pd_process_evt_tcp.c", "pd_process_evt_vcs.c", "pd_process_evt_vdm.c",
    "rt-regmap.c", "tcpci.c", "tcpci_alert.c", "tcpci_core.c", "tcpci_dual_role.c",
    "tcpci_event.c", "tcpci_timer.c", "tcpci_typec.c", "tcpm.c",
]

TOP_FILES = [
    "drivers/power/supply/nopmi_chg.c",
    "drivers/power/supply/nopmi_chg.h",
    "drivers/power/supply/nopmi_chg_common.c",
    "drivers/power/supply/nopmi_chg_common.h",
    "drivers/power/supply/nopmi_chg_iio.h",
    "drivers/power/supply/nopmi_chg_jeita.c",
    "drivers/power/supply/nopmi_chg_jeita.h",
    "drivers/power/supply/pd_policy_manager.c",
    "drivers/power/supply/pd_policy_manager.h",
    "drivers/power/supply/touch-charger.h",
    "include/linux/pmic-voter.h",
    "include/linux/qti_power_supply.h",
    "include/linux/usb/class-dual-role.h",
    "include/linux/usb/usbpd.h",
    "include/dt-bindings/iio/qti_power_supply_iio.h",
]

KCONFIG = r'''

config RT_REGMAP
	bool
	default y
config USB_POWER_DELIVERY
	bool
	default y
config PD_DBG_INFO
	bool
	default y
config TCPC_CLASS
	tristate "Tapas Type-C port controller class"
config TCPC_RT1711H
	tristate "Tapas Richtek RT1711H controller"
	depends on TCPC_CLASS
config DUAL_ROLE_USB_INTF
	tristate "Tapas dual-role Type-C interfaces"
	depends on TCPC_RT1711H
config QCOM_PMIC_VOTER
	tristate "Tapas PMIC voter"
config BQ2589X_CHARGER
	tristate "Tapas BQ2589x charger"
config CHARGER_SC8551
	tristate "Tapas SC8551 charge pump"
config FG_SM5602
	tristate "Tapas SM5602 fuel gauge"
config LN8000_CHARGER
	tristate "Tapas LN8000 charge pump"
config ONEWIRE_GPIO
	tristate "Tapas one-wire GPIO"
config BATT_VERIFY_BY_DS28E16
	tristate "Tapas DS28E16 battery authentication"
	depends on ONEWIRE_GPIO
config NOPMI_CHARGER
	tristate "Tapas Xiaomi non-PMI charger"
config CHARGER_PD_POLICY
	tristate "Tapas charging PD policy"
	depends on TCPC_RT1711H
'''


def registration(name: str, out: str, config: str, srcs: list[str],
                 deps: list[str] | None = None, includes: list[str] | None = None) -> str:
    def values(key: str, items: list[str]) -> str:
        if not items:
            return ""
        body = "".join(f'            "{item}",\n' for item in items)
        return f"        {key} = [\n{body}        ],\n"
    return (
        "    registry.register(\n"
        f'        name = "{name}",\n'
        f'        out = "{out}",\n'
        f'        config = "{config}",\n'
        + values("srcs", srcs)
        + values("deps", deps or [])
        + values("includes", includes or [])
        + "    )\n"
    )


def registry_text() -> str:
    tcpc = [f"drivers/usb/typec/tcpc/{name}" for name in TCPC_CLASS_SOURCES]
    modules = [
        registration("drivers/usb/typec/tcpc/tcpc-class-tapas", "tcpc_class.ko",
                     "CONFIG_TCPC_CLASS", tcpc,
                     includes=["drivers/usb/typec/tcpc/inc"]),
        registration("drivers/usb/typec/tcpc/rt1711h-tapas", "tcpc_rt1711h.ko",
                     "CONFIG_TCPC_RT1711H", ["drivers/usb/typec/tcpc/tcpc_rt1711h.c"],
                     ["drivers/usb/typec/tcpc/tcpc-class-tapas"],
                     ["drivers/usb/typec/tcpc/inc"]),
    ]
    for source, output in [
        ("rt_pd_manager", "rt_pd_manager.ko"),
        ("class-dual-role", "class-dual-role.ko"),
        ("xm_adapter_class", "xm_adapter_class.ko"),
        ("xm_pd_adapter", "xm_pd_adapter.ko"),
    ]:
        modules.append(registration(
            f"drivers/usb/typec/tcpc/{source}-tapas", output,
            "CONFIG_DUAL_ROLE_USB_INTF", [f"drivers/usb/typec/tcpc/{source}.c"],
            ["drivers/usb/typec/tcpc/tcpc-class-tapas",
             "drivers/usb/typec/tcpc/rt1711h-tapas"],
            ["drivers/usb/typec/tcpc/inc"],
        ))
    modules += [
        registration("drivers/power/supply/qcom-pmic-voter-tapas", "qcom-pmic-voter.ko",
                     "CONFIG_QCOM_PMIC_VOTER",
                     ["drivers/power/supply/nopmi/qcom-pmic-voter.c"]),
        registration("drivers/power/supply/bq2589x-tapas", "bq2589x_charger.ko",
                     "CONFIG_BQ2589X_CHARGER",
                     ["drivers/power/supply/nopmi/bq2589x_charger.c"],
                     ["drivers/power/supply/qcom-pmic-voter-tapas",
                      "drivers/usb/typec/tcpc/tcpc-class-tapas"]),
        registration("drivers/power/supply/sc8551-tapas", "sc8551_charger.ko",
                     "CONFIG_CHARGER_SC8551",
                     ["drivers/power/supply/nopmi/sc8551_charger.c"],
                     ["drivers/power/supply/qcom-pmic-voter-tapas"]),
        registration("drivers/power/supply/sm5602-tapas", "sm5602_fg.ko",
                     "CONFIG_FG_SM5602", ["drivers/power/supply/nopmi/sm5602_fg.c"]),
        registration("drivers/power/supply/ln8000-tapas", "ln8000_charger.ko",
                     "CONFIG_LN8000_CHARGER",
                     ["drivers/power/supply/nopmi/ln8000_charger.c"],
                     ["drivers/power/supply/qcom-pmic-voter-tapas"]),
        registration("drivers/power/supply/onewire-gpio-tapas", "onewire_gpio.ko",
                     "CONFIG_ONEWIRE_GPIO",
                     ["drivers/power/supply/battery_secret/onewire_gpio.c"]),
        registration("drivers/power/supply/ds28e16-tapas", "batt-ds28e16.ko",
                     "CONFIG_BATT_VERIFY_BY_DS28E16", [
                         "drivers/power/supply/battery_secret/ucl_sha3.c",
                         "drivers/power/supply/battery_secret/sha384_software.c",
                         "drivers/power/supply/battery_secret/ds28e16.c",
                     ], ["drivers/power/supply/onewire-gpio-tapas"]),
        registration("drivers/power/supply/nopmi-chg-tapas", "nopmi-chg.ko",
                     "CONFIG_NOPMI_CHARGER", [
                         "drivers/power/supply/nopmi_chg.c",
                         "drivers/power/supply/nopmi_chg_jeita.c",
                         "drivers/power/supply/nopmi_chg_common.c",
                     ], [
                         "drivers/power/supply/qcom-pmic-voter-tapas",
                         "drivers/power/supply/bq2589x-tapas",
                         "drivers/power/supply/sm5602-tapas",
                         "drivers/usb/typec/tcpc/tcpc-class-tapas",
                     ]),
        registration("drivers/power/supply/pd-policy-tapas", "pd_policy_manager.ko",
                     "CONFIG_CHARGER_PD_POLICY",
                     ["drivers/power/supply/pd_policy_manager.c"], [
                         "drivers/power/supply/nopmi-chg-tapas",
                         "drivers/power/supply/sc8551-tapas",
                         "drivers/usb/typec/tcpc/rt1711h-tapas",
                     ]),
    ]
    return "def register_modules(registry):\n" + "\n".join(modules)


def port_i2c_remove(path: Path, function: str) -> None:
    text = path.read_text()
    signature = f"static int {function}(struct i2c_client *client)"
    start = text.find(signature)
    if start < 0:
        raise RuntimeError(f"{path}: callback {function} not found")
    brace = text.index("{", start)
    depth = 0
    end = None
    for index in range(brace, len(text)):
        depth += text[index] == "{"
        depth -= text[index] == "}"
        if depth == 0:
            end = index + 1
            break
    if end is None:
        raise RuntimeError(f"{path}: unterminated callback {function}")
    block = text[start:end].replace(signature, signature.replace("static int", "static void"), 1)
    block = re.sub(r"\breturn\s+[^;]+;", "return;", block)
    path.write_text(text[:start] + block + text[end:])


def port_i2c_probe(path: Path, function: str) -> None:
    text = path.read_text()
    pattern = re.compile(
        rf"static int {re.escape(function)}\(struct i2c_client \*client,\s*"
        rf"const struct i2c_device_id \*id\)"
    )
    text, count = pattern.subn(
        f"static int {function}(struct i2c_client *client)", text, count=1
    )
    if count != 1:
        raise RuntimeError(f"{path}: probe callback {function} not found")
    path.write_text(text)


def main() -> int:
    if len(sys.argv) != 3:
        print(f"usage: {sys.argv[0]} TOPAZ_TREE SOC_TREE", file=sys.stderr)
        return 2
    donor, soc = map(Path, sys.argv[1:])
    for relative in ("drivers/usb/typec/tcpc", "drivers/power/supply/nopmi",
                     "drivers/power/supply/battery_secret"):
        shutil.copytree(donor / relative, soc / relative, dirs_exist_ok=True)
    for relative in TOP_FILES:
        source = donor / relative
        if not source.is_file():
            raise FileNotFoundError(source)
        output = soc / relative
        output.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, output)

    imported_sources = []
    for directory in (soc / "drivers/usb/typec/tcpc", soc / "drivers/power/supply/nopmi",
                      soc / "drivers/power/supply/battery_secret"):
        imported_sources.extend(directory.glob("*.c"))
    imported_sources.extend(soc / relative for relative in TOP_FILES if relative.endswith(".c"))
    for source in imported_sources:
        text = source.read_text(errors="surrogateescape")
        text = text.replace("class_create(THIS_MODULE, ", "class_create(")
        text = text.replace("struct class *class", "const struct class *class")
        text = text.replace("struct class_attribute *attr", "const struct class_attribute *attr")
        source.write_text(text, errors="surrogateescape")

    nopmi = soc / "drivers/power/supply/nopmi_chg.c"
    text = nopmi.read_text().replace("struct class *c,", "const struct class *c,")
    text = text.replace('#include "touch-charger.h"',
                        '/* Touch charging hooks are enabled with the future target touch stack. */')
    nopmi.write_text(text)

    # IIO core now performs standard OF channel translation itself.
    for source in imported_sources:
        text = source.read_text(errors="surrogateescape")
        text = re.sub(r"^\s*\.of_xlate\s*=\s*\w+,\n", "", text, flags=re.M)
        source.write_text(text, errors="surrogateescape")

    bq = soc / "drivers/power/supply/nopmi/bq2589x_charger.c"
    text = bq.read_text().replace(
        "bq->wall_cfg.of_node = bq->dev->of_node;",
        "bq->wall_cfg.fwnode = of_fwnode_handle(bq->dev->of_node);",
    )
    bq.write_text(text)

    onewire = soc / "drivers/power/supply/battery_secret/onewire_gpio.c"
    text = onewire.read_text()
    if "#include <linux/pinctrl/consumer.h>" not in text:
        text = text.replace("#include <linux/platform_device.h>\n",
                            "#include <linux/platform_device.h>\n#include <linux/pinctrl/consumer.h>\n", 1)
    text = text.replace(
        'of_get_named_gpio_flags(np,\n\t\t\t\t\t"xiaomi,ow_gpio", 0, NULL)',
        'of_get_named_gpio(np, "xiaomi,ow_gpio", 0)',
    )
    onewire.write_text(text)

    dual = soc / "drivers/usb/typec/tcpc/class-dual-role.c"
    text = dual.read_text().replace("strtobool(", "kstrtobool(")
    text = text.replace("int dual_role_uevent(struct device *dev,",
                        "int dual_role_uevent(const struct device *dev,")
    dual.write_text(text)

    rt1711 = soc / "drivers/usb/typec/tcpc/tcpc_rt1711h.c"
    text = rt1711.read_text().replace("strlcpy(", "strscpy(")
    text = text.replace("devm_gpio_request(chip->dev, chip->irq_gpio, name)",
                        "devm_gpio_request_one(chip->dev, chip->irq_gpio, 0, name)")
    rt1711.write_text(text)

    sm5602 = soc / "drivers/power/supply/nopmi/sm5602_fg.c"
    text = sm5602.read_text().replace("#include <asm/unaligned.h>",
                                      "#include <linux/unaligned.h>")
    text = text.replace("sm->chip = id->driver_data;", "sm->chip = SM5602;")
    sm5602.write_text(text)

    timer = soc / "drivers/usb/typec/tcpc/tcpci_timer.c"
    text = timer.read_text().replace(
        "static enum alarmtimer_restart\n\ttcpc_timer_wakeup(struct alarm *alarm, ktime_t now)",
        "static void tcpc_timer_wakeup(struct alarm *alarm, ktime_t now)",
    )
    text = text.replace("\tschedule_delayed_work(&tcpc->wake_up_work, 0);\n\treturn ALARMTIMER_NORESTART;",
                        "\tschedule_delayed_work(&tcpc->wake_up_work, 0);")
    timer.write_text(text)

    for relative, function in [
        ("drivers/power/supply/nopmi/bq2589x_charger.c", "bq2589x_charger_probe"),
        ("drivers/power/supply/nopmi/ln8000_charger.c", "ln8000_probe"),
        ("drivers/power/supply/nopmi/sc8551_charger.c", "sc8551_charger_probe"),
        ("drivers/power/supply/nopmi/sm5602_fg.c", "sm_fg_probe"),
        ("drivers/usb/typec/tcpc/tcpc_rt1711h.c", "rt1711_i2c_probe"),
    ]:
        port_i2c_probe(soc / relative, function)

    for relative, function in [
        ("drivers/usb/typec/tcpc/xm_pd_adapter.c", "xm_pd_adapter_remove"),
        ("drivers/usb/typec/tcpc/rt_pd_manager.c", "rt_pd_manager_remove"),
        ("drivers/power/supply/battery_secret/onewire_gpio.c", "onewire_gpio_remove"),
        ("drivers/power/supply/battery_secret/ds28e16.c", "ds28e16_remove"),
        ("drivers/power/supply/nopmi_chg.c", "nopmi_chg_remove"),
        ("drivers/power/supply/pd_policy_manager.c", "usbpd_pm_remove"),
    ]:
        port_remove(soc / relative, function)
    for relative, function in [
        ("drivers/usb/typec/tcpc/tcpc_rt1711h.c", "rt1711_i2c_remove"),
        ("drivers/power/supply/nopmi/sm5602_fg.c", "sm_fg_remove"),
        ("drivers/power/supply/nopmi/sc8551_charger.c", "sc8551_charger_remove"),
        ("drivers/power/supply/nopmi/ln8000_charger.c", "ln8000_remove"),
    ]:
        port_i2c_remove(soc / relative, function)

    registry_dir = soc / "drivers/soc/qcom/tapas-power"
    registry_dir.mkdir(parents=True, exist_ok=True)
    (registry_dir / "modules.bzl").write_text(registry_text())
    parent = soc / "drivers/soc/qcom/modules.bzl"
    text = parent.read_text()
    load = ('load(":drivers/soc/qcom/tapas-power/modules.bzl", '
            'register_tapas_power = "register_modules")\n')
    if load not in text:
        text = load + text
    call = "    register_tapas_power(registry)\n"
    anchor = "def register_modules(registry):\n"
    if call not in text:
        text = text.replace(anchor, anchor + call, 1)
    parent.write_text(text)

    kconfig = soc / "drivers/soc/qcom/Kconfig"
    text = kconfig.read_text()
    if "config TCPC_CLASS" not in text:
        kconfig.write_text(text + KCONFIG)
    print("k618_tapas_power: imported 15 Type-C, charging and battery modules")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
