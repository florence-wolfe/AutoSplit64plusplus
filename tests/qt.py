import time

from PyQt6 import QtCore, QtWidgets, sip


def close_window(window):
    """
    Close a window and delete it now. Windows that delete themselves when closed are otherwise
    only deleted at exit, with the rest of Qt, in an order that can crash.
    """
    # A test may have closed it already
    if not sip.isdeleted(window):
        window.close()
    QtWidgets.QApplication.sendPostedEvents(None, QtCore.QEvent.Type.DeferredDelete)


def qml_items(view):
    """ The items in a qml_view(), by the items they're in: a Repeater's aren't its QObject children """
    items = [view.rootObject()]
    for item in items:
        items.extend(item.childItems())
    return items


def qml(view, name):
    """ The QML item with that objectName in a qml_view(), or popup: those aren't items """
    objects = qml_items(view) + view.rootObject().findChildren(QtCore.QObject)
    return next((item for item in objects if item.objectName() == name), None)


def wait_until(condition, timeout=2):
    """ Process events until condition() is true, e.g. once a QML transition ended, or timeout seconds passed """
    deadline = time.monotonic() + timeout
    while not condition() and time.monotonic() < deadline:
        QtWidgets.QApplication.processEvents()
        time.sleep(0.01)
