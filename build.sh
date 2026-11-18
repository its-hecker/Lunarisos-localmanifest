#!/usr/bin/env bash
set -eo pipefail

if [[ ! -d .repo || ! -f build/envsetup.sh ]]; then
  echo "Run from the LunarisOS Android source root after repo init and sync." >&2
  exit 1
fi

for p in device/google/coral/lineage_coral.mk \
         device/google/coral/camera/camera.mk \
         vendor/google/coral/coral-vendor.mk \
         kernel/google/msm-4.14/Makefile \
         packages/apps/ElmyraService \
         vendor/hecker/floral/faceid/faceid.mk \
         vendor/hecker/floral/motionsense/motionsense.mk; do
  if [[ ! -e "$p" ]]; then
    echo "Missing $p; check that repo sync completed with the feature manifest." >&2
    exit 1
  fi
done

case "${LUNARIS_BUILD_VARIANT:-userdebug}" in
  user|userdebug|eng) ;;
  *) echo "LUNARIS_BUILD_VARIANT must be user, userdebug or eng." >&2; exit 1 ;;
esac

# Fail before the costly build if ServerHive is still compiling an old Coral checkout.
# The pre-fix vendor_internal_prop macro blocks the system_ext Oslo application.
oslo_policy="device/google/coral/sepolicy/system_ext/public/property.te"
expected_oslo='system_restricted_prop(pixel_oslo_debug_prop)'
if ! grep -Fxq "$expected_oslo" "$oslo_policy"; then
  echo "ERROR: Stale Coral device policy at $oslo_policy" >&2
  echo "Expected: $expected_oslo" >&2
  echo "Found:" >&2
  sed -n '1,8p' "$oslo_policy" >&2
  echo "Re-sync the wip/android16-hardware-features device tree before building." >&2
  exit 1
fi
if [[ "${LUNARIS_BUILD_VARIANT:-userdebug}" != "user" ]]; then
  if ! grep -Fq 'include device/google/coral/debug/lunaris_development_adb.mk' device/google/coral/lineage_coral.mk; then
    echo "ERROR: Stale Coral device tree: missing Lunaris diagnostic ADB integration." >&2
    exit 1
  fi
fi
echo "PASS: Synced Coral SELinux policy and diagnostic ADB integration." >&2

export WITH_GMS="${WITH_GMS:-true}"
export WITH_GMS_COMMS_SUITE="${WITH_GMS_COMMS_SUITE:-false}"
export WITH_PIXEL_LAUNCHER="${WITH_PIXEL_LAUNCHER:-false}"
export TARGET_USE_GPHOTOS="${TARGET_USE_GPHOTOS:-false}"

if command -v git-lfs >/dev/null 2>&1; then
  git -C vendor/google/coral lfs pull
fi

here="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
python3 "$here/tools/prepare_hardware.py"

# Lunaris vendor/lineage envsetup generates a random build hostname through
# cat /dev/urandom | tr ... | head -c 4. The resulting SIGPIPE is expected,
# but causes this script to exit prematurely under pipefail.
set +o pipefail
source build/envsetup.sh
set -o pipefail
lunch "lineage_coral-bp4a-${LUNARIS_BUILD_VARIANT:-userdebug}"
out_product="$(get_build_var PRODUCT_OUT)"

# Avoid packaging retired camera apps left behind by an earlier output.
for partition in system system_ext product vendor; do
  for app in Aperture Camera2; do
    if [[ -d "$out_product/$partition/app/$app" || -d "$out_product/$partition/priv-app/$app" ]]; then
      echo "Cleaning stale $app output before installing GCam."
      m installclean
      break 2
    fi
  done
done

m bacon
python3 "$here/tools/prepare_hardware.py" --post-build "$out_product"
