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
SM6225_GATE2=1 SM6225_GATE3=1 bash "$PROJECT_ROOT/kernel-6.18/k618_gki.sh" "${JOBS:-4}"
SM6225_DONOR="$topaz" bash "$PROJECT_ROOT/kernel-6.18/k618_tapas_base.sh" "${JOBS:-4}"

python3 "$PROJECT_ROOT/tools/tapas/module_coverage.py" \
  --stock "$PROJECT_ROOT/provenance/tapas-vendor-boot-modules.load" \
  --map "$PROJECT_ROOT/provenance/module-name-map-sm6225.json" \
  --root "gki=$K618/out-gki" --root "soc=$soc" \
  --output "$BUILD_ROOT/gate4-coverage.json" --require-complete

echo "Gate 4 first-stage module coverage passed; no image was packaged."
