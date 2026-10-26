"""
The app's colors: a theme, which is a palette from qt-themes or AutoSplit64++'s own. Widgets take
their colors from the palette, or status_color() for green, yellow and red. Like the palettes,
the app uses the Fusion style.

The windows in QML use a Qt Quick Controls style too, which Qt takes when the first one opens, so a new style
needs a restart.
"""
import os
import sys
from pathlib import Path

from PyQt6 import QtCore, QtGui, QtWidgets

# qt-themes uses qtpy, which would otherwise look for PyQt5 first
os.environ.setdefault("QT_API", "pyqt6")
import qt_themes  # noqa: E402

# The default: AS64++ Dark or AS64++ Light, as the system is set to
SYSTEM = "as64_system"
DEFAULT = SYSTEM
# The palette the app had before its own themes, still named as it was in the settings
CLASSIC = "default"
# Where AutoSplit64++'s own Qt Quick Controls style is, a directory of QML named after it
STYLES_DIR = Path(__file__).parent / "qml" / "styles"
# The platforms' own Qt Quick Controls styles, whose controls take the system's accent color instead of the theme's
_PLATFORM_STYLES = {"darwin": ["macOS"], "win32": ["Windows", "FluentWinUI3"]}
SYSTEM_STYLES = {style for styles in _PLATFORM_STYLES.values() for style in styles}

Role = QtGui.QPalette.ColorRole


def _theme(**colors):
    """ A qt-themes theme from hex colors, like the ones its own files describe """
    return qt_themes.Theme(**{name: QtGui.QColor(color) for name, color in colors.items()})


# AutoSplit64++'s own themes, which qt-themes turns into a palette like the others: base is the window and its
# panels, mantle (crust in a light theme) the splits' ground, surface0 a raised row and surface1 a border
_OWN = {
    "as64_dark": _theme(
        primary="#f5b83d", secondary="#f5b83d",
        magenta="#e8567a", red="#f44336", orange="#ff9800", yellow="#ffc107", green="#4caf50", cyan="#4dd0e1",
        blue="#5b8def",
        text="#e6e8ec", subtext1="#c5c9d1", subtext0="#b0b5bf", overlay2="#9aa0ab", overlay1="#8a909b",
        overlay0="#5b616c", surface2="#3a3e47", surface1="#2c3038", surface0="#23262d",
        base="#191b20", mantle="#131418", crust="#0e0f12"),
    "as64_light": _theme(
        primary="#2f61cc", secondary="#2f61cc",
        magenta="#c2185b", red="#d32f2f", orange="#e65100", yellow="#f9a825", green="#2e8b4c", cyan="#00838f",
        blue="#2f61cc",
        text="#1c1f24", subtext1="#3a3f48", subtext0="#4a505b", overlay2="#575d68", overlay1="#6b717c",
        overlay0="#a9afba", surface2="#c5cad4", surface1="#d9dde5", surface0="#e8ebf1",
        base="#ffffff", mantle="#eef0f4", crust="#f4f5f8"),
}
_DISPLAY_NAMES = {SYSTEM: "AS64++ (System)", "as64_dark": "AS64++ Dark", "as64_light": "AS64++ Light", CLASSIC: "Classic"}
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
# Whether apply() listens for the system's light or dark changing
_watching = False


def styles():
    """
    The Qt Quick Controls styles there are on this platform, the default first: AutoSplit64++'s own, in STYLES_DIR.
    Not Basic, which draws with palette colors that most of the themes' dark palettes have the wrong way round, e.g.
    its switches' handles in `light`.
    """
    return ["AutoSplit64", "Material", "Fusion", "Universal"] + _PLATFORM_STYLES.get(sys.platform, [])


def use_style(name):
    """ The QML windows' style, before the first opens """
    os.environ["QT_QUICK_CONTROLS_STYLE"] = name if name in styles() else styles()[0]
    # Where Qt looks for a style that isn't one of its own
    paths = [path for path in os.environ.get("QML2_IMPORT_PATH", "").split(os.pathsep) if path]
    if str(STYLES_DIR) not in paths:
        os.environ["QML2_IMPORT_PATH"] = os.pathsep.join(paths + [str(STYLES_DIR)])


def default_palette():
    """ AutoSplit64++'s own palette """
    palette = QtGui.QPalette()
    for role, rgb in _DEFAULT_COLORS.items():
        palette.setColor(role, QtGui.QColor(*rgb))
    return palette


def themes():
    """ The themes' names, the default first, then AutoSplit64++'s own and the one it had before them """
    return [SYSTEM, *_OWN, CLASSIC] + sorted(qt_themes.get_themes())


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
    return _DISPLAY_NAMES.get(name) or name.replace("_", " ").title()


def current():
    """ The name of the theme in use """
    return _name


def system_dark():
    """ Whether the system is set to dark, which it's taken to be where it doesn't say """
    return QtGui.QGuiApplication.styleHints().colorScheme() != QtCore.Qt.ColorScheme.Light


def _follows_system(name):
    """ Whether the theme is the system's light or dark one: the default, also for a name that's no theme """
    return name == SYSTEM or name not in themes()


def _on_system_changed(*_):
    if _name is not None and _follows_system(_name):
        apply(_name)


def apply(name):
    """ Use the theme, the default for one that doesn't exist. Widgets repaint once events are processed. """
    global _name, _current, _watching
    app = QtWidgets.QApplication.instance()
    _name = name
    if not _watching:
        # The default changes with the system, also while the app is open
        QtGui.QGuiApplication.styleHints().colorSchemeChanged.connect(_on_system_changed)
        _watching = True
    drawn = ("as64_dark" if system_dark() else "as64_light") if _follows_system(name) else name
    # Before the palette, which makes the widgets repaint
    _current = _OWN.get(drawn) or qt_themes.get_themes().get(drawn)
    if _current:
        qt_themes.set_theme(_current, style=None)
    else:
        app.setPalette(default_palette())
