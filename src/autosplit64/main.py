import sys
import os
from threading import Thread
import logging
from PyQt6 import QtCore, QtWidgets, QtGui
from autosplit64.gui.app import App
from autosplit64.gui.constants import FONT_PATH
from autosplit64 import core
from autosplit64.core.processing import register_process, ProcessorGenerator
from autosplit64.core.route_loader import load_or_none
from autosplit64.core import config, livesplit
from autosplit64.core.resource_utils import resource_path
from autosplit64.processes.standard import (
    ProcessDummy,
    ProcessFadein,
    ProcessFadeout,
    ProcessFadeoutNoStar,
    ProcessFadeoutResetOnly,
    ProcessFileSelectSplit,
    ProcessFlashCheck,
    ProcessPostFadeout,
    ProcessReset,
    ProcessRunStart,
    ProcessRunStartUpSegment,
    ProcessStarCount,
    ProcessWait,
)
from autosplit64.processes.xcam import ProcessXCam, ProcessXCamStartUpSegment
from autosplit64.processes.ddd import ProcessDDDEntry, ProcessDDDEntryX, ProcessFindDDDPortal
from autosplit64.processes.final import ProcessFinalStageEntry, ProcessFinalStarGrab, ProcessFinalStarSpawn

def route_timing():
    """ The configured route's timing, or None without a valid route """
    route = load_or_none(config.get("route", "path"))
    return route.timing if route else None


def timing_setup(timing):
    """ The initial processor for a route's timing, and whether a console reset restarts the timer """
    if timing == core.TIMING_UP_RTA:
        return "up_rta/initial_up_rta.processor", False
    if timing == core.TIMING_FILE_SELECT:
        return "file_select/initial_file_select_start.processor", False
    return "standard/initial.processor", True


def set_up_timing():
    """ Set up the configured route's timing, and return its initial processor """
    path, core.start_on_reset = timing_setup(route_timing())
    return ProcessorGenerator.generate(path)


class AutoSplit64(QtCore.QObject):
    error = QtCore.pyqtSignal(str)
    update_found = QtCore.pyqtSignal(dict)
    # Split detection reports from its own thread, and only the GUI thread may change widgets
    started_changed = QtCore.pyqtSignal(bool)
    display_updated = QtCore.pyqtSignal(object, object, object)

    def __init__(self, parent=None):
        super().__init__(parent=parent)

        # Initialize GUI
        self.app = App()

        # Connections
        self.app.start.connect(lambda: Thread(target=self.start).start())
        self.app.stop.connect(self.stop)
        self.app.destroyed.connect(lambda: self.stop())
        self.error.connect(self.app.display_error_message)
        self.started_changed.connect(self.app.set_started)
        self.display_updated.connect(self.app.update_display)

        # Start the LiveSplit One server so LiveSplit One can connect before a run is started
        if config.get("connection", "ls_connection_type") == 2:
            livesplit.connect()

    def start(self):
        core.init()
        
        
        if not os.path.exists(resource_path(config.get("advanced", "reset_frame_one"))) or not os.path.exists(resource_path(config.get("advanced", "reset_frame_two"))):
            self.on_error("Reset template files are missing!\n\nPlease generate reset templates first.")
            return

        register_process("WAIT", ProcessWait())
        register_process("RUN_START", ProcessRunStart())
        register_process("RUN_START_UP_RTA", ProcessRunStartUpSegment())
        register_process("STAR_COUNT", ProcessStarCount())
        register_process("FADEIN", ProcessFadein())
        register_process("FADEOUT", ProcessFadeout())
        register_process("FADEOUT_NO_STAR", ProcessFadeoutNoStar())
        register_process("FADEOUT_RESET_ONLY", ProcessFadeoutResetOnly())
        register_process("POST_FADEOUT", ProcessPostFadeout())
        register_process("FLASH_CHECK", ProcessFlashCheck())
        register_process("RESET", ProcessReset())
        register_process("DUMMY", ProcessDummy())

        register_process("XCAM", ProcessXCam())
        register_process("XCAM_UP_RTA", ProcessXCamStartUpSegment())

        register_process("FILE_SELECT_SPLIT", ProcessFileSelectSplit())

        register_process("FIND_DDD_PORTAL", ProcessFindDDDPortal())
        register_process("DDD_SPLIT", ProcessDDDEntry())  # TODO: RENAME ProcessDDDEntry to ProcessDDDSplit
        register_process("DDD_SPLIT_X", ProcessDDDEntryX())  # TODO: RENAME ProcessDDDEntryX to ProcessDDDSplitX

        register_process("FINAL_DETECT_ENTRY", ProcessFinalStageEntry())  # TODO: RENAME
        register_process("FINAL_DETECT_SPAWN", ProcessFinalStarSpawn())  # TODO: RENAME
        register_process("FINAL_STAR_SPLIT", ProcessFinalStarGrab())  # TODO: RENAME to FINAL_STAR_SPLIT

        initial_processor = set_up_timing()

        standard_processor = ProcessorGenerator.generate("standard/star_fade.processor")
        fade_only_processor = ProcessorGenerator.generate("standard/fade_only.processor")
        xcam_processor = ProcessorGenerator.generate("standard/xcam_split.processor")
        ddd_processor = ProcessorGenerator.generate("ddd/ddd.processor")
        mips_x_processor = ProcessorGenerator.generate("ddd/mips_x.processor")
        final_processor = ProcessorGenerator.generate("final/final.processor")

        core.register_split_processor(core.SPLIT_INITIAL, initial_processor)
        core.register_split_processor(core.SPLIT_NORMAL, standard_processor)
        core.register_split_processor(core.SPLIT_FADE_ONLY, fade_only_processor)
        core.register_split_processor(core.SPLIT_MIPS, ddd_processor)
        core.register_split_processor(core.SPLIT_MIPS_X, mips_x_processor)
        core.register_split_processor(core.SPLIT_FINAL, final_processor)
        core.register_split_processor(core.SPLIT_XCAM, xcam_processor)

        core.set_update_listener(self.on_update)
        core.set_error_listener(self.on_error)
        core.set_start_listener(self.on_start)

        core.start()

    def stop(self):
        core.stop()

    def on_start(self):
        self.started_changed.emit(True)

    def on_update(self, index, star_count, split_star):
        self.display_updated.emit(index, star_count, split_star)

    def on_error(self, error):
        self.error.emit(error)
        self.started_changed.emit(False)

    def exit(self):
        self.stop()
        self.app.close()


