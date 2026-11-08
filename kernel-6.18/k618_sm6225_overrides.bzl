k618_sm6225_overrides_config = {
    # First build-only gate. These options do not yet make a bootable platform.
    "CONFIG_ARCH_BENGAL": "y",
    "CONFIG_ARCH_KHAJE": "y",
    "CONFIG_SM_GCC_KHAJE": "m",
    "CONFIG_SM_DISPCC_KHAJE": "m",
    "CONFIG_SM_GPUCC_KHAJE": "m",
    "CONFIG_SM_DEBUGCC_KHAJE": "m",
    "CONFIG_PINCTRL_KHAJE": "m",
    "CONFIG_PINCTRL_BENGAL": "m",
    "CONFIG_PHY_QCOM_UFS_V4_KHAJE": "m",

    # Qualcomm's 5.15 WALT cannot be built against 6.18 scheduler internals.
    "CONFIG_SCHED_WALT": "n",
    "CONFIG_ARM_QCOM_CPUFREQ_HW": "m",
}
