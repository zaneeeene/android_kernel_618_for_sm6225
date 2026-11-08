#!/usr/bin/env bash
# Build-only Gate 1: import and compile the initial Khaje platform modules.
# This does not produce a flashable image.
set -euo pipefail
. "$(dirname "$(readlink -f "$0")")/env.sh"

jobs=${1:-8}
shift 2>/dev/null || true
donor=${SM6225_DONOR:-$K618/src/topaz}

[ -d "$donor/.git" ] || {
  echo "No MiCode topaz donor at $donor (set SM6225_DONOR)" >&2
  exit 2
}

git -C "$S" checkout -q -- .
python3 -I "$K618_DIR/k618_khaje.py" "$donor" "$S"
python3 -I "$K618_DIR/k618_fix618.py" "$S"
cp "$K618_DIR/k618_sm6225_overrides.bzl" "$S/configs/"

bash "$K618_DIR/k618_soc_build.sh" \
  configs/canoe_perf.bzl,k618_sm6225_overrides.bzl "$jobs" \
  clk-qcom gdsc-regulator pinctrl-msm phy-qcom-ufs \
  gcc-khaje dispcc-khaje gpucc-khaje debugcc-khaje \
  pinctrl-khaje pinctrl-bengal phy-qcom-ufs-qmp-v4-khaje "$@"
