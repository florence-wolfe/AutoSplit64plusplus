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
# Why the last update couldn't be installed, which the install script leaves next to the settings for the app to tell
FAILED_UPDATE_FILE = "AutoSplit64++.update-failed.txt"


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
    try:
        data = response.json()
        assets = {asset["name"]: asset["browser_download_url"] for asset in data["assets"]}
        tag, page = data["tag_name"], data["html_url"]
    except (ValueError, KeyError, TypeError) as e:
        raise UpdateError("GitHub's answer about the latest release couldn't be read.") from e

    suffix = ASSET_SUFFIXES.get(sys.platform)
    app = next((name for name in assets if suffix and name.endswith(suffix)), None)
    if app is None or CHECKSUMS not in assets:
        return None
    return Release(tag.removeprefix("v"), app, assets[app], assets[CHECKSUMS], page)


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
    """
    Downloads the release's app into directory and checks it. progress(done, total) is called as it goes.
    Nothing is left of a download that failed.
    """
    path = Path(directory) / release.asset_name
    try:
        _download(release, path, progress)
    except BaseException:
        path.unlink(missing_ok=True)
        raise
    return path


def _download(release, path, progress):
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
    if expected is None:
        raise UpdateError(f"{CHECKSUMS} has no checksum for {release.asset_name}.")
    if expected != sha256.hexdigest():
        raise UpdateError(f"The download of {release.asset_name} doesn't match its checksum.")


# Waits for AutoSplit64++ to quit, then swaps the app for the update, keeping the old one if that fails
_MACOS_INSTALL = """#!/bin/sh
set -x
# Leave why for the app to tell, and open it as it was
fail() {
    printf '%s\n\nWhat happened is in %s.\n' "$1" "$AS64_WORK/install.log" > "$AS64_NOTICE"
    if [ "$AS64_RELAUNCH" = 1 ]; then open "$AS64_APP"; fi
    exit 1
}
while kill -0 "$AS64_PID" 2>/dev/null; do sleep 0.2; done
staging="$AS64_WORK/update"
rm -rf "$staging"
ditto -x -k "$AS64_ZIP" "$staging" || fail "Couldn't unpack the update."
new=$(find "$staging" -maxdepth 1 -name "*.app" | head -n 1)
[ -d "$new" ] || fail "The update has no app in it."
rm -rf "$AS64_APP.old"
mv "$AS64_APP" "$AS64_APP.old" || fail "Couldn't move $AS64_APP aside."
if mv "$new" "$AS64_APP"; then
    rm -rf "$AS64_APP.old"
else
    mv "$AS64_APP.old" "$AS64_APP"
    fail "Couldn't put the update in place of $AS64_APP."
fi
if [ "$AS64_RELAUNCH" = 1 ]; then open "$AS64_APP"; fi
"""

