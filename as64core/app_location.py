"""
Moving the macOS app to Applications when it runs from Downloads.

macOS runs a downloaded app that wasn't moved from a hidden, read-only copy ("App Translocation"),
where updates can't replace it. Moving it to Applications, without the downloaded flag that
causes translocation, avoids that.
"""
import os
import subprocess
import sys
from pathlib import Path

TRANSLOCATED = "translocated"
DOWNLOADS = "downloads"


def running_app():
    """ The .app this is, as the executable is <name>.app/Contents/MacOS/<name> """
    return Path(sys.executable).parents[2]


def move_reason(app):
    """ Why the app should be moved to Applications (TRANSLOCATED or DOWNLOADS), or None """
    if not (getattr(sys, "frozen", False) and sys.platform == "darwin"):
        return None
    if "/AppTranslocation/" in str(app):
        return TRANSLOCATED
    if Path(app).is_relative_to(Path.home() / "Downloads"):
        return DOWNLOADS
    return None


def applications_folder():
    """ /Applications, or the user's own Applications folder without permission to it """
    if os.access("/Applications", os.W_OK):
        return Path("/Applications")
    folder = Path.home() / "Applications"
    folder.mkdir(exist_ok=True)
    return folder


def _trash(path):
    from Foundation import NSFileManager, NSURL
    trashed, _, error = NSFileManager.defaultManager().trashItemAtURL_resultingItemURL_error_(
        NSURL.fileURLWithPath_(str(path)), None, None)
    if not trashed:
        raise OSError(error.localizedDescription())


def move_to(app, folder):
    """ Copies the app into folder, replacing an earlier copy (which goes to the Trash). Returns the new app. """
    destination = Path(folder) / Path(app).name
    if destination.exists():
        _trash(destination)
    subprocess.run(["ditto", str(app), str(destination)], check=True)
    # Without the downloaded flag, macOS runs it where it is; the user already allowed it to open
    subprocess.run(["xattr", "-d", "-r", "com.apple.quarantine", str(destination)], capture_output=True)
    return destination


def reopen_after_exit(app, pid=None):
    """ Opens app once this process (pid) has exited, so the two don't run at once """
    subprocess.Popen(["/bin/sh", "-c", 'while kill -0 "$1" 2>/dev/null; do sleep 0.2; done; open "$2"', "reopen",
                      str(pid or os.getpid()), str(app)], start_new_session=True)
