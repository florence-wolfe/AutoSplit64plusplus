"""
Updates AutoSplit64++ from its GitHub releases: finds a newer release, downloads the app for this
platform, checks it against the release's SHA256SUMS, and installs it after AutoSplit64++ quits.

The app can't replace itself while it runs (and a running .exe can't be overwritten), so a small
detached script waits for it to quit, installs the update and optionally reopens it.
"""
import hashlib
import logging
import os
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

import requests

# The asset of each platform, as named by .github/workflows/release.yml
ASSET_SUFFIXES = {"darwin": "-macos-arm64.zip", "win32": "-windows-x64.zip"}
CHECKSUMS = "SHA256SUMS"


class UpdateError(Exception):
    pass


@dataclass
class Release:
    version: str
    asset_name: str
    asset_url: str
    checksums_url: str
    page_url: str


def parse_version(version):
    """ (0, 4, 0) for v0.4.0 or 0.4.0, None for anything that isn't a release, e.g. dev or 0.4.0-3-gabc1234 """
    match = re.fullmatch(r"v?(\d+)\.(\d+)\.(\d+)", version)
    return tuple(int(part) for part in match.groups()) if match else None


def latest_release(repo):
    """ The latest release of repo with an app for this platform, or None """
    response = requests.get(f"https://api.github.com/repos/{repo}/releases/latest", timeout=10)
    response.raise_for_status()
    data = response.json()

    assets = {asset["name"]: asset["browser_download_url"] for asset in data["assets"]}
    suffix = ASSET_SUFFIXES.get(sys.platform)
    app = next((name for name in assets if suffix and name.endswith(suffix)), None)
    if app is None or CHECKSUMS not in assets:
        return None
    return Release(data["tag_name"].removeprefix("v"), app, assets[app], assets[CHECKSUMS], data["html_url"])


def newer_release(repo, current_version):
    """ The latest release if it's newer than current_version, which must be a release itself """
    current = parse_version(current_version)
    if current is None:
        return None
    release = latest_release(repo)
    if release is None or (parse_version(release.version) or (0, 0, 0)) <= current:
        return None
    return release


def download(release, directory, progress=None):
    """ Downloads the release's app into directory and checks it. progress(done, total) is called as it goes. """
    path = Path(directory) / release.asset_name
    sha256 = hashlib.sha256()
    with requests.get(release.asset_url, stream=True, timeout=30) as response:
        response.raise_for_status()
        total = int(response.headers.get("Content-Length", 0))
        done = 0
        with open(path, "wb") as file:
            for chunk in response.iter_content(1024 * 1024):
                file.write(chunk)
                sha256.update(chunk)
                done += len(chunk)
                if progress:
                    progress(done, total)

    checksums = requests.get(release.checksums_url, timeout=10)
    checksums.raise_for_status()
    expected = next((line.split()[0] for line in checksums.text.splitlines()
                     if line.split()[-1:] == [release.asset_name]), None)
    if expected != sha256.hexdigest():
        path.unlink()
        raise UpdateError(f"The download of {release.asset_name} doesn't match its checksum.")
    return path


# Waits for AutoSplit64++ to quit, then swaps the app for the update, keeping the old one if that fails
_MACOS_INSTALL = """#!/bin/sh
# Log what happens, as nobody sees this script run
exec >"$AS64_WORK/install.log" 2>&1
set -x
while kill -0 "$AS64_PID" 2>/dev/null; do sleep 0.2; done
staging="$AS64_WORK/update"
rm -rf "$staging"
ditto -x -k "$AS64_ZIP" "$staging" || exit 1
new=$(find "$staging" -maxdepth 1 -name "*.app" | head -n 1)
[ -d "$new" ] || exit 1
rm -rf "$AS64_APP.old"
mv "$AS64_APP" "$AS64_APP.old" || exit 1
if mv "$new" "$AS64_APP"; then
    rm -rf "$AS64_APP.old"
else
    mv "$AS64_APP.old" "$AS64_APP"
    exit 1
fi
if [ "$AS64_RELAUNCH" = 1 ]; then open "$AS64_APP"; fi
"""

