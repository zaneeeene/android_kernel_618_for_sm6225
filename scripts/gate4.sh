#!/usr/bin/env bash
# Gate 4: build Gate 3 and audit every stock first-stage module requirement.
set -euo pipefail
[ "${K618_LIMITS_VERIFIED:-}" = 1 ] || {
  echo 'Use bash scripts/run-limited.sh gate4.' >&2
  exit 2
}
. "$(dirname -- "${BASH_SOURCE[0]}")/project-env.sh"

common="$K618/ws/common"
soc="$K618/soc"
topaz="$K618/src/topaz"
for path in "$common/.git" "$soc/.git" "$topaz/.git"; do
  [ -e "$path" ] || { echo "Missing $path; bootstrap Gate 4 sources first." >&2; exit 2; }
done

git -C "$common" reset -q --hard HEAD
git -C "$common" clean -fdxq
git -C "$soc" reset -q --hard HEAD
git -C "$soc" clean -fdxq
SM6225_GATE2=1 SM6225_GATE3=1 bash "$PROJECT_ROOT/kernel-6.18/k618_gki.sh" "${JOBS:-4}"
SM6225_DONOR="$topaz" SM6225_COMPAT=1 \
  bash "$PROJECT_ROOT/kernel-6.18/k618_tapas_base.sh" "${JOBS:-4}"

# The earlier gates deliberately requested only the minimal Khaje set. Build
# every additional first-stage stock module that the 6.11 soc registry can
# supply, resolving registry names from output filenames at runtime.
stock_targets=$(python3 -I "$PROJECT_ROOT/kernel-6.18/k618_soc_stock_select.py" \
  "$soc" "$PROJECT_ROOT/provenance/tapas-vendor-boot-modules.load" \
  "$PROJECT_ROOT/provenance/module-name-map-sm6225.json")
stock_targets="$stock_targets drivers/remoteproc/qcom_q6v5_pas drivers/soc/qcom/qfprom-sys"
if [ -n "$stock_targets" ]; then
  bash "$PROJECT_ROOT/kernel-6.18/k618_soc_build.sh" \
    configs/canoe_perf.bzl,k618_sm6225_overrides.bzl,k618_sm6225_compat.bzl \
    "${JOBS:-4}" $stock_targets
fi

python3 "$PROJECT_ROOT/tools/tapas/module_coverage.py" \
  --stock "$PROJECT_ROOT/provenance/tapas-vendor-boot-modules.load" \
  --map "$PROJECT_ROOT/provenance/module-name-map-sm6225.json" \
  --config "$K618/out-gki/.config" \
  --root "gki=$K618/out-gki" --root "soc=$soc" \
  --output "$BUILD_ROOT/gate4-coverage.json" --require-complete

release=$(cat "$K618/out-gki/include/config/kernel.release")
python3 "$PROJECT_ROOT/tools/tapas/assemble_module_payload.py" \
  --coverage "$BUILD_ROOT/gate4-coverage.json" \
  --rules "$PROJECT_ROOT/provenance/module-name-map-sm6225.json" \
  --root "gki=$K618/out-gki" --root "soc=$soc" \
  --output "$BUILD_ROOT/gate4-payload" --release "$release" \
  --system-map "$K618/out-gki/System.map"

python3 "$PROJECT_ROOT/tools/tapas/audit_dt_bindings.py" \
  --manifest "$PROJECT_ROOT/provenance/tapas-boot-critical-bindings.json" \
  --payload "$BUILD_ROOT/gate4-payload" \
  --config "$K618/out-gki/.config" \
  --output "$BUILD_ROOT/gate4-binding-audit.json"

echo "Gate 4 coverage, dependency closure and DT bindings passed; no image was packaged."
