import os

# The tests' windows are drawn in memory, so the parallel test processes don't each open windows, or show in the Dock
# on macOS. QT_QPA_PLATFORM=cocoa (or windows) shows them.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
# The app's default style, which main sets from the settings before the first window
os.environ.setdefault("QT_QUICK_CONTROLS_STYLE", "Material")
