import time
from unittest import mock

from PyQt6 import QtCore, QtWidgets, sip

# The tests' QApplication, which widgets need before they're made, and Qt has only one of
qapp = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


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


def answering(choice, record=None):
    """ Answer message boxes by clicking the button with the given text """
    def exec_(box):
        if record is not None:
            record.append({b.text(): b.isEnabled() for b in box.buttons()})
        next(b for b in box.buttons() if b.text() == choice).click()
        return 0
    return mock.patch.object(QtWidgets.QMessageBox, "exec", exec_)
