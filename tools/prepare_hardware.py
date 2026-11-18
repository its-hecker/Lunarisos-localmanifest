#!/usr/bin/env python3
"""Prepare Android 16 Coral Face Unlock, Motion Sense and stock GCam before lunch.

The Face framework patcher checks exact upstream HIDL methods and aborts without
mutating files if LunarisOS updates to an unreviewed implementation.
"""
import argparse
from pathlib import Path
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from google_camera import prepare as prepare_camera, verify_installed as verify_camera

FACE = Path("vendor/hecker/floral/faceid")
MOTION = Path("vendor/hecker/floral/motionsense")

def prepare_lunaris_property_partitions(root):
    """Keep Lunaris runtime properties outside generic_system.mk's restricted system."""
    path = root / "vendor/lineage/config/lunaris.mk"
    original = path.read_text()
    updated = original

    # Limit the edit to known upstream blocks. Refuse unexpected changes instead
    # of silently rewriting unrelated system properties.
    blocks = (
        ("# Enable blur", "TARGET_LOW_END_BLUR", 2),
        ("# Quick Switch (Launcher3)", "ifeq ($(SURFACE_FLINGER_BOOST),true)", 3),
    )
    old_key = "PRODUCT_SYSTEM_PROPERTIES +="
    new_key = "PRODUCT_SYSTEM_EXT_PROPERTIES +="

    for start_marker, end_marker, expected in blocks:
        start = updated.find(start_marker)
        end = updated.find(end_marker, start + len(start_marker))
        if start < 0 or end < 0:
            raise ValueError("Lunaris property block changed: " + start_marker)
        block = updated[start:end]
        if block.count(old_key) + block.count(new_key) != expected:
            raise ValueError("Unexpected Lunaris property assignments: " + start_marker)
        updated = updated[:start] + block.replace(old_key, new_key) + updated[end:]

    if updated != original:
        path.write_text(updated)
    print("PASS: Lunaris blur/launcher props target system_ext.", flush=True)



def run(root, plugin, script, *args):
    cmd = [sys.executable, str(root / plugin / "tools" / script), *map(str, args)]
    print("+", " ".join(cmd), flush=True)
    subprocess.run(cmd, cwd=root, check=True)


def prepare(root, offline=False):
    prepare_lunaris_property_partitions(root)
    for path in [
        "device/google/coral/lineage_coral.mk",
        "device/google/coral/camera/camera.mk",
        "vendor/google/coral/Android.bp",
        "frameworks/base/services/core/java/com/android/server/biometrics/"
        "sensors/face/hidl/HidlToAidlSessionAdapter.java",
        "frameworks/base/packages/SystemUI/res/values/config.xml",
    ]:
        if not (root / path).is_file():
            raise FileNotFoundError("Missing required source: " + path)

    fetch_args = ["--verify-only"] if offline else []
    run(root, FACE, "fetch_prebuilts.py", *fetch_args)
    run(root, MOTION, "fetch_prebuilts.py", *fetch_args)
    run(root, FACE, "apply_framework_fixes.py", "--rom-root", root, "--check")
    run(root, FACE, "apply_framework_fixes.py", "--rom-root", root, "--apply")
    run(root, FACE, "prepare.py", "--rom-root", root, "--vendor-tree",
        "vendor/google/coral", "--biometrics-xml",
        "device/google/coral/overlay/frameworks/base/core/res/res/values/config.xml")
    run(root, MOTION, "prepare.py", "--rom-root", root,
        "--policy-dir", "device/google/coral/sepolicy")
    prepare_camera(root, offline=offline)
    run(root, FACE, "verify_ready.py")
    run(root, MOTION, "verify_ready.py")
    print("PASS: Android 16 Face/Motion/GCam preflight. This does not replace a phone test.",
          flush=True)


def verify_output(root, product_out):
    output = product_out.resolve()
    verify_camera(root, output)
    face = output / "vendor/bin/hw/android.hardware.biometrics.face@1.0-service.google"
    if not face.is_file():
        raise FileNotFoundError("Missing hardware Face HAL: " + str(face))
    system_ext = output / "system_ext"
    for filename in ("FloralOsloFeedback.apk", "FloralMotionSenseSettings.apk"):
        if not any(system_ext.rglob(filename)):
            raise FileNotFoundError("Missing Motion Sense package: " + filename)
    print("PASS: Face HAL, Oslo APKs and pinned Google Camera APK set are packaged.",
          flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom-root", type=Path, default=Path.cwd())
    parser.add_argument("--offline", action="store_true",
                        help="Use only previously fetched plugin and Camera payloads")
    parser.add_argument("--post-build", type=Path, metavar="PRODUCT_OUT")
    args = parser.parse_args()
    root = args.rom_root.resolve()
    try:
        if args.post_build:
            verify_output(root, args.post_build)
        else:
            prepare(root, offline=args.offline)
    except (OSError, ValueError, subprocess.CalledProcessError) as exc:
        parser.exit(1, "Lunaris hardware integration: " + str(exc) + "\n")


if __name__ == "__main__":
    main()
