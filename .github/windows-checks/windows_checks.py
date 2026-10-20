"""
Helpers for windows-checks.yml, which runs AutoSplit64++ releases on Windows to find where one crashes.

- play VIDEO OUT: plays VIDEO in a window, over and over, as a game to capture, and writes where the window is to OUT
- configure APP WINDOW RECORDING: sets the app in APP to autostart, capturing the game window that WINDOW (play's
  OUT) describes, which plays the recording RECORDING of tests/recordings, with its route
- install-script REF OUT: writes the Windows install script of the updater of the release at the git ref REF to OUT
- dismiss PID APP: closes the settings changes an update offers, if the app with process id PID shows them

play runs in a copy of Python by another name, since the app doesn't list python.exe's windows to capture, so it only
uses OpenCV and the standard library.
"""
import ast
import ctypes
import json
import shutil
import subprocess
import sys
import time
from ctypes import wintypes
from pathlib import Path

RECORDINGS = Path(__file__).parents[2] / "tests" / "recordings"
GAME_PROCESS = "as64game.exe"
GAME_TITLE = "AutoSplit64++ windows checks game"
DWMWA_EXTENDED_FRAME_BOUNDS = 9
WM_CLOSE = 0x0010

user32 = ctypes.windll.user32


def window_geometry(hwnd):
    """
    The window's size, as the app's get_capture_size measures it, and where its client area is in what
    Windows.Graphics.Capture captures of it: the window's visible frame, without the invisible resize borders
    """
    window = wintypes.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(window))
    frame = wintypes.RECT()
    ctypes.windll.dwmapi.DwmGetWindowAttribute(hwnd, DWMWA_EXTENDED_FRAME_BOUNDS, ctypes.byref(frame),
                                               ctypes.sizeof(frame))
    client = wintypes.POINT(0, 0)
    user32.ClientToScreen(hwnd, ctypes.byref(client))
    return {"size": [window.right - window.left, window.bottom - window.top],
            "client_offset": [client.x - frame.left, client.y - frame.top]}


def play(video, out):
    import cv2

    capture = cv2.VideoCapture(video)
    delay = max(1, round(1000 / capture.get(cv2.CAP_PROP_FPS)))
    cv2.namedWindow(GAME_TITLE, cv2.WINDOW_AUTOSIZE)
    written = False
    while True:
        ok, frame = capture.read()
        if not ok:
            capture.set(cv2.CAP_PROP_POS_FRAMES, 0)
            continue
        cv2.imshow(GAME_TITLE, frame)
        cv2.waitKey(delay)
        if not written:
            geometry = window_geometry(user32.FindWindowW(None, GAME_TITLE))
            Path(out).write_text(json.dumps(dict(geometry, frame=[frame.shape[1], frame.shape[0]])))
            written = True


def configure(app, window, recording):
    app = Path(app)
    settings_file = app / "config.ini"
    # Settings an earlier release made, or a fresh install's, which it makes from its defaults
    settings = json.loads((settings_file if settings_file.exists() else app / "defaults.ini").read_text())
    window = json.loads(Path(window).read_text())
    recording = json.loads((RECORDINGS / f"{recording}.json").read_text())

    route = shutil.copy(RECORDINGS / recording["route"], app / "routes")
    x, y, width, height = recording["game_region"]
    offset_x, offset_y = window["client_offset"]

    settings.setdefault("general", {})["auto_start"] = True
    settings.setdefault("route", {})["path"] = str(Path(route).resolve())
    settings.setdefault("connection", {})["ls_connection_type"] = 0
    settings.setdefault("game", {}).update(use_obs=False, capture_source="window", process_name=GAME_PROCESS,
                                           capture_size=window["size"],
                                           game_region=[x + offset_x, y + offset_y, width, height])
    settings_file.write_text(json.dumps(settings, indent=4))
    print(json.dumps(settings, indent=4))


def install_script(ref, out):
    source = subprocess.run(["git", "show", f"{ref}:src/autosplit64/core/updater.py"],
                            capture_output=True, text=True, check=True).stdout
    for node in ast.parse(source).body:
        if isinstance(node, ast.Assign) and any(getattr(t, "id", None) == "_WINDOWS_INSTALL" for t in node.targets):
            Path(out).write_text(ast.literal_eval(node.value))
            return
    sys.exit(f"{ref}'s updater has no Windows install script")


def migrated(app):
    return "_migrations" in json.loads((Path(app) / "config.ini").read_text())


def qt_windows(pid):
    """ The visible top-level Qt windows of the process pid, leaving out PyInstaller's Tk splash screen """
    windows = []

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def add(hwnd, _):
        owner = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(owner))
        name = ctypes.create_unicode_buffer(256)
        user32.GetClassNameW(hwnd, name, 256)
        if owner.value == pid and user32.IsWindowVisible(hwnd) and name.value.startswith("Qt"):
            windows.append(hwnd)
        return True

    user32.EnumWindows(add, 0)
    return windows


def dismiss(pid, app):
    """
    The settings changes are asked about before the settings are migrated and saved, and before the main window
    opens, so a Qt window while they aren't migrated is the dialog. Closing it keeps the settings as they were.
    """
    pid = int(pid)
    if migrated(app):
        print("The settings were migrated without asking")
        return
    windows = qt_windows(pid)
    if not windows:
        print("The settings aren't migrated, and no window asks about them")
        return
    for hwnd in windows:
        user32.PostMessageW(hwnd, WM_CLOSE, 0, 0)
    for _ in range(20):
        time.sleep(0.5)
        if migrated(app):
            print(f"Closed the settings changes dialog ({len(windows)} window), keeping the settings")
            return
    print("Closed the settings changes dialog, but the settings still aren't migrated")


if __name__ == "__main__":
    commands = {"play": play, "configure": configure, "install-script": install_script, "dismiss": dismiss}
    commands[sys.argv[1]](*sys.argv[2:])
