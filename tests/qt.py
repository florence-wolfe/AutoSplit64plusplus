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
