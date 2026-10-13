"""
Shows the app's QML, in gui/qml, in its widgets. The QML uses Qt Quick Controls' Material style.
"""
import os
from pathlib import Path

from PyQt6 import QtCore, QtQuickWidgets, QtWidgets

# Material's compact sizes. Read when the style is first loaded.
os.environ.setdefault("QT_QUICK_CONTROLS_MATERIAL_VARIANT", "Dense")

QML_DIR = Path(__file__).parent / "qml"


def qml_view(parent, name, **context):
    """
    Fills parent with a view of qml/<name>.qml, which reads context's values by their names. Its
    objects become the view's children: the view deletes its QML before its children, so the QML
    never sees them deleted.
    """
    view = QtQuickWidgets.QQuickWidget()
    view.setResizeMode(QtQuickWidgets.QQuickWidget.ResizeMode.SizeRootObjectToView)
    for key, value in context.items():
        if isinstance(value, QtCore.QObject):
            value.setParent(view)
        view.rootContext().setContextProperty(key, value)
    view.setSource(QtCore.QUrl.fromLocalFile(str(QML_DIR / f"{name}.qml")))
    if view.status() == QtQuickWidgets.QQuickWidget.Status.Error:
        raise RuntimeError("\n".join(error.toString() for error in view.errors()))

    layout = QtWidgets.QVBoxLayout(parent)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.addWidget(view)
    return view
