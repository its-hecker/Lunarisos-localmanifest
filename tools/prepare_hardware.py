#!/usr/bin/env python3
"""Prepare Android 16 Coral Face Unlock, Motion Sense and stock GCam before lunch.

The Face framework patcher checks exact upstream HIDL methods and aborts without
mutating files if LunarisOS updates to an unreviewed implementation.
"""
import argparse
from pathlib import Path
import subprocess
import xml.etree.ElementTree as ET
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



def prepare_coral_about_phone(root):
    """Bake Pixel 4 XL specs into Lunaris Settings-core before Soong compiles it.

    Lunaris Settings is an android_library (Settings-core) statically linked
    into Settings.apk. An overlay directory alone did not replace its upstream
    joke defaults on the device, so update only those four guarded strings in
    this checkout. The device overlay remains the single source of values.
    """
    overlay = root / (
        "device/google/coral/overlay/packages/apps/Settings/"
        "res/values/lunaris_coral_specs.xml"
    )
    settings = root / "packages/apps/Settings/res/values/lunaris_strings.xml"
    names = {
        "lunaris_device_message": "ICorn 10 Pro Max",
        "lunaris_processor_code_message": "Chicken Nuggets® 52",
        "lunaris_battery_type_message": "15000 mAh",
        "lunaris_screen_message": "Cathode Ray Tube 24hz",
    }
    values = {
        item.get("name"): item.text
        for item in ET.parse(overlay).getroot().findall("string")
    }
    if set(values) != set(names) or not all(values.values()):
        raise ValueError("Coral Settings specification overlay is incomplete or changed.")

    original = settings.read_text()
    updated = original
    for name, placeholder in names.items():
        before = f'<string name="{name}">{placeholder}</string>'
        after = f'<string name="{name}">{values[name]}</string>'
        if updated.count(before) == 1 and updated.count(after) == 0:
            updated = updated.replace(before, after, 1)
        elif updated.count(after) == 1 and updated.count(before) == 0:
            continue
        else:
            raise ValueError(
                "Unexpected Lunaris Settings string for " + name
                + "; refusing to modify an unreviewed upstream resource."
            )
    if updated != original:
        settings.write_text(updated)
        print("PATCH: Coral About Phone specs baked into Lunaris Settings-core.", flush=True)
    else:
        print("PASS: Coral About Phone specs already baked into Settings-core.", flush=True)


def prepare_android16_source_compat(root):
    """Guarded checkout-only repairs for the pinned A16 QPR2 source combination.

    Keep these patches in Lunaris, rather than changing the shared Face ID,
    Motion Sense and KernelSU Next plugin repositories. All are repeat-safe.
    """
    kernel_types = root / "kernel/google/msm-4.14/include/uapi/linux/types.h"
    if "typedef unsigned __poll_t;" not in kernel_types.read_text():
        raise ValueError("KernelSU poll compatibility requires floral's existing __poll_t typedef.")
    patches = (
        (
            root / "system/libfmq/include/fmq/MessageQueueBase.h",
            '''        hardware::details::logDebug(
                std::format("Read failed after an overflow. Resetting read pointer with preserving "
                            "{} messages.",
                            wantToSave / getQuantumSize()));''',
            '''        hardware::details::logDebug(
                std::string("Read failed after an overflow. Resetting read pointer with preserving ") +
                std::to_string(wantToSave / getQuantumSize()) + " messages.");''',
            "LineageOS FMQ C++17-compatible overflow logging",
        ),
        (
            root / "vendor/hecker/floral/motionsense/settings/src/org/hecker/floral/motionsense/motionsense/MotionSense.java",
            "        preference.applyIlloColors();",
            "        // Motion Sense glow tint is applied by the OnBindListener below.",
            "Lunaris SettingsLib IllustrationPreference API compatibility",
        ),
        (
            root / "kernel/google/msm-4.14/drivers/kernelsu/infra/event_queue.h",
            """#if LINUX_VERSION_CODE < KERNEL_VERSION(4, 16, 0)
typedef unsigned int __poll_t;
#endif""",
            """/* __poll_t is already provided by this floral kernel's linux/types.h. */""",
            "KernelSU Next legacy event queue poll typedef compatibility",
        ),
    )
    for path, old, new, label in patches:
        original = path.read_text()
        if old in original:
            if original.count(old) != 1:
                raise ValueError("Unexpected repeated source block in " + str(path))
            path.write_text(original.replace(old, new, 1))
            print("PATCH: " + label, flush=True)
        elif new in original:
            print("PASS: Already compatible: " + label, flush=True)
        else:
            raise ValueError(
                "Upstream source changed; refusing a blind compatibility edit: " + str(path)
            )


def run(root, plugin, script, *args):
    cmd = [sys.executable, str(root / plugin / "tools" / script), *map(str, args)]
    print("+", " ".join(cmd), flush=True)
    subprocess.run(cmd, cwd=root, check=True)


def prepare(root, offline=False):
    prepare_lunaris_property_partitions(root)
    prepare_coral_about_phone(root)
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

    prepare_android16_source_compat(root)

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


def verify_coral_about_phone_output(root, output):
    """Verify packaged Settings resources, not just checked-out source strings."""
    settings_apk = output / "system_ext/priv-app/Settings/Settings.apk"
    if not settings_apk.is_file():
        raise FileNotFoundError("Missing built Settings APK: " + str(settings_apk))
    aapt2 = output.parents[2] / "host/linux-x86/bin/aapt2"
    if not aapt2.is_file():
        print("NOTE: aapt2 unavailable; built Settings resource inspection skipped.", flush=True)
        return
    dump = subprocess.run(
        [str(aapt2), "dump", "resources", "--values", str(settings_apk)],
        capture_output=True, text=True, check=True,
    ).stdout
    overlay = root / (
        "device/google/coral/overlay/packages/apps/Settings/"
        "res/values/lunaris_coral_specs.xml"
    )
    values = {
        item.get("name"): item.text
        for item in ET.parse(overlay).getroot().findall("string")
    }
    placeholders = ("ICorn 10 Pro Max", "Chicken Nuggets® 52",
                    "15000 mAh", "Cathode Ray Tube 24hz")
    for name, value in values.items():
        if f"string/{name}" not in dump or value not in dump:
            raise ValueError("Built Settings.apk lacks Coral About Phone value: "
                             + name + "=" + str(value))
    if any(value in dump for value in placeholders):
        raise ValueError("Built Settings.apk still contains Lunaris joke About Phone values.")
    print("PASS: Settings.apk contains genuine Pixel 4 XL About Phone specs.", flush=True)


def verify_output(root, product_out):
    output = product_out.resolve()
    verify_camera(root, output)
    verify_coral_about_phone_output(root, output)
    face = output / "vendor/bin/hw/android.hardware.biometrics.face@1.0-service.google"
    if not face.is_file():
        raise FileNotFoundError("Missing hardware Face HAL: " + str(face))
    # The Lunaris software FaceUnlock APK must never coexist with Google's
    # IR/Citadel hardware face provider. Checking packaged output catches a
    # stale install that remains after disabling TARGET_FACE_UNLOCK_SUPPORTED.
    software_face = [
        str(path)
        for partition in ("system", "system_ext", "product", "vendor")
        for path in (output / partition).rglob("FaceUnlock.apk")
    ]
    if software_face:
        raise ValueError(
            "Software 2D FaceUnlock conflicts with Floral 3D HAL; "
            "run m installclean and rebuild: " + ", ".join(software_face)
        )
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
