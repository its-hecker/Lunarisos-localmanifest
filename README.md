# LunarisOS 16.2 for Google Pixel 4 XL (coral)

Android 16 QPR2 port, maintained by Hecker.

## Base

- ROM: `Lunaris-AOSP/android` branch `16.2`.
- Device tree: `its-hecker/lunairs-coral-dt` branch `lunaris-16.2`, imported from `LineageOS/android_device_google_coral` `lineage-23.2`.
- Vendor: `its-hecker/lunaris-coral-vendor` branch `lunaris-16.2`, imported from `TheMuppets/proprietary_vendor_google_coral` `lineage-23.2`. LFS files are mirrored into GitHub LFS.
- Kernel: `its-hecker/lunaris-coral-kernel` branch `lunaris-16.2`, imported from `LineageOS/android_kernel_google_msm-4.14` `lineage-23.2`.
- KernelSU Next: integrated into the 4.14 kernel using the pinned legacy submodule; XML enables submodule syncing.
- The `lineage_coral` lunch product and the `bp4a` release come from the matching Android 16 sources.

## Build on ServerHive

Run commands from a separate fresh checkout; do not mix this with Android 17 projects.

```bash
mkdir -p ~/lunaris-coral
cd ~/lunaris-coral
repo init -u https://github.com/Lunaris-AOSP/android.git -b 16.2 --git-lfs
git clone -b main https://github.com/its-hecker/Lunarisos-localmanifest.git .repo/local_manifests
repo sync -c --fail-fast --no-clone-bundle --no-tags -j4
bash .repo/local_manifests/build.sh 2>&1 | tee ~/lunaris-coral-build.log
```

The script selects `lineage_coral-bp4a-userdebug` and `m bacon`. Set `LUNARIS_BUILD_VARIANT=user` for a release variant. The default is a GMS-enabled build (`WITH_GMS=true`).

## Hardware feature status and precautions

- **Base camera HAL, PixelCameraServices, FaceAuth firmware and Oslo sensor firmware:** inherited from the 23.2 device and proprietary vendor sources; physical operation must still be tested.
- **KernelSU Next:** source-integration present; only a complete build and a physical device test can confirm that the kernel boots and grants root correctly.
- **3D Face Unlock:** Android 17 plugin checked out at `vendor/hecker/floral/faceid` as a reference, but its framework patches are explicitly Android 17-specific. Not yet integrated/verified for Android 16.
- **Motion Sense:** Android 17 plugin checked out at `vendor/hecker/floral/motionsense` as a reference. Android 16 SystemUI interface and SEPolicy compatibility still need validation. Not yet enabled in the stable device tree.
- **GCam:** Google's camera hardware services are in the vendor tree, but they are not the Google Camera app. Enabling GMS alone does **not** guarantee that the GCam APK is installed. GCam app packaging and on-device camera tests remain pending.

Hardware integration is staged on the separate device tree branch `wip/android16-hardware-features`; the stable `lunaris-16.2` branch is kept buildable without requiring the Android 17 plugins. Do not release or claim all features working until the Android 16 integration builds and passes phone testing.

## Notes

The device source repository is intentionally spelled `lunairs-coral-dt` to match the repository name provided by Hecker. When updating, use `repo sync` and ensure KernelSU Next's submodule is present; the local manifest specifies `sync-s=\"true\"`. Do not import Android 17 framework/system vendor overlays directly.