# Waits for AutoSplit64++ to quit, then replaces the app's files. Settings, routes and
# generated reset templates are the user's, so routes and templates only gain missing files.
_WINDOWS_INSTALL = r"""
param([int]$AppPid, [string]$Zip, [string]$InstallDir, [string]$Work, [int]$Relaunch, [string]$Notice)
$ErrorActionPreference = "Stop"
# The app's files moved aside, as (where it was, where it is now), to put back if the update fails
$aside = New-Object System.Collections.ArrayList
try {
    Wait-Process -Id $AppPid -ErrorAction SilentlyContinue
    # Any other AutoSplit64++ from this folder keeps its files open, which the update can't replace
    $deadline = (Get-Date).AddSeconds(60)
    $prefix = (Resolve-Path $InstallDir).Path.TrimEnd("\") + "\"
    while (Get-Process | Where-Object { $_.Path -and $_.Path.StartsWith($prefix, [StringComparison]::OrdinalIgnoreCase) }) {
        if ((Get-Date) -gt $deadline) { throw "AutoSplit64++ is still running from $InstallDir" }
        Start-Sleep 1
    }
    $staging = Join-Path $Work "update"
    if (Test-Path $staging) { Remove-Item $staging -Recurse -Force }
    Expand-Archive -Path $Zip -DestinationPath $staging -Force
    $new = Get-ChildItem $staging -Directory | Select-Object -First 1

    # Moved aside before anything is replaced: Windows refuses to move a folder while a file in it is open, which
    # then stops the update with the app as it was, instead of half of it deleted
    $names = @("libraries", "resources", "obs-plugin") + @(Get-ChildItem $new.FullName -File | ForEach-Object Name)
    foreach ($name in $names) {
        $target = Join-Path $InstallDir $name
        if (-not (Test-Path $target)) { continue }
        $old = "$target.old"
        if (Test-Path $old) { Remove-Item $old -Recurse -Force -ErrorAction SilentlyContinue }
        if (Test-Path $old) { $old = "$target.old-$(Get-Date -Format yyyyMMddHHmmss)" }
        # A rename, which Move-Item isn't always: it copies a folder it can't rename, and fails partway
        if (Test-Path $target -PathType Container) { [IO.Directory]::Move($target, $old) } else { [IO.File]::Move($target, $old) }
        [void]$aside.Add(@($target, $old))
    }
    foreach ($name in "libraries", "resources", "obs-plugin") {
        $source = Join-Path $new.FullName $name
        if (Test-Path $source) { Copy-Item $source (Join-Path $InstallDir $name) -Recurse }
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

    # The app as it was, unless something still has a file of it open, e.g. antivirus, which a later update removes
    foreach ($moved in $aside) { Remove-Item $moved[1] -Recurse -Force -ErrorAction SilentlyContinue }
    $aside.Clear()

    if ($Relaunch) {
        $exe = Get-ChildItem $InstallDir -Filter "*.exe" | Select-Object -First 1
        Start-Process $exe.FullName -WorkingDirectory $InstallDir
    }
}
catch {
    "Install failed: $($_ | Out-String)"
    # For the app to tell, the next time it starts
    Set-Content -LiteralPath $Notice -Encoding UTF8 `
        -Value "$($_.Exception.Message)`r`n`r`nWhat happened is in $(Join-Path $Work "install.log")."
    # Put the app back as it was, newest first, over whatever of the update was copied
    for ($i = $aside.Count - 1; $i -ge 0; $i--) {
        $target, $old = $aside[$i]
        try {
            if (Test-Path $target) { Remove-Item $target -Recurse -Force }
            if (Test-Path $old -PathType Container) { [IO.Directory]::Move($old, $target) } else { [IO.File]::Move($old, $target) }
        }
        catch { "Couldn't put back ${target}: $($_ | Out-String)" }
    }
    if ($Relaunch) {
        $exe = Get-ChildItem $InstallDir -Filter "*.exe" | Select-Object -First 1
        if ($exe) { Start-Process $exe.FullName -WorkingDirectory $InstallDir }
    }
    exit 1
}
"""


def take_failed_update_notice(directory="."):
    """ Why the last update couldn't be installed, which is then forgotten, or None if it could """
    path = Path(directory) / FAILED_UPDATE_FILE
    try:
        # The Windows install script writes it with a byte order mark
        text = path.read_text(encoding="utf-8-sig").strip()
    except FileNotFoundError:
        return None
    path.unlink()
    return text


def can_install():
    """ Updates are installed into the built app, not when running from source """
    return getattr(sys, "frozen", False) and sys.platform in ASSET_SUFFIXES


def install_on_exit(zip_path, relaunch, pid=None, install_path=None, notice=None):
    """
    Installs the update in zip_path once the process pid (this one by default) has exited.
    install_path is the app to replace: the .app on macOS, the app's folder on Windows.
    If it fails, why is left in notice, FAILED_UPDATE_FILE next to the settings by default, for the app to tell.
    """
    pid = pid or os.getpid()
    notice = Path(notice or FAILED_UPDATE_FILE).absolute()
    work = tempfile.mkdtemp(prefix="as64-update-")
    # Nobody sees the script run, so log all its output, including errors starting it
    log_path = Path(work) / "install.log"
    log = open(log_path, "w")

    if sys.platform == "darwin":
        # This app is <name>.app/Contents/MacOS/<name>
        install_path = install_path or Path(sys.executable).parents[2]
        script = Path(work) / "install.sh"
        script.write_text(_MACOS_INSTALL)
        env = dict(os.environ, AS64_PID=str(pid), AS64_ZIP=str(zip_path), AS64_APP=str(install_path),
                   AS64_WORK=work, AS64_RELAUNCH="1" if relaunch else "0", AS64_NOTICE=str(notice))
        process = subprocess.Popen(["/bin/sh", str(script)], env=env, start_new_session=True, stdout=log, stderr=subprocess.STDOUT)

    elif sys.platform == "win32":
        install_path = install_path or Path(sys.executable).parent
        script = Path(work) / "install.ps1"
        script.write_text(_WINDOWS_INSTALL)
        process = subprocess.Popen(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script),
             "-AppPid", str(pid), "-Zip", str(zip_path), "-InstallDir", str(install_path), "-Work", work,
             "-Relaunch", "1" if relaunch else "0", "-Notice", str(notice)],
            stdout=log, stderr=subprocess.STDOUT,
            creationflags=subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP)
    else:
        log.close()
        raise UpdateError(f"Updates can't be installed on {sys.platform}")

    # The script has its own handle on the log
    log.close()
    process.log_path = log_path
    logging.getLogger(".log").info("Installing the update after AutoSplit64++ quits, logging to %s", process.log_path)
    return process
