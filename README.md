# LunarisOS 16.2 for Pixel 4 XL (coral) — Android 16 hardware feature branch

This `feat/android16-hardware-features` manifest selects the experimental Coral
device tree with 3D Face Unlock, Motion Sense and original Google Camera
packaging. The ordinary `main` manifest and `lunaris-16.2` device tree remain
unchanged for builders who want the previous base.

## Source and integration

- LunarisOS: `Lunaris-AOSP/android` branch `16.2` (Android 16 QPR2).
- Device: `its-hecker/lunairs-coral-dt` branch
  `wip/android16-hardware-features`, based on LineageOS 23.2.
- Vendor: `its-hecker/lunaris-coral-vendor` branch `lunaris-16.2`.
- Kernel: `its-hecker/lunaris-coral-kernel` branch `lunaris-16.2`,
  with KernelSU Next's legacy 4.14 submodule.
- Face: the pinned `floral-3D-faceid-plugin` source and its verified legacy
  Face HAL, Citadel and camera libraries; the exact HIDL framework patch sites
  were compared against LunarisOS 16.2.
- Motion Sense: the pinned `floral-motionsense-plugin` source with standalone
  Settings, Oslo bridge, SystemUI overlay and scoped policies. The original
  radar firmware, CHRE and calibration remain from the LineageOS device/vendor.
- GCam: the original signed Google Camera 8.7.250 split set, including startup
  JNI, imported using the checksum-pinned package from HeckerOS/Infinity-X.
  This is the Camera *app*, not merely PixelCameraServices.

## Fresh build on ServerHive

```bash
mkdir -p ~/lunaris-coral
cd ~/lunaris-coral
repo init -u https://github.com/Lunaris-AOSP/android.git -b 16.2 --git-lfs
git clone -b feat/android16-hardware-features https://github.com/its-hecker/Lunarisos-localmanifest.git .repo/local_manifests
repo sync -c --fail-fast --no-clone-bundle --no-tags -j4
bash .repo/local_manifests/build.sh 2>&1 | tee ~/lunaris-coral-hardware.log
```

Before lunch, `build.sh` downloads and verifies the pinned Face/Motion native
payloads, refuses unrecognized framework HIDL methods, applies the guarded
face startup/challenge/enrollment fixes, generates biometric and SystemUI
overlays, and retrieves/verifies all ten original GCam APKs. It then uses
`lineage_coral-bp4a-userdebug` and `m bacon`. Build and package checks fail
rather than silently shipping missing Face/Motion/Camera components.

Set `LUNARIS_BUILD_VARIANT=user` for a release-style build. GMS defaults to
`WITH_GMS=true`. To verify a previously fetched cache without networking, run
`python3 .repo/local_manifests/tools/prepare_hardware.py --offline`.

## Validation status

**Source integration committed; full ROM build and device acceptance are not
yet confirmed.** Matching Android 16 HIDL methods and the presence of firmware,
sensor policy and SystemUI allowlist are source-level checks, not evidence that
biometric enrollment, secure authentication, radar gestures or GCam operate
on the handset. Do not label the ROM official on this evidence alone.

After a successful build, flash only with your usual backup/recovery procedure.
Test Face enrollment, screen unlock and removal; reach/silence/skip gestures,
country settings and sensor permission; and still/photo/portrait/video/flash
in Google Camera. Collect `adb logcat -b all` if one feature fails.

The 4.14 KernelSU Next implementation is unchanged by this feature branch.
