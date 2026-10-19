import os
import tempfile

from autosplit64.core import config

# The tests' windows are drawn in memory, so the parallel test processes don't each open windows, or show in the Dock
# on macOS. QT_QPA_PLATFORM=cocoa (or windows) shows them.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
# The app's default style, which main sets from the settings before the first window
os.environ.setdefault("QT_QUICK_CONTROLS_STYLE", "Material")

# The tests' settings start from the defaults, in a file of their own, instead of the config.ini of whoever runs them
# in the working directory, which they'd read, e.g. auto_start starting split detection in the main window's tests,
# and could overwrite
_settings = tempfile.TemporaryDirectory()
config._CONFIG_FILE_NAME = os.path.join(_settings.name, "config.ini")
