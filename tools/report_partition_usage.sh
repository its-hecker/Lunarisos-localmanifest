#!/usr/bin/env bash
set -e

root="${1:-$PWD}"
out="$root/out/target/product/coral"
if [[ ! -d "$out" ]]; then
  echo "Missing $out. Run from the existing LunarisOS Coral checkout."
  exit 1
fi

echo "LunarisOS Coral image and installed-file size report"
echo "Product output: $out"
echo
printf '%-15s %16s %16s\n' "Partition" "Image bytes" "Installed bytes"
for part in product system system_ext vendor; do
  img=0
  installed=0
  if [[ -f "$out/$part.img" ]]; then
    img=$(stat -c %s "$out/$part.img")
  fi
  if [[ -d "$out/$part" ]]; then
    installed=$(du -sb "$out/$part" | cut -f1)
  fi
  printf '%-15s %16s %16s\n' "$part" "$img" "$installed"
done

echo
echo "Largest top-level directories in dynamic partitions (bytes, descending):"
for part in product system system_ext vendor; do
  if [[ -d "$out/$part" ]]; then
    echo "--- $part ---"
    du -B1 -d 2 "$out/$part" | sort -nr | sed -n '1,30p'
  fi
done

echo
echo "Largest individual installed files (bytes, descending):"
find "$out/product" "$out/system" "$out/system_ext" "$out/vendor" \
  -type f -printf '%s\t%p\n' 2>/dev/null | sort -k1,1nr | sed -n '1,100p'

echo
echo "Pixel 4 XL super size bytes: 9755951104"
echo "A/B slot size ceiling bytes: 4877975552"
echo "Declared dynamic group ceiling bytes: 4873781248"
echo "Build output directories may include leftover installed files; the check_partition_sizes images determine final sizing."
