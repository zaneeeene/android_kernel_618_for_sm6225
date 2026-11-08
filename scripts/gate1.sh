#!/usr/bin/env bash
# Compile-only SM6225 Gate 1. It intentionally does not package a boot image.
set -euo pipefail
[ "${K618_LIMITS_VERIFIED:-}" = 1 ] || {
  echo 'Use bash scripts/run-limited.sh gate1.' >&2
  exit 2
}
. "$(dirname -- "${BASH_SOURCE[0]}")/project-env.sh"

common="$K618/ws/common"
soc="$K618/soc"
topaz="$K618/src/topaz"
for path in "$common/.git" "$soc/.git" "$topaz/.git"; do
  [ -e "$path" ] || {
    echo "Missing $path; run the Gate 1 source bootstrap first." >&2
    exit 2
  }
done

bash "$PROJECT_ROOT/kernel-6.18/k618_gki.sh" "${JOBS:-4}"
SM6225_DONOR="$topaz" bash "$PROJECT_ROOT/kernel-6.18/k618_tapas_base.sh" "${JOBS:-4}"

python3 - "$soc" "$BUILD_ROOT/gate1-report.json" <<'PY'
import hashlib
import json
from pathlib import Path
import sys

soc, output = map(Path, sys.argv[1:])
wanted = {
    'gcc-khaje.ko', 'dispcc-khaje.ko', 'gpucc-khaje.ko', 'debugcc-khaje.ko',
    'pinctrl-khaje.ko', 'pinctrl-bengal.ko', 'phy-qcom-ufs-qmp-v4-khaje.ko',
}
modules = []
for path in sorted(soc.rglob('*.ko')):
    if path.name not in wanted:
        continue
    modules.append({
        'name': path.name,
        'path': str(path.relative_to(soc)),
        'size': path.stat().st_size,
        'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
    })
missing = sorted(wanted - {entry['name'] for entry in modules})
report = {'gate': 1, 'status': 'passed' if not missing else 'failed', 'modules': modules, 'missing': missing}
output.write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps(report, indent=2))
if missing:
    raise SystemExit(1)
PY

echo "Gate 1 compile passed; this output is not flashable."
