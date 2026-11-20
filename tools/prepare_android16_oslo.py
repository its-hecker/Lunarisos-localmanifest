#!/usr/bin/env python3
"""Build an Android 16-compatible OsloFeedback APK for LunarisOS 16.2.

Infinity-X's Android 17 APK calls Kotlin PluginDependency.INSTANCE.get();
LunarisOS 16.2 exposes Java's static PluginDependency.get(). Retain the
checksum-pinned original APK and rebuild only this Lunaris-specific variant.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import urllib.request
import zipfile

REPOSITORY = "its-hecker/infinity_OsloFeedback"
SOURCE_PATH = Path("smali/classes/com/google/oslo/OsloOverlay.smali")
PREBUILT_PATH = "proprietary/system_ext/priv-app/OsloFeedback/OsloFeedback.apk"
A16_APK_PATH = "generated/lunaris16/OsloFeedback.apk"
INSTANCE = (
    "    sget-object v3, Lcom/android/systemui/plugins/PluginDependency;"
    "->INSTANCE:Lcom/android/systemui/plugins/PluginDependency;\n\n"
    "    invoke-virtual {v3, p0, v0}, "
    "Lcom/android/systemui/plugins/PluginDependency;"
    "->get(Lcom/android/systemui/plugins/Plugin;Ljava/lang/Class;)Ljava/lang/Object;"
)
STATIC = (
    "    invoke-static {p0, v0}, "
    "Lcom/android/systemui/plugins/PluginDependency;"
    "->get(Lcom/android/systemui/plugins/Plugin;Ljava/lang/Class;)Ljava/lang/Object;"
)


def patch_smali(original):
    if original.count(INSTANCE) != 2:
        raise ValueError("Expected exactly two Android 17 PluginDependency.INSTANCE "
                         "calls; refusing to patch unknown upstream smali")
    result = original.replace(INSTANCE, STATIC)
    if "PluginDependency;->INSTANCE" in result or result.count(STATIC) != 2:
        raise ValueError("Unexpected PluginDependency references after patch")
    return result


APKEDITOR_VERSION = "1.4.9"
APKEDITOR_NAME = f"APKEditor-{APKEDITOR_VERSION}.jar"
APKEDITOR_URL = (
    f"https://github.com/REAndroid/APKEditor/releases/download/"
    f"V{APKEDITOR_VERSION}/{APKEDITOR_NAME}"
)
# Pinned bytes for REAndroid/APKEditor V1.4.9 release asset.
APKEDITOR_SHA256 = "a9cd40df818845456be6d696de6110c89edf4b0a0580cb83438ed6b25a366e67"
APKEDITOR_SIZE = 7733037


def verify_jar(path):
    if path.stat().st_size != APKEDITOR_SIZE:
        raise ValueError(f"APKEditor {APKEDITOR_VERSION} size mismatch: {path}")
    if hashlib.sha256(path.read_bytes()).hexdigest() != APKEDITOR_SHA256:
        raise ValueError(f"APKEditor {APKEDITOR_VERSION} SHA-256 mismatch: {path}")
    with zipfile.ZipFile(path) as archive:
        if archive.testzip() is not None:
            raise ValueError("APKEditor archive CRC verification failed")


def choose_jar(root):
    env = os.environ.get("APK_EDITOR_JAR")
    choices = [Path(env).expanduser()] if env else [
        root / "tools" / APKEDITOR_NAME,
        Path.home() / "tools" / APKEDITOR_NAME,
        Path.home() / APKEDITOR_NAME,
    ]
    for candidate in choices:
        if candidate.is_file():
            verify_jar(candidate)
            print(f"Verified APKEditor {APKEDITOR_VERSION}: {candidate}", flush=True)
            return candidate.resolve()
    if env:
        raise FileNotFoundError(f"APK_EDITOR_JAR points to a missing file: {env}")

    target = Path.home() / "tools" / APKEDITOR_NAME
    target.parent.mkdir(parents=True, exist_ok=True)
    print(f"Downloading pinned APKEditor {APKEDITOR_VERSION} from REAndroid...", flush=True)
    with tempfile.NamedTemporaryFile(prefix=".apkeditor-", dir=target.parent,
                                     delete=False) as staged:
        temporary = Path(staged.name)
        try:
            request = urllib.request.Request(APKEDITOR_URL, headers={
                "User-Agent": "LunarisOS-Android16-Oslo-build"
            })
            with urllib.request.urlopen(request, timeout=120) as response:
                while True:
                    chunk = response.read(1024 * 1024)
                    if not chunk:
                        break
                    staged.write(chunk)
        except BaseException:
            temporary.unlink(missing_ok=True)
            raise
    try:
        verify_jar(temporary)
        temporary.replace(target)
    finally:
        temporary.unlink(missing_ok=True)
    print(f"Verified APKEditor {APKEDITOR_VERSION}: {target}", flush=True)
    return target.resolve()

def prepare(root):
    root = root.resolve()
    motion = root / "vendor/hecker/floral/motionsense"
    lock = json.loads((motion / "prebuilts.lock.json").read_text())
    entries = [x for x in lock["artifacts"] if x.get("repository") == REPOSITORY
               and x.get("destination") == PREBUILT_PATH]
    if len(entries) != 1:
        raise ValueError("Missing the pinned Infinity-X Oslo source")
    revision = entries[0]["revision"]
    if len(revision) != 40 or any(c not in "0123456789abcdef" for c in revision):
        raise ValueError("Expected a full immutable Oslo source commit SHA")
    if not (motion / PREBUILT_PATH).is_file():
        raise FileNotFoundError("Missing original checksum-verified Oslo APK")

    blueprint_in = motion / "Android.bp.in"
    bp = blueprint_in.read_text()
    original_bp = f'apk: "{PREBUILT_PATH}"'
    patched_bp = f'apk: "{A16_APK_PATH}"'
    if bp.count(original_bp) != 1 and bp.count(patched_bp) != 1:
        raise ValueError("Oslo Soong import changed; refusing a blind edit")
    jar = choose_jar(root)

    output = motion / A16_APK_PATH
    output.parent.mkdir(parents=True, exist_ok=True)
    (root / "out").mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="lunaris-oslo16-", dir=root / "out") as temp:
        source = Path(temp) / "source"
        subprocess.run(["git", "clone", "--quiet", "--no-checkout",
                        f"https://github.com/{REPOSITORY}.git", str(source)], check=True)
        subprocess.run(["git", "-C", str(source), "checkout", "--quiet", "--detach",
                        revision], check=True)
        actual = subprocess.check_output(
            ["git", "-C", str(source), "rev-parse", "HEAD"], text=True).strip()
        if actual != revision:
            raise ValueError("Oslo checkout does not match locked revision")
        smali = source / SOURCE_PATH
        smali.write_text(patch_smali(smali.read_text()))
        candidate = Path(temp) / "OsloFeedback-lunaris16.apk"
        subprocess.run(["java", "-jar", str(jar), "b", "-no-cache",
                        "-i", str(source), "-o", str(candidate)], check=True)
        if not candidate.is_file() or candidate.stat().st_size < 1_000_000:
            raise ValueError("APKEditor failed to build a plausible Oslo APK")
        with zipfile.ZipFile(candidate) as apk:
            if apk.testzip() is not None:
                raise ValueError("Rebuilt APK failed CRC verification")
            for required in ("AndroidManifest.xml", "classes.dex"):
                if required not in apk.namelist():
                    raise ValueError("Rebuilt Oslo APK missing " + required)
        candidate.replace(output)

    if bp.count(original_bp) == 1:
        blueprint_in.write_text(bp.replace(original_bp, patched_bp, 1))
    print("PASS: Lunaris Android 16 Oslo APK uses static PluginDependency.get", flush=True)
    print("PASS: Original Android 17 prebuilt remains unmodified", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom-root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    try:
        prepare(args.rom_root)
    except (OSError, ValueError, subprocess.CalledProcessError,
            zipfile.BadZipFile) as error:
        print("Lunaris Android 16 Oslo compatibility: " + str(error), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
