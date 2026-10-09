"""
The log of this session, AutoSplit64++.log, and the previous session's, AutoSplit64++.old.log. They are next to
the settings, for sending with a bug report.
"""
import logging
import os
import platform
import sys
from pathlib import Path

LOG_FILE = "AutoSplit64++.log"
OLD_LOG_FILE = "AutoSplit64++.old.log"


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
