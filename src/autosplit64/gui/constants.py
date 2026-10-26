from ..core.constants import DATA_DIR

try:
    # Written by build.py from the release's git tag
    from ._version import VERSION
except ImportError:
    VERSION = "dev"
TITLE = "AutoSplit64++"
AUTHOR = "Flo Wolfe\nDavi Be\nSynozure"

GITHUB_REPO = "florence-wolfe/AutoSplit64plusplus"

WIDTH = 460
HEIGHT = 330

FONT_PATH = str(DATA_DIR / "font" / "InterVariable.ttf")
ICON_PATH = "resources/gui/icons/as64plus.png"
ROUTES_DIR = "routes"
PLACEHOLDER_PATH = "resources/gui/obs_error.png"


