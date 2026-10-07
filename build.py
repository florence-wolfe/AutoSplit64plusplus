"""
Builds AutoSplit64++ with PyInstaller: `uv run build.py`

- Windows: dist/AutoSplit64++/ with AutoSplit64++.exe and its resources next to it
- macOS: dist/AutoSplit64++.app, which includes its resources and can be installed anywhere

The version comes from the release's git tag (AS64_VERSION, set in CI), or git describe.
"""
import contextlib
import os
import plistlib
import shutil
import subprocess
import sys
from pathlib import Path

import PyInstaller.__main__

NAME = "AutoSplit64++"
DATA_DIRS = ["logic", "resources", "routes", "templates"]
# Files the app writes at runtime, which don't belong in a build
IGNORE = shutil.ignore_patterns("game_preview.png", ".DS_Store")
OBS_PLUGIN = Path("obs-plugin/build_x64/RelWithDebInfo/autosplit64plus-framegrabber.dll")
VERSION_FILE = Path("as64gui/_version.py")


def release_version():
    """ The version to build, e.g. 0.4.0 for the tag v0.4.0 """
    version = os.environ.get("AS64_VERSION") or subprocess.run(
        ["git", "describe", "--tags", "--match", "v[0-9]*", "--dirty"], capture_output=True, text=True).stdout.strip()
    return version.removeprefix("v") or "dev"


@contextlib.contextmanager
def version_file(version):
    """ Puts the version in the app while it's built """
    VERSION_FILE.write_text(f'VERSION = "{version}"\n')
    try:
        yield
    finally:
        VERSION_FILE.unlink()


def build_windows():
    PyInstaller.__main__.run([
        "--noconfirm",
        "--name", NAME,
        "--splash", "resources/gui/icons/as64plus.png",
        "--icon", "resources/gui/icons/as64plus.ico",
        "--noconsole",
        "--clean",
        "--noupx",
        "--contents-directory", "libraries",
        "AutoSplit64.py",
    ])

    app_dir = Path("dist") / NAME
    for name in DATA_DIRS:
        shutil.copytree(name, app_dir / name, dirs_exist_ok=True, ignore=IGNORE)
    shutil.copy2("defaults.ini", app_dir)

    if OBS_PLUGIN.exists():
        (app_dir / "obs-plugin").mkdir(exist_ok=True)
        shutil.copy2(OBS_PLUGIN, app_dir / "obs-plugin")
    else:
        print(f"OBS plugin not found at {OBS_PLUGIN}, building without it")

    return app_dir / f"{NAME}.exe"


def build_macos():
    work = Path("build/mac")

    # Convert the PNG icon to .icns
    iconset = work / "as64plus.iconset"
    iconset.mkdir(parents=True, exist_ok=True)
    for size in (16, 32, 128, 256):
        subprocess.run(["sips", "-z", str(size), str(size), "resources/gui/icons/as64plus.png",
                        "--out", str(iconset / f"icon_{size}x{size}.png")], check=True, stdout=subprocess.DEVNULL)
    subprocess.run(["iconutil", "-c", "icns", str(iconset), "-o", str(work / "as64plus.icns")], check=True)

    # The resources are bundled in the app. At launch it copies them to Application Support.
    data = work / "data"
    shutil.rmtree(data, ignore_errors=True)
    add_data = []
    for name in DATA_DIRS:
        shutil.copytree(name, data / name, ignore=IGNORE)
        add_data += ["--add-data", f"{data / name}:{name}"]

    PyInstaller.__main__.run([
        "--noconfirm",
        "--name", NAME,
        "--icon", str(work / "as64plus.icns"),
        "--osx-bundle-identifier", "local.autosplit64plusplus",
        "--windowed",
        "--clean",
        "--noupx",
        "--workpath", str(work),
        "--distpath", str(work / "dist"),
        *add_data,
        "--add-data", "defaults.ini:.",
        "AutoSplit64.py",
    ])

    # macOS stops an app that uses a camera without saying why
    built = work / "dist" / f"{NAME}.app"
    info_plist = built / "Contents" / "Info.plist"
    info = plistlib.loads(info_plist.read_bytes())
    info["NSCameraUsageDescription"] = "AutoSplit64++ captures the game from your capture card or virtual camera."
    info_plist.write_bytes(plistlib.dumps(info))
    # Changing Info.plist invalidates the signature
    subprocess.run(["codesign", "--force", "--deep", "--sign", "-", str(built)], check=True)

    app = Path("dist") / f"{NAME}.app"
    shutil.rmtree(app, ignore_errors=True)
    shutil.copytree(built, app, symlinks=True)
    return app


if __name__ == "__main__":
    os.chdir(Path(__file__).parent)

    if sys.platform not in ("win32", "darwin"):
        sys.exit("AutoSplit64++ can be built on Windows and macOS")

    version = release_version()
    with version_file(version):
        built = build_windows() if sys.platform == "win32" else build_macos()

    print(f"Built {built} {version}")
