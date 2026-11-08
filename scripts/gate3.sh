#!/usr/bin/env bash
# Compile-only SM6225 Gate 3: Gate 2 plus the exact-binding Bengal NoC.
set -euo pipefail
[ "${K618_LIMITS_VERIFIED:-}" = 1 ] || {
  echo 'Use bash scripts/run-limited.sh gate3.' >&2
  exit 2
}
. "$(dirname -- "${BASH_SOURCE[0]}")/project-env.sh"

common="$K618/ws/common"
soc="$K618/soc"
topaz="$K618/src/topaz"
for path in "$common/.git" "$soc/.git" "$topaz/.git"; do
  [ -e "$path" ] || { echo "Missing $path; bootstrap Gate 3 sources first." >&2; exit 2; }
done

git -C "$common" reset -q --hard HEAD
git -C "$common" clean -fdxq
SM6225_GATE2=1 SM6225_GATE3=1 bash "$PROJECT_ROOT/kernel-6.18/k618_gki.sh" "${JOBS:-4}"
SM6225_DONOR="$topaz" bash "$PROJECT_ROOT/kernel-6.18/k618_tapas_base.sh" "${JOBS:-4}"

python3 - "$common" "$soc" "$BUILD_ROOT/gate3-report.json" <<'PY'
import hashlib
import json
from pathlib import Path
import sys

common, soc, output = map(Path, sys.argv[1:])
expected = {
    'clk-smd-rpm.ko', 'smd-rpm.ko', 'qcom_smd-regulator.ko',
    'irq-qcom-mpm.ko', 'qcom-apcs-ipc-mailbox.ko', 'qnoc-bengal.ko',
    'bam_dma.ko', 'ufs-qcom.ko', 'sdhci-msm.ko', 'qcom_hwspinlock.ko',
    'nvmem_qfprom.ko', 'qrtr-smd.ko', 'qcom_glink_smem.ko', 'qcom_smd.ko',
    'qcom_q6v5_pas.ko', 'gcc-khaje.ko', 'dispcc-khaje.ko',
    'gpucc-khaje.ko', 'debugcc-khaje.ko', 'pinctrl-khaje.ko',
    'pinctrl-bengal.ko', 'phy-qcom-ufs-qmp-v4-khaje.ko',
}
found = {}
for root in (common.parent.parent / 'out-gki', soc):
    for path in root.rglob('*.ko'):
        if path.name in expected and path.name not in found:
            found[path.name] = {
                'name': path.name,
                'size': path.stat().st_size,
                'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                'source': 'gki' if root.name == 'out-gki' else 'soc',
            }
missing = sorted(expected - found.keys())
report = {'gate': 3, 'status': 'passed' if not missing else 'failed',
          'flashable': False, 'modules': [found[n] for n in sorted(found)],
          'missing': missing}
output.write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps(report, indent=2))
if missing:
    raise SystemExit(1)
PY

echo "Gate 3 compile passed; output remains non-flashable."
