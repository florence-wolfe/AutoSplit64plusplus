import os
import sys
from pathlib import Path


def base_path(relative_path=None):
    directory = os.path.dirname(sys.argv[0])
    # A macOS .app runs from <name>.app/Contents/MacOS, and its resources are next to the .app
    if getattr(sys, "frozen", False) and sys.platform == "darwin":
        directory = os.path.abspath(os.path.join(directory, "..", "..", ".."))

    if not relative_path:
        return directory
    else:
        return os.path.join(directory, relative_path).replace('\\', '/')


def absolute_path(relative_path=None):
    if not relative_path:
        return str(Path().absolute()).replace('\\', '/')
    else:
        return os.path.join(Path().absolute(), relative_path).replace('\\', '/')


def resource_path(relative_path):
    """
    Get absolute path to resource, works for dev and for PyInstaller

    Credit: https://stackoverflow.com/questions/7674790/bundling-data-files-with-pyinstaller-onefile/13790741#13790741
    """
    # try:
    #     # PyInstaller creates a temp folder and stores path in _MEIPASS
    #     path = sys._MEIPASS
    # except Exception:
    #     path = os.path.abspath(".")
    path = os.path.abspath(".")
    return os.path.join(path, relative_path).replace('\\', '/')


def abs_to_rel(p):
    # Convert to relative path, if possible
    rel_path = p.replace(absolute_path(), "")

    # Store Path
    if rel_path != p:
        return rel_path[1:]
    else:
        return p


def rel_to_abs(p):
    if not os.path.isabs(p):
        return absolute_path(p)
    else:
        return p
