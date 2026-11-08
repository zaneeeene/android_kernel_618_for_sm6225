# SM6225 / khaje to ACK 6.18 port plan

## Scope and definition of “full”

The target is Redmi Note 12 4G `tapas` (non-NFC) first, with `topaz` kept as a
later board overlay. A full port means that the stock Android 13 vendor userspace
can boot and retain normal display/GPU, touch, charging, audio, connectivity,
camera, video, thermal and suspend behavior. Merely compiling 6.18 or reaching an
early console is not a full port.

This remains a research project. Public source availability makes an attempt
possible; it does not guarantee that every stock function can be reproduced.

## Verified target

Reference firmware: `OS2.0.209.0.VMTMIXM`, fingerprint:

```text
Redmi/tapas_global/tapas:13/TKQ1.221114.001/OS2.0.209.0.VMTMIXM:user/release-keys
```

Stock facts:

| Item | Value |
|:--|:--|
| Boot kernel | `5.15.194-android13-8-00019-gf4321180a397-ab15212794` |
| Vendor-module vermagic | `5.15.41 SMP preempt mod_unload modversions aarch64` |
| Boot header | v4, 4 KiB pages, no boot ramdisk |
| Vendor boot | v4, platform ramdisk + concatenated DTBs |
| Base DTB | index 1, `qcom,khaje`, `qcom,msm-id = <0x24a 0x10000>` |
| Board overlay | index 45, board ID `0x20022`, PMIC ID `0x2d` |
| Merged hardware tree | 15,037 decompiled lines, 297 unique compatibles |
| First-stage module list | 86 modules |
| Vendor module load list | 238 lines / 237 unique modules |

The paired `0x206` base and overlay 46 represent the older SM6225 variant. The
Snapdragon 685 (`SM6225-AD`) target is `0x24a`, therefore base 1 + overlay 45.

An initial source overlap audit is recorded in
`provenance/sm6225-sm8850-module-overlap.json`. Across audio, camera, display,
KGSL, video and WLAN there are 6,678 common file paths; 3,982 are byte-identical.
The 6.11 tree still carries Khaje/Bengal selectors for KGSL, camera and audio,
which makes it useful as an API-forward implementation rather than only a
different-SoC example.

## Source bridge

### Layer A: ACK 6.18

Use the same pinned ACK 6.18.32 base and toolchain as the upstream SM8550
project initially. This keeps Android binder, GKI, build and packaging behavior
known while the hardware layer changes.

### Layer B: newer Qualcomm API reference

OnePlus SM8850 is Linux 6.11. It does not contain Khaje support, but it contains
newer downstream Qualcomm frameworks and multimedia drivers. The upstream
project already adapts many of those interfaces from 6.11 to 6.18.

Reuse compatibility work, not SM8550 register tables or device definitions.

### Layer C: exact SM6225 platform donor

OPlus's Android 16 SM6225 branches remain Linux 5.15.180 but include:

- `gcc/dispcc/gpucc-khaje`, Bengal interconnect and Khaje/Bengal pinctrl;
- Khaje UFS PHY, UFS host, USB and power infrastructure;
- full Qualcomm Khaje base/reference DT source;
- downstream display (`msm_drm`), KGSL, camera, video, audio, WLAN and data;
- OPlus board drivers that are useful only as API examples.

For each subsystem, port the exact Khaje tables/logic into the newer 6.11
implementation when possible, then apply the existing 6.18 API adaptations.
Blindly compiling a complete 5.15 driver directory against 6.18 is the fallback,
not the preferred method.

### Layer D: Xiaomi board support

MiCode `topaz-t-oss` supplies source for core board pieces including:

- `nopmi-chg`, BQ2589x, LN8000, SC8551 and SM5602 fuel gauge;
- fingerprint glue;
- panel event notifier and Xiaomi thermal interfaces;
- Khaje/Bengal core drivers and config fragments.

The stock binary tree remains authoritative where public source differs.
The `xiaomi-6225-AD` organization supplies target-family WIP module and DT
repositories, including source files named for tapas/topaz. Its DTS is useful
but not authoritative: for example, its `tapas` overlay currently declares
board ID `0x30022`, while the verified stock tapas DTBO uses `0x20022`
(`0x30022` belongs to topaz). Every imported property is therefore checked
against the stock image.