# Waits for AutoSplit64++ to quit, then replaces the app's files. Settings, routes and
# generated reset templates are the user's, so routes and templates only gain missing files.
_WINDOWS_INSTALL = r"""
param([int]$AppPid, [string]$Zip, [string]$InstallDir, [string]$Work, [int]$Relaunch)
$ErrorActionPreference = "Stop"
# Log what happens, as nobody sees this script run
Start-Transcript -Path (Join-Path $Work "install.log") | Out-Null
try {
    Wait-Process -Id $AppPid -ErrorAction SilentlyContinue
    $staging = Join-Path $Work "update"
    if (Test-Path $staging) { Remove-Item $staging -Recurse -Force }
    Expand-Archive -Path $Zip -DestinationPath $staging -Force
    $new = Get-ChildItem $staging -Directory | Select-Object -First 1

    foreach ($name in "libraries", "logic", "resources", "obs-plugin") {
        $source = Join-Path $new.FullName $name
        $target = Join-Path $InstallDir $name
        if (Test-Path $target) { Remove-Item $target -Recurse -Force }
        if (Test-Path $source) { Copy-Item $source $target -Recurse }
    }
    Get-ChildItem $new.FullName -File | Copy-Item -Destination $InstallDir -Force

    foreach ($name in "routes", "templates") {
        $source = Join-Path $new.FullName $name
        if (-not (Test-Path $source)) { continue }
        Get-ChildItem $source -Recurse -File | ForEach-Object {
            $target = Join-Path (Join-Path $InstallDir $name) $_.FullName.Substring($source.Length + 1)
            if (-not (Test-Path $target)) {
                New-Item -ItemType Directory -Force (Split-Path $target) | Out-Null
                Copy-Item $_.FullName $target
            }
        }
    }

    if ($Relaunch) {
        $exe = Get-ChildItem $InstallDir -Filter "*.exe" | Select-Object -First 1
        Start-Process $exe.FullName -WorkingDirectory $InstallDir
    }
}
catch {
    "Install failed: $($_ | Out-String)"
    exit 1
}
finally {
    Stop-Transcript | Out-Null
}
"""


def can_install():
    """ Updates are installed into the built app, not when running from source """
    return getattr(sys, "frozen", False) and sys.platform in ASSET_SUFFIXES


def install_on_exit(zip_path, relaunch, pid=None, install_path=None):
    """
    Installs the update in zip_path once the process pid (this one by default) has exited.
    install_path is the app to replace: the .app on macOS, the app's folder on Windows.
    """
    pid = pid or os.getpid()
    work = tempfile.mkdtemp(prefix="as64-update-")

    if sys.platform == "darwin":
        # This app is <name>.app/Contents/MacOS/<name>
        install_path = install_path or Path(sys.executable).parents[2]
        script = Path(work) / "install.sh"
        script.write_text(_MACOS_INSTALL)
        env = dict(os.environ, AS64_PID=str(pid), AS64_ZIP=str(zip_path), AS64_APP=str(install_path),
                   AS64_WORK=work, AS64_RELAUNCH="1" if relaunch else "0")
        process = subprocess.Popen(["/bin/sh", str(script)], env=env, start_new_session=True)

    elif sys.platform == "win32":
        install_path = install_path or Path(sys.executable).parent
        script = Path(work) / "install.ps1"
        script.write_text(_WINDOWS_INSTALL)
        process = subprocess.Popen(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script),
             "-AppPid", str(pid), "-Zip", str(zip_path), "-InstallDir", str(install_path), "-Work", work,
             "-Relaunch", "1" if relaunch else "0"],
            creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP)
    else:
        raise UpdateError(f"Updates can't be installed on {sys.platform}")

    process.log_path = Path(work) / "install.log"
    logging.getLogger(".log").info("Installing the update after AutoSplit64++ quits, logging to %s", process.log_path)
    return process
