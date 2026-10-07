from PyQt6 import QtCore, QtWidgets


def close_window(window):
    """
    Close a window and delete it now. Windows that delete themselves when closed are otherwise
    only deleted at exit, with the rest of Qt, in an order that can crash.
    """
    window.close()
    QtWidgets.QApplication.sendPostedEvents(None, QtCore.QEvent.Type.DeferredDelete)
