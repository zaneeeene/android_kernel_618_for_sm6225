#!/usr/bin/env bash
# Build every stock vendor_dlkm entry represented by the SM8850/public registry.
set -euo pipefail
[ "${K618_LIMITS_VERIFIED:-}" = 1 ] || {
  echo 'Use bash scripts/run-limited.sh vendor-modules.' >&2
  exit 2
}
. "$(dirname -- "${BASH_SOURCE[0]}")/project-env.sh"

# Establish the already-gated kernel, exact platform stack and first-stage set.
bash "$PROJECT_ROOT/scripts/gate4.sh"

soc="$K618/soc"
targets=$(python3 -I "$PROJECT_ROOT/kernel-6.18/k618_soc_stock_select.py" \
  "$soc" "$PROJECT_ROOT/provenance/tapas-vendor-dlkm-modules.load" \
  "$PROJECT_ROOT/provenance/module-name-map-sm6225.json")

set +e
bash "$PROJECT_ROOT/kernel-6.18/k618_soc_build.sh" \
  configs/canoe_perf.bzl,k618_sm6225_overrides.bzl,k618_sm6225_compat.bzl \
  "${JOBS:-4}" $targets
build_rc=$?
set -e

python3 "$PROJECT_ROOT/tools/tapas/module_coverage.py" \
  --stock "$PROJECT_ROOT/provenance/tapas-vendor-dlkm-modules.load" \
  --map "$PROJECT_ROOT/provenance/module-name-map-sm6225.json" \
  --config "$K618/out-gki/.config" \
  --root "gki=$K618/out-gki" --root "soc=$soc" \
  --output "$BUILD_ROOT/vendor-module-coverage.json"

exit "$build_rc"
