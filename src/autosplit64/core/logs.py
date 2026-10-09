"""
The log of this session, AutoSplit64++.log, and the previous session's, AutoSplit64++.old.log. They are next to
the settings, for sending with a bug report.
"""
import faulthandler
import logging
import os
import platform
import sys
import threading
from pathlib import Path

LOG_FILE = "AutoSplit64++.log"
OLD_LOG_FILE = "AutoSplit64++.old.log"
# What faulthandler writes when Python crashes
CRASH_MARKER = "Fatal Python error"


def start_session(version, directory="."):
    """ Start this session's log, keeping the previous session's as the old log. Returns its handler. """
    directory = Path(directory)
    log = directory / LOG_FILE
    try:
        os.replace(log, directory / OLD_LOG_FILE)
    except OSError:
        # The first session, or another AutoSplit64++ has the log open on Windows, and both write to it
        pass

    handler = logging.FileHandler(log, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    root = logging.getLogger()
    root.addHandler(handler)
    root.setLevel(logging.INFO)

    logging.getLogger(".log").info("AutoSplit64++ %s on %s, Python %s%s", version, platform.platform(),
                                   platform.python_version(), "" if getattr(sys, "frozen", False) else ", from source")
    return handler


def install_crash_handlers(handler, on_error=None):
    """
    Log what nothing else handled: exceptions in the GUI and in threads, then call on_error with the exception,
    and with faulthandler, crashes that end AutoSplit64++, in the log of handler
    """
    def log_exception(exc_type, exc, traceback, thread=None):
        logging.getLogger(".log").critical("Unhandled error%s", f" in thread {thread.name}" if thread else "",
                                           exc_info=(exc_type, exc, traceback))
        if on_error:
            on_error(exc)

    def except_hook(exc_type, exc, traceback):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc, traceback)
        else:
            log_exception(exc_type, exc, traceback)

    def thread_except_hook(args):
        if not issubclass(args.exc_type, SystemExit):
            log_exception(args.exc_type, args.exc_value, args.exc_traceback, args.thread)

    # PyQt6 also calls it for exceptions in slots, instead of aborting
    sys.excepthook = except_hook
    threading.excepthook = thread_except_hook
    faulthandler.enable(handler.stream)


def previous_session_crashed(directory="."):
    """ Whether the previous session ended in a crash, which its log, OLD_LOG_FILE, has """
    try:
        return CRASH_MARKER in (Path(directory) / OLD_LOG_FILE).read_text(encoding="utf-8", errors="replace")
    except FileNotFoundError:
        return False
