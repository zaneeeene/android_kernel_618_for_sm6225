#!/usr/bin/env bash
# Build a temporary-boot-only experiment after compile, dependency and DT gates.
# This script never talks to a device and never invokes fastboot.
set -euo pipefail

usage() {
  cat >&2 <<'EOF'
Usage: build_fastboot_boot_test.sh \
  --image Image --payload gate4-payload --stock-boot boot.img \
  --init-boot init_boot.img --vendor-boot vendor_boot.img \
  --coverage gate4-coverage.json --bindings binding-audit.json --out DIR
EOF
  exit 2
}

image= payload= stock_boot= init_boot= vendor_boot= coverage= bindings= out=
while [ "$#" -gt 0 ]; do
  case "$1" in
    --image) image=$2; shift 2 ;;
    --payload) payload=$2; shift 2 ;;
    --stock-boot) stock_boot=$2; shift 2 ;;
    --init-boot) init_boot=$2; shift 2 ;;
    --vendor-boot) vendor_boot=$2; shift 2 ;;
    --coverage) coverage=$2; shift 2 ;;
    --bindings) bindings=$2; shift 2 ;;
    --out) out=$2; shift 2 ;;
    *) usage ;;
  esac
done
for value in image payload stock_boot init_boot vendor_boot coverage bindings out; do
  [ -n "${!value}" ] || usage
done
for path in "$image" "$stock_boot" "$init_boot" "$vendor_boot" "$coverage" "$bindings"; do
  [ -e "$path" ] || { echo "Missing input: $path" >&2; exit 2; }
done
[ -f "$payload/NOT_FLASHABLE" ] || { echo 'Payload safety marker missing.' >&2; exit 2; }
image=$(realpath "$image")
payload=$(realpath "$payload")
stock_boot=$(realpath "$stock_boot")
init_boot=$(realpath "$init_boot")
vendor_boot=$(realpath "$vendor_boot")
coverage=$(realpath "$coverage")
bindings=$(realpath "$bindings")
out=$(realpath -m "$out")

expected_boot=816029b9afac6adb640195e35f4bcea5f6f844eabea1c31115892525c2d0ac2b
expected_init=828d3bb72990345d0eae44684fefae5f0f8960596920b0b2c7a3e84c0fbfabcd
expected_vendor=29ff1732bdcdc4e208e3c57c94b85c178b31e0118bdb84c31433682fdebb874f
check_hash() {
  local expected=$1 path=$2 actual
  actual=$(sha256sum "$path" | cut -d' ' -f1)
  [ "$actual" = "$expected" ] || {
    echo "Unexpected stock input hash: $path ($actual)" >&2
    exit 2
  }
}
check_hash "$expected_boot" "$stock_boot"
check_hash "$expected_init" "$init_boot"
check_hash "$expected_vendor" "$vendor_boot"

python3 - "$coverage" "$bindings" "$payload/payload-report.json" <<'PY'
import json, sys
coverage, bindings, payload = (json.load(open(path)) for path in sys.argv[1:])
if coverage.get("missing_count") != 0:
    raise SystemExit("Gate 4 has blocking missing modules")
if bindings.get("status") != "passed":
    raise SystemExit("boot-critical DT binding audit has not passed")
if payload.get("flashable") is not False:
    raise SystemExit("payload does not carry the non-flashable safety state")
PY

for command in unpack_bootimg lz4 cpio mkbootimg avbtool; do
  command -v "$command" >/dev/null || { echo "Missing host tool: $command" >&2; exit 2; }
done

work="$out/work"
rm -rf "$out"
mkdir -p "$work/init" "$work/vendor" "$work/vendor-root" "$work/overlay/lib/modules"
unpack_bootimg --boot_img "$init_boot" --out "$work/init" >/dev/null
unpack_bootimg --boot_img "$vendor_boot" --out "$work/vendor" >/dev/null
lz4 -d -c "$work/init/ramdisk" > "$work/init.cpio"
( cd "$work/vendor-root" && lz4 -d -c "$work/vendor/vendor_ramdisk00" | cpio -id --quiet )

module_root=$(find "$payload/lib/modules" -mindepth 1 -maxdepth 1 -type d -print -quit)
[ -n "$module_root" ] || { echo 'No versioned module payload found.' >&2; exit 2; }
cp -a "$module_root"/. "$work/overlay/lib/modules/"
if [ -f "$work/vendor-root/lib/modules/modules.blocklist" ]; then
  cp "$work/vendor-root/lib/modules/modules.blocklist" "$work/overlay/lib/modules/"
fi
find "$work/overlay" -exec touch -h -d @0 {} +

( cd "$work/overlay" && \
  find . -print0 | sort -z | \
  cpio --null -o -H newc --reproducible --owner=0:0 --quiet > "$work/overlay.cpio" )
cat "$work/init.cpio" "$work/overlay.cpio" > "$work/combined.cpio"
lz4 -l -12 -f "$work/combined.cpio" "$work/combined.lz4" >/dev/null

experiment="$out/tapas-618-EARLY-BOOT-EXPERIMENT-FASTBOOT-BOOT-ONLY-NOT-FLASHABLE.img"
mkbootimg --header_version 4 --kernel "$image" --ramdisk "$work/combined.lz4" -o "$experiment"
partition_size=$(stat -c %s "$stock_boot")
salt=$(sha256sum "$image" "$work/combined.lz4" | sha256sum | cut -d' ' -f1)
avbtool add_hash_footer --image "$experiment" --partition_name boot \
  --partition_size "$partition_size" --algorithm NONE --hash_algorithm sha256 --salt "$salt"
ln -s "$experiment" "$work/boot.img"
avbtool verify_image --image "$work/boot.img" >/dev/null
rm "$work/boot.img"

image_sha=$(sha256sum "$image" | cut -d' ' -f1)
experiment_sha=$(sha256sum "$experiment" | cut -d' ' -f1)
cat > "$out/RESTORE.txt" <<EOF
THIS IMAGE IS AN EARLY-BOOT EXPERIMENT AND IS NOT FLASHABLE.

Permitted future test method after explicit review: fastboot boot only.
Do not run fastboot flash with the experiment image.

Temporary boot changes no boot partition. If it hangs, hold Power to reboot and
boot the installed stock kernel normally.

If an experiment was accidentally flashed, enter bootloader fastboot, query the
active slot, and restore this verified stock image to that same boot slot:
  $stock_boot
  SHA-256: $expected_boot
EOF
python3 - "$out/manifest.json" <<PY
import json
json.dump({
  "status": "experimental-fastboot-boot-only",
  "flashable": False,
  "kernel_sha256": "$image_sha",
  "image_sha256": "$experiment_sha",
  "stock_boot_sha256": "$expected_boot",
  "stock_init_boot_sha256": "$expected_init",
  "stock_vendor_boot_sha256": "$expected_vendor",
  "partition_size": $partition_size,
  "avb_verified": True,
}, open("$out/manifest.json", "w"), indent=2)
open("$out/manifest.json", "a").write("\n")
PY
sha256sum "$experiment" > "$experiment.sha256"
rm -rf "$work"
echo "Built $experiment"
echo "NOT FLASHABLE; fastboot-boot-only review artifact."
