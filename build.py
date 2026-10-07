"""
Builds AutoSplit64++ with PyInstaller: `uv run build.py`

- Windows: dist/AutoSplit64++/ with AutoSplit64++.exe and its resources next to it
- macOS: dist/AutoSplit64++.app, which includes its resources and can be installed anywhere
"""
import os
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

    app = Path("dist") / f"{NAME}.app"
    shutil.rmtree(app, ignore_errors=True)
    shutil.copytree(work / "dist" / f"{NAME}.app", app, symlinks=True)
    return app


if __name__ == "__main__":
    os.chdir(Path(__file__).parent)

    if sys.platform == "win32":
        built = build_windows()
    elif sys.platform == "darwin":
        built = build_macos()
    else:
        sys.exit("AutoSplit64++ can be built on Windows and macOS")

    print(f"Built {built}")