The newer community `sm6225-dev/kernel_xiaomi_sm6225-modules` branch `13`
supplies the missing Khaje touch-driver tree (FocalTech, Goodix, Synaptics,
Novatek and Xiaomi's touch interface). It is a supplemental donor, not
automatically trusted: source paths/configuration and resulting interfaces must
be checked against the stock modules before inclusion. Closed 5.15 `.ko` files
still cannot be loaded safely into 6.18.

Its overlap with the SM8850 API donor is recorded in
`provenance/xiaomi-sm6225-sm8850-module-overlap.json`. Touch is entirely absent
from SM8850, while the other major driver families retain hundreds of common
paths.

The older, tapas-specific WIP module overlap is recorded separately in
`provenance/tapas-sm6225-sm8850-module-overlap.json`.

## Work breakdown

### Gate 1 — build-only platform

1. Produce a new `soc-sm6225.patch`; keep `soc-sm8550.patch` unchanged for
   comparison.
2. Enable/import Khaje GCC, GPUCC, DISPCC, TLMM, Bengal NoC, UFS PHY and USB.
3. Import DT bindings and compile the public Khaje reference DT.
4. Compile first-stage platform modules with modversions enabled.
5. Add symbol/structure checks against the stock 5.15 module inventory.

No image from this gate is flashable.

The first implementation slice is `k618_khaje.py` plus
`k618_tapas_base.sh`: clocks, Khaje/Bengal TLMM and the exact UFS PHY are
registered in the 6.11 soc-repo and passed through the existing 6.18 API fixer.
It deliberately stops before claiming SMD/RPM, NoC or remoteproc support.

### Gate 2 — early boot

1. Reconstruct base 1 + overlay 45 from the reference firmware at build time.
2. Replace DT nodes only when the 6.18 driver binding requires it; keep hardware
   addresses, interrupts, clocks, regulators and reserved memory unchanged.
3. Bring up PSCI, GIC, timers, RPM/RPMh or SMD paths, regulators, UFS and USB.
4. Capture pstore/ramoops and serial/earlycon logs.
5. Boot to first-stage init with display intentionally optional.

### Gate 3 — Android UI

1. Port downstream display using SM8850's newer display driver as the API
   skeleton and SM6225's DPU/DSI/panel tables as the hardware source.
2. Port KGSL for Adreno 610. Do not substitute upstream MSM DRM GPU support
   unless Android userspace compatibility is proven.
3. Port one detected tapas touch stack; keep the alternate panel/touch variant
   disabled until tested.
4. Validate SurfaceFlinger, HWC fences, refresh-rate switching and suspend.

### Gate 4 — daily hardware

Port and test charger/fuel gauge, audio, Wi-Fi/Bluetooth, modem data paths,
thermal controls, sensors, fingerprint, vibrator/LED and deep idle. Replace the
stock module lists with an internally consistent 6.18 payload; do not mix 5.15
modules into it.

### Gate 5 — multimedia

Port camera and video last because they have the largest private userspace
interfaces. Compile success is insufficient: camera provider enumeration,
preview, capture, flash and every sensor path need physical tests.

## Known blockers and risks

- Some Xiaomi touch/audio/charger glue may have no matching published revision.
- Android vendor HALs can depend on private ioctls and sysfs behavior not
  represented by KMI symbols.
- Qualcomm 5.15→6.11 is a large API jump even before the 6.11→6.18 adaptation.
- Stock binary modules use 5.15 layouts and are not a fallback on 6.18.
- A valid DT can still damage hardware if regulator, charger or panel sequencing
  is wrong. Those paths stay disabled until reviewed.
- Camera may remain the final non-working subsystem even after a UI boot.

## Validation policy

Every milestone records:

1. pinned source revisions and generated-tree hashes;
2. compile and modpost reports;
3. DT binding/merge audit;
4. the exact partitions an installer changes;
5. restore instructions;
6. physical-device result and logs.

No “full port” claim is made until all stock-critical hardware is exercised on
the target phone.
