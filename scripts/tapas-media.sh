#!/usr/bin/env bash
# First exact OPlus SM6225 UI-source compile slice: display + KGSL only.
set -euo pipefail
[ "${K618_LIMITS_VERIFIED:-}" = 1 ] || {
  echo 'Use bash scripts/run-limited.sh tapas-media.' >&2
  exit 2
}
. "$(dirname -- "${BASH_SOURCE[0]}")/project-env.sh"

common="$K618/ws/common"
soc="$K618/soc"
oplus="$K618/src/oplus-modules"
oplus_kernel="$K618/src/oplus-kernel"
for path in "$common/.git" "$soc/.git" "$oplus/.git" "$oplus_kernel/.git"; do
  [ -e "$path" ] || { echo "Missing $path; run the pinned source bootstrap first." >&2; exit 2; }
done

# Re-establish the verified GKI and first-stage symbol/config environment.
SM6225_DAILY=1 bash "$PROJECT_ROOT/scripts/gate4.sh"

# KGSL includes this exact OPlus common declaration, absent from the newer
# SM8850 module repository.
mkdir -p "$soc/include/soc/qcom"
cp "$oplus_kernel/include/soc/qcom/boot_stats.h" "$soc/include/soc/qcom/boot_stats.h"

# Apply OPlus techpack fixes (generates k618_oplus_stub.h, mi_disp_k618.c/h, and applies
# OPlus-specific display/KGSL fixes). This must run before k618_tp.sh with TAPAS_OPLUS=1.
python3 -I "$PROJECT_ROOT/kernel-6.18/k618_tp_fix.py" "$oplus/vendor/qcom/opensource"

TP_SOURCE="$oplus/vendor/qcom/opensource" \
TP_ARCH=KHAJE \
TAPAS_OPLUS=1 \
CLEAN=1 \
bash "$PROJECT_ROOT/kernel-6.18/k618_tp.sh" "${JOBS:-4}" display graphics

python3 - "$BUILD_ROOT/k618/tpmods" "$BUILD_ROOT/tapas-media-report.json" <<'PY'
import hashlib
import json
from pathlib import Path
import sys

root, report_path = Path(sys.argv[1]), Path(sys.argv[2])
required = {"msm_drm.ko", "msm_kgsl.ko"}
found = {}
for path in root.glob("*.ko"):
    if path.name in required:
        found[path.name] = {
            "size": path.stat().st_size,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        }
missing = sorted(required - found.keys())
report = {
    "gate": "media-source-compile-1",
    "status": "passed" if not missing else "failed",
    "flashable": False,
    "modules": found,
    "missing": missing,
}
report_path.write_text(json.dumps(report, indent=2) + "\n")
print(json.dumps(report, indent=2))
if missing:
    raise SystemExit(1)
PY
