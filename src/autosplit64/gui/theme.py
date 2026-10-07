"""
The app's colors: a theme, which is a palette from qt-themes or AutoSplit64++'s own. Widgets take
their colors from the palette, or status_color() for green, yellow and red. Like the palettes,
the app uses the Fusion style.
"""
import os

from PyQt6 import QtGui, QtWidgets

# qt-themes uses qtpy, which would otherwise look for PyQt5 first
os.environ.setdefault("QT_API", "pyqt6")
import qt_themes  # noqa: E402

DEFAULT = "default"

Role = QtGui.QPalette.ColorRole
# AutoSplit64++'s own dark palette
_DEFAULT_COLORS = {
    Role.Window: (60, 63, 65),
    Role.WindowText: (200, 203, 207),
    Role.Link: (88, 157, 246),
    Role.Base: (23, 25, 27),
    Role.AlternateBase: (53, 55, 57),
    Role.ToolTipBase: (53, 55, 57),
    Role.ToolTipText: (255, 255, 255),
    Role.Text: (200, 203, 207),
    Role.Button: (53, 55, 57),
    Role.ButtonText: (200, 203, 207),
    Role.BrightText: (255, 0, 0),
    Role.Highlight: (75, 110, 175),
    Role.HighlightedText: (0, 0, 0),
    Role.Light: (105, 108, 112),
    Role.Dark: (12, 12, 12),
}


# The default theme's status colors
_DEFAULT_STATUS_COLORS = {"green": (76, 175, 80), "yellow": (255, 193, 7), "red": (244, 67, 54)}
# The theme in use, by name and as a qt-themes theme (None for the default)
_name = None
_current = None


def default_palette():
    """ AutoSplit64++'s own palette """
    palette = QtGui.QPalette()
    for role, rgb in _DEFAULT_COLORS.items():
        palette.setColor(role, QtGui.QColor(*rgb))
    return palette


def themes():
    """ The themes' names, the default first """
    return [DEFAULT] + sorted(qt_themes.get_themes())


def status_color(name):
    """ The theme's "green", "yellow" or "red" """
    return QtGui.QColor(getattr(_current, name)) if _current else QtGui.QColor(*_DEFAULT_STATUS_COLORS[name])


def mix(color, other, amount):
    """ color, amount of the way to other """
    return QtGui.QColor(*(round(a + (b - a) * amount) for a, b in zip(color.getRgb()[:3], other.getRgb()[:3])))


def muted(palette):
    """ For less prominent text and icons: the text color, a third of the way to the background """
    return mix(palette.color(Role.Text), palette.color(Role.Base), 0.3)


def display_name(name):
    return name.replace("_", " ").title()


def current():
    """ The name of the theme in use """
    return _name


def apply(name):
    """ Use the theme, the default for one that doesn't exist. Widgets repaint once events are processed. """
    global _name, _current
    app = QtWidgets.QApplication.instance()
    _name = name
    # Before the palette, which makes the widgets repaint
    _current = qt_themes.get_themes().get(name)
    if _current:
        qt_themes.set_theme(name, style=None)
    else:
        app.setPalette(default_palette())
