#!/usr/bin/env bash
# Merge the verified Snapdragon 685 tapas base/overlay pair.
set -euo pipefail

if [ "$#" -ne 3 ]; then
  echo "usage: $0 EXTRACTED_DT_DIR DTC_BUILD_DIR OUTPUT_DTB" >&2
  exit 2
fi

dt_dir=$1
dtc_dir=$2
output=$3

base="$dt_dir/vendor-dtbs/001.dtb"
overlay="$dt_dir/dtbo/045.dtbo"
[ -f "$base" ] && [ -f "$overlay" ] || {
  echo "missing base 001 or tapas overlay 045" >&2
  exit 1
}

export LD_LIBRARY_PATH="$dtc_dir/libfdt${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
"$dtc_dir/fdtoverlay" -i "$base" -o "$output" "$overlay"
"$dtc_dir/dtc" -q -I dtb -O dts -o "${output%.dtb}.dts" "$output"
echo "merged base 001 + overlay 045 -> $output"
