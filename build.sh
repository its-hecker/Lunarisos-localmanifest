#!/usr/bin/env bash
set -eo pipefail

if [[ ! -d .repo || ! -f build/envsetup.sh ]]; then
  echo "Run from the LunarisOS Android source root after repo init and sync." >&2
  exit 1
fi

for p in device/google/coral/lineage_coral.mk \
         vendor/google/coral/coral-vendor.mk \
         kernel/google/msm-4.14/Makefile \
         packages/apps/ElmyraService; do
  if [[ ! -e "$p" ]]; then
    echo "Missing $p; check that repo sync finished successfully." >&2
    exit 1
  fi
done

case "${LUNARIS_BUILD_VARIANT:-userdebug}" in
  user|userdebug|eng) ;;
  *) echo "LUNARIS_BUILD_VARIANT must be user, userdebug or eng." >&2; exit 1 ;;
esac

export WITH_GMS="${WITH_GMS:-true}"
export WITH_GMS_COMMS_SUITE="${WITH_GMS_COMMS_SUITE:-false}"
export WITH_PIXEL_LAUNCHER="${WITH_PIXEL_LAUNCHER:-false}"
export TARGET_USE_GPHOTOS="${TARGET_USE_GPHOTOS:-false}"

if command -v git-lfs >/dev/null 2>&1; then
  git -C vendor/google/coral lfs pull
fi

source build/envsetup.sh
lunch "lineage_coral-bp4a-${LUNARIS_BUILD_VARIANT:-userdebug}"
m bacon