def main():
    # Create QT Application
    qt_app = QtWidgets.QApplication(sys.argv)

    # Configure QT Application Style
    qt_app.setStyle('Fusion')

    palette = QtGui.QPalette()
    palette.setColor(QtGui.QPalette.ColorRole.Window, QtGui.QColor(60, 63, 65))
    palette.setColor(QtGui.QPalette.ColorRole.WindowText, QtGui.QColor(200, 203, 207))
    palette.setColor(QtGui.QPalette.ColorRole.Link, QtGui.QColor(88, 157, 246))
    palette.setColor(QtGui.QPalette.ColorRole.Base, QtGui.QColor(23, 25, 27))
    palette.setColor(QtGui.QPalette.ColorRole.AlternateBase, QtGui.QColor(53, 55, 57))
    palette.setColor(QtGui.QPalette.ColorRole.ToolTipBase, QtGui.QColor(53, 55, 57))
    palette.setColor(QtGui.QPalette.ColorRole.ToolTipText, QtGui.QColor(255, 255, 255))
    palette.setColor(QtGui.QPalette.ColorRole.Text, QtGui.QColor(200, 203, 207))
    palette.setColor(QtGui.QPalette.ColorRole.Button, QtGui.QColor(53, 55, 57))
    palette.setColor(QtGui.QPalette.ColorRole.ButtonText, QtGui.QColor(200, 203, 207))
    palette.setColor(QtGui.QPalette.ColorRole.BrightText, QtGui.QColor(255, 0, 0))
    palette.setColor(QtGui.QPalette.ColorRole.Highlight, QtGui.QColor(75, 110, 175))
    palette.setColor(QtGui.QPalette.ColorRole.HighlightedText, QtGui.QColor(0, 0, 0))
    palette.setColor(QtGui.QPalette.ColorRole.Light, QtGui.QColor(105, 108, 112))
    palette.setColor(QtGui.QPalette.ColorRole.Dark, QtGui.QColor(12, 12, 12))

    qt_app.setPalette(palette)

    # Add font to database
    QtGui.QFontDatabase.addApplicationFont(FONT_PATH)

    logging.basicConfig(
        level=logging.WARNING,
        format='%(asctime)s:%(levelname)s:%(name)s:%(message)s',
        filename=".log",
        filemode='a'
    )

    # Create main application
    autosplit64 = AutoSplit64(qt_app)

    # Exit
    sys.exit(qt_app.exec())
