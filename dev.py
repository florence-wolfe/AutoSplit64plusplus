"""
Runs AutoSplit64++ for development, and restarts it when its code changes: `uv run dev.py`

- `--open NAME` opens a window after each start, one of: debug, route-editor, settings, capture, reset-templates, about
- Quitting AutoSplit64++ ends it. When AutoSplit64++ crashes, it starts again on the next change.

It uses the settings in the repository, like `uv run python -m autosplit64`.
"""
import argparse
import subprocess
import sys
import time
from pathlib import Path

SOURCE = Path(__file__).parent / "src" / "autosplit64"
# Code, and the processors of split detection
WATCHED = {".py", ".processor"}
# Seconds between looking for changes
INTERVAL = 0.5

# What opens each window, like the menu does
WINDOWS = {
    "debug": lambda app: app.dialogs["debug_dialog"].show(),
    "route-editor": lambda app: app.dialogs["route_editor"].show(),
    "settings": lambda app: app.dialogs["settings_dialog"].show(),
    "capture": lambda app: app._edit_coordinates(),
    "reset-templates": lambda app: app.dialogs["reset_dialog"].show(),
    "about": lambda app: app.dialogs["about_dialog"].show(),
}


def snapshot(directory=SOURCE):
    """ Each watched file's modification time """
    return {path.relative_to(directory).as_posix(): path.stat().st_mtime_ns
            for path in directory.rglob("*") if path.suffix in WATCHED}


def changes(before, after):
    """ The files that changed, were added or deleted """
    return sorted(name for name in before.keys() | after.keys() if before.get(name) != after.get(name))


def open_window(app, name):
    WINDOWS[name](app)


def run_app(window):
    """ Run AutoSplit64++ in this process, opening window once it's there """
    from PyQt6 import QtCore
    from autosplit64 import main

    if window:
        start = main.AutoSplit64.__init__

        def init(self, *args, **kwargs):
            start(self, *args, **kwargs)
            QtCore.QTimer.singleShot(0, lambda: open_window(self.app, window))

        main.AutoSplit64.__init__ = init
    main.main()


def start(window):
    return subprocess.Popen([sys.executable, __file__, "--app", *(["--open", window] if window else [])])


def stop(app):
    app.terminate()
    try:
        app.wait(timeout=5)
    except subprocess.TimeoutExpired:
        app.kill()
        app.wait()


def watch(window):
    app = start(window)
    # Whether it ended with an error, which was said already
    crashed = False
    before = snapshot()
    try:
        while True:
            time.sleep(INTERVAL)
            after = snapshot()
            changed = changes(before, after)
            before = after
            if changed:
                print(f"Changed: {', '.join(changed)}. Restarting.", flush=True)
                if app.poll() is None:
                    stop(app)
                app = start(window)
                crashed = False
            elif app.poll() == 0:
                print("AutoSplit64++ quit.")
                return
            elif app.poll() is not None and not crashed:
                print(f"AutoSplit64++ ended with {app.returncode}. It starts again when the code changes.", flush=True)
                crashed = True
    except KeyboardInterrupt:
        if app.poll() is None:
            stop(app)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run AutoSplit64++, restarting it when its code changes")
    parser.add_argument("--open", choices=sorted(WINDOWS), help="the window to open after each start")
    parser.add_argument("--app", action="store_true", help=argparse.SUPPRESS)
    arguments = parser.parse_args()
    if arguments.app:
        run_app(arguments.open)
    else:
        watch(arguments.open)
