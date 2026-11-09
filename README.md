# Redmi Note 12 4G · experimental Linux 6.18 bring-up

**Research port of Android ACK 6.18 for Xiaomi Redmi Note 12 4G
(`tapas`/`topaz`, Qualcomm SM6225-AD “khaje”, Snapdragon 685).**

> [!WARNING]
> There is no bootable 6.18 release yet. Do not flash anything produced by this
> repository until a milestone is explicitly marked device-tested.

This branch starts from JiaqiLi404's Xiaomi 13 Pro / SM8550 6.18 integration and
replaces its hardware inputs with exact SM6225 sources. The original project's
README is preserved at [docs/UPSTREAM_SM8550_README.md](docs/UPSTREAM_SM8550_README.md).

## Current status

| Area | Status |
|:--|:--|
| Stock 5.15 build/flash pipeline | Built; separate [Stage 0 repository](https://github.com/zaneeeene/tapas-kernel-stage0) |
| Stock firmware and module inventory | Complete for `OS2.0.209.0.VMTMIXM` |
| Stock device-tree extraction | Complete: 6 base DTBs, 49 overlays |
| Exact tapas DT selection | Identified and merged: base `001` + overlay `045` |
| Public SM6225 source inventory | Complete |
| 6.18 SM6225 platform patch | **Gate 1 passed:** ACK Image + clocks/TLMM/UFS compile |
| 6.18 legacy platform stack | **Gate 2 passed:** SMD/RPM, storage, IPC and remoteproc compile |
| Exact Bengal interconnect | **Gate 3 passed:** 98 nodes, 22 QoS tables and exact RPM IDs compile |
| 6.18 first-stage modules | **Gate 4 passed:** 86/86 policy coverage, 102-module closed payload, 33/33 DT bindings |
| Public vendor module expansion | **Passed:** 169 modules compile; 126/238 stock load entries covered |
| Physical-device boot | Not attempted; one local fastboot-boot-only experiment exists and is **NOT FLASHABLE** |

The stock target uses:

- Linux `5.15.194-android13-8` in `boot.img`;
- vendor modules built with `5.15.41` vermagic and GKI symbol versioning;
- base DTB `001`: `qcom,khaje`, SoC ID `0x24a`;
- DTBO `045`: board ID `0x20022`, model `KHAJE IDP nopmi tapas`;
- 86 first-stage modules, then 238 entries in the vendor module load list.

## Gate 1 build result

[GitHub Actions run 42512386428](https://github.com/zaneeeene/android_kernel_618_for_sm6225/actions/runs/42512386428)
successfully built:

- `Image`: Linux `6.18.32`, 44,321,280 bytes, SHA-256
  `c39814c588be21ab34a26d0b4f447106e86c613b5769702a2d25a0d53ef94bb9`;
- Khaje GCC, DISPCC, GPUCC and debug clock modules;
- Khaje and Bengal pinctrl modules;
- the exact Khaje QMP v4 UFS PHY module.

All seven target modules use the same 6.18 modversion ABI and compiled with no
errors. The artifact is intentionally named `GATE1-NOT-FLASHABLE`: SMD/RPM,
Bengal NoC, full storage/USB dependencies, device-tree packaging and Android
modules are not integrated yet. Reproducible hashes are recorded in
[provenance/gate1-build.json](provenance/gate1-build.json).

[Gate 2 run 42519405745](https://github.com/zaneeeene/android_kernel_618_for_sm6225/actions/runs/42519405745)
then built the expanded 22-module target set: SMD/RPM, regulator, MPM/APCS,
SM6115 NoC reference, BAM DMA, UFS host, SDHCI, hwspinlock, NVMEM, QRTR,
GLINK/SMD and PAS remoteproc alongside the Gate 1 modules. Its report is
[provenance/gate2-build.json](provenance/gate2-build.json). It remains
non-flashable pending the exact Bengal NoC and boot/runtime integration.

[Gate 3 run 42532251548](https://github.com/zaneeeene/android_kernel_618_for_sm6225/actions/runs/42532251548)
passed with MiCode's exact 98 Bengal nodes, 22 QoS tables, downstream RPM IDs
and two-clock voting ported to ACK 6.18's provider registration API. It
supersedes the earlier SM6115-backed API prototype. Exact hashes and the
superseded run are recorded in
[provenance/gate3-build.json](provenance/gate3-build.json).

[Gate 4 run 42541820086](https://github.com/zaneeeene/android_kernel_618_for_sm6225/actions/runs/42541820086)
compiled all 95 selected soc targets with clean modpost. The stock 86-entry
first-stage list is covered by 77 modules, three validated built-ins, two modern
replacements and four documented non-applicable/diagnostic omissions, with zero blocking
gaps. The resulting 102-module payload is dependency-closed, and all 33
boot-critical stock DT compatibles have providers. See
[provenance/gate4-build.json](provenance/gate4-build.json).

A gated local artifact was assembled only for a future temporary
`fastboot boot` review. Its filename contains
`FASTBOOT-BOOT-ONLY-NOT-FLASHABLE`; no device command has been run, and it must
not be flashed. Its structure and hashes are recorded in
[provenance/early-boot-experiment.json](provenance/early-boot-experiment.json).

[Vendor expansion run 42545170149](https://github.com/zaneeeene/android_kernel_618_for_sm6225/actions/runs/42545170149)
then compiled 156/156 selected modules (107 direct stock-registry matches plus
their dependencies) with no compile or modpost errors. This covers 111 of the
238 stock vendor load entries. The remaining 127 entries are classified by
audio, charging, thermal, connectivity, multimedia/GPU, touch/biometrics,
security, Xiaomi policy and platform gaps in
[provenance/vendor-module-expansion.json](provenance/vendor-module-expansion.json).

[Thermal/platform run 42554292269](https://github.com/zaneeeene/android_kernel_618_for_sm6225/actions/runs/42554292269)
expanded that result to 169 clean modules and 126/238 covered entries. Five
Qualcomm thermal modules, six target platform interfaces and four ACK-native
modules were added; Xiaomi's private thermal-class shim and legacy TSENS remain
deferred. See
[provenance/daily-module-expansion.json](provenance/daily-module-expansion.json).

## Why this attempt is now plausible

OPlus publishes an exact SM6225 source set, not merely a nearby Qualcomm SoC:

| Input | Kernel | Role |
|:--|:--|:--|
| OPlus `android_kernel_common_oppo_sm6225` | 5.15.180 | Khaje clocks, pinctrl, interconnect, UFS, USB and core platform behavior |
| OPlus `android_kernel_modules_and_devicetree_oppo_sm6225` | 5.15 | Khaje DT plus display, KGSL, camera, video, audio, WLAN and data drivers |
| OnePlus SM8850 kernel/modules | 6.11 | Newer Qualcomm driver APIs used as the bridge to 6.18 |
| MiCode `topaz-t-oss` | 5.15.41 | Xiaomi charger/fuel-gauge, fingerprint, thermal and board-specific interfaces |
| `xiaomi-6225-AD` modules/device trees | 5.15 generation | Target-family tapas/topaz multimedia and DTS source (WIP; checked against stock) |
| `sm6225-dev` modules | 5.15 generation | Supplemental Khaje touch drivers absent from MiCode's partial release |
| Stock tapas firmware | 5.15.194 | Authoritative DT, module list and runtime ABI requirements |
| Upstream SM8550 6.18 project | 6.18.32 | Proven ACK integration, build tooling and 6.11→6.18 compatibility work |

Pinned revisions and partition hashes are in
[provenance/input-sources-sm6225.json](provenance/input-sources-sm6225.json).

## Bring-up gates

1. **Build-only platform gate** — import Khaje clock, pinctrl, interconnect,
   UFS and USB support into ACK 6.18 and compile a coherent kernel/module set.
2. **Early-boot gate** — bootloader handoff, console/pstore, interrupts, timers,
   regulators, storage and USB; no Android UI required.
3. **UI gate** — downstream display, KGSL/Adreno 610 and one tapas touch stack.
4. **Daily hardware gate** — charging/fuel gauge, audio, Wi-Fi/Bluetooth, modem
   data paths, sensors, suspend/resume and thermal control.
5. **Multimedia gate** — camera and video interfaces, then compatibility with
   the stock Android 13 vendor userspace.

Each gate must pass before the next image is offered for flashing. See
[docs/PORTING_SM6225.md](docs/PORTING_SM6225.md) for the technical plan.

## Repository layout during bring-up

| Path | Purpose |
|:--|:--|
| `kernel-6.18/` | Upstream project's 6.18 integration scripts; currently SM8550-oriented |
| `patches/soc-sm8550.patch` | Preserved upstream reference; not a tapas patch |
| `tools/tapas/` | Stock DT extraction and hardware-inventory helpers |
| `profiles/tapas-stock.json` | Verified target identity, DT selection and module counts |
| `provenance/tapas-*` | Stock module and compatible-string inventories |
| `provenance/input-sources-sm6225.json` | Pinned public source inputs and local partition hashes |

## Safety

- The successful Stage 0 image is a 5.15 test, not part of this 6.18 port.
- The verified restore image is `Downloads/StockBootImages/boot.img`, SHA-256
  `816029b9afac6adb640195e35f4bcea5f6f844eabea1c31115892525c2d0ac2b`.
- Early 6.18 images must be tested with a working recovery/fastboot restore path.
- The current 6.18 experiment is temporary-boot-only and has not passed any
  physical-device runtime gate. Do not use it with `fastboot flash`.
- Never flash a generated `vendor_boot`, `dtbo` or `vendor_dlkm` until its gate
  and exact target firmware are documented.

## Attribution

The 6.18 framework and existing SM8550 work come from
[JiaqiLi404/android_kernel_618_for_sm8550](https://github.com/JiaqiLi404/android_kernel_618_for_sm8550).
Qualcomm/OPlus, OnePlus, Xiaomi/MiCode, ACK and other source origins remain
identified in the provenance files and in the original source headers.
