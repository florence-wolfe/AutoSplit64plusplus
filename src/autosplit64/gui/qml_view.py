"""
Shows the app's QML, in gui/qml, in its widgets. The QML uses Qt Quick Controls' Material style.
"""
import os
from pathlib import Path

from PyQt6 import QtCore, QtQuick, QtQuickWidgets, QtWidgets

# Material's compact sizes. Read when the style is first loaded.
os.environ.setdefault("QT_QUICK_CONTROLS_MATERIAL_VARIANT", "Dense")

QML_DIR = Path(__file__).parent / "qml"


def _load(view, name, context):
    """
    Shows qml/<name>.qml in view, which reads context's values by their names. Its objects become the
    view's children: the view deletes its QML before its children, so the QML never sees them deleted.
    """
    for key, value in context.items():
        if isinstance(value, QtCore.QObject):
            value.setParent(view)
        view.rootContext().setContextProperty(key, value)
    view.setSource(QtCore.QUrl.fromLocalFile(str(QML_DIR / f"{name}.qml")))
    if view.errors():
        raise RuntimeError("\n".join(error.toString() for error in view.errors()))


def _fill(parent, widget):
    layout = QtWidgets.QVBoxLayout(parent)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.addWidget(widget)


def qml_view(parent, name, **context):
    """ Fills parent with a view of qml/<name>.qml, see _load() """
    view = QtQuickWidgets.QQuickWidget()
    view.setResizeMode(QtQuickWidgets.QQuickWidget.ResizeMode.SizeRootObjectToView)
    _load(view, name, context)
    _fill(parent, view)
    return view


def qml_window(parent, name, **context):
    """
    Like qml_view(), in a native window of its own inside parent: its popups can be windows too (Popup.Window),
    e.g. a menu taller than a small window. A QQuickWidget's are kept inside it.
    """
    view = QtQuick.QQuickView()
    view.setResizeMode(QtQuick.QQuickView.ResizeMode.SizeRootObjectToView)
    _load(view, name, context)
    _fill(parent, QtWidgets.QWidget.createWindowContainer(view, parent))
    return view
