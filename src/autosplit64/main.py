import logging
import sys
import os
import threading
from pathlib import Path
from threading import Thread
from PyQt6 import QtCore, QtWidgets, QtGui
from autosplit64.gui import theme
from autosplit64.gui.app import App
from autosplit64.gui.constants import FONT_PATH, VERSION
from autosplit64 import core
from autosplit64.core.constants import (
    SPLIT_FADE_ONLY,
    SPLIT_FINAL,
    SPLIT_INITIAL,
    SPLIT_MIPS,
    SPLIT_MIPS_X,
    SPLIT_NORMAL,
    SPLIT_XCAM,
    TIMING_FILE_SELECT,
    TIMING_UP_RTA,
)
from autosplit64.core.processing import register_process, ProcessorGenerator
from autosplit64.core.route_loader import load_or_none
from autosplit64.core import config, livesplit, logs
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
from autosplit64.processes.ddd import ProcessDDDSplit, ProcessDDDSplitX, ProcessFindDDDPortal
from autosplit64.processes.final import ProcessFindFinalStage, ProcessFinalStarSplit, ProcessFindFinalStar

def route_timing():
    """ The configured route's timing, or None without a valid route """
    route = load_or_none(config.get("route", "path"))
    return route.timing if route else None


def timing_setup(timing):
    """ The initial processor for a route's timing, and whether a console reset restarts the timer """
    if timing == TIMING_UP_RTA:
        return "up_rta/initial_up_rta.processor", False
    if timing == TIMING_FILE_SELECT:
        return "file_select/initial_file_select_start.processor", False
    return "standard/initial.processor", True


def set_up_timing():
    """ Set up the configured route's timing, and return its initial processor's file """
    path, core.start_on_reset = timing_setup(route_timing())
    return path


def register_processes(detection):
    """ Register the processes, which run in detection, the Base that started """
    register_process("WAIT", ProcessWait(detection))
    register_process("RUN_START", ProcessRunStart(detection))
    register_process("RUN_START_UP_RTA", ProcessRunStartUpSegment(detection))
    register_process("STAR_COUNT", ProcessStarCount(detection))
    register_process("FADEIN", ProcessFadein(detection))
    register_process("FADEOUT", ProcessFadeout(detection))
    register_process("FADEOUT_NO_STAR", ProcessFadeoutNoStar(detection))
    register_process("FADEOUT_RESET_ONLY", ProcessFadeoutResetOnly(detection))
    register_process("POST_FADEOUT", ProcessPostFadeout(detection))
    register_process("FLASH_CHECK", ProcessFlashCheck(detection))
    register_process("RESET", ProcessReset(detection))
    register_process("DUMMY", ProcessDummy(detection))

    register_process("XCAM", ProcessXCam(detection))
    register_process("XCAM_UP_RTA", ProcessXCamStartUpSegment(detection))

    register_process("FILE_SELECT_SPLIT", ProcessFileSelectSplit(detection))

    register_process("FIND_DDD_PORTAL", ProcessFindDDDPortal(detection))
    register_process("DDD_SPLIT", ProcessDDDSplit(detection))
    register_process("DDD_SPLIT_X", ProcessDDDSplitX(detection))

    register_process("FIND_FINAL_STAGE", ProcessFindFinalStage(detection))
    register_process("FIND_FINAL_STAR", ProcessFindFinalStar(detection))
    register_process("FINAL_STAR_SPLIT", ProcessFinalStarSplit(detection))


def register_split_processors():
    """ Register each split type's processor, returning the file of one that failed to generate, or None """
    processor_paths = {
        SPLIT_INITIAL: set_up_timing(),
        SPLIT_NORMAL: "standard/star_fade.processor",
        SPLIT_FADE_ONLY: "standard/fade_only.processor",
        SPLIT_XCAM: "standard/xcam_split.processor",
        SPLIT_MIPS: "ddd/ddd.processor",
        SPLIT_MIPS_X: "ddd/mips_x.processor",
        SPLIT_FINAL: "final/final.processor",
    }
    for split_type, path in processor_paths.items():
        processor = ProcessorGenerator.generate(path)
        if processor is None:
            return path
        core.register_split_processor(split_type, processor)
    return None


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

        register_processes(core._base)

        failed = register_split_processors()
        # Without it, splits of this type would never happen
        if failed:
            self.on_error(f"Unable to load the split detection logic {failed}.\n\nSee the log for details.")
            return

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


# Whether this session showed a message about an error already
_shown_error = False


def show_error(error):
    """
    Tell about the first error nothing else handled in this session, whose details are in the log. Only the GUI
    thread may show windows, so errors in other threads are only logged.
    """
    global _shown_error
    if _shown_error or threading.current_thread() is not threading.main_thread() or not QtWidgets.QApplication.instance():
        return
    _shown_error = True
    QtWidgets.QMessageBox.critical(
        None, "AutoSplit64++",
        f"Something went wrong: {error}\n\nWhat happened is in the log, {Path(logs.LOG_FILE).absolute()}. "
        "Please send it with a bug report. More errors in this session are only in the log.")


def tell_about_previous_crash():
    """ The log of a crash is the old log now, until AutoSplit64++ starts again """
    if logs.previous_session_crashed():
        logging.getLogger(".log").warning("The previous session crashed, see %s", logs.OLD_LOG_FILE)
        QtWidgets.QMessageBox.warning(
            None, "AutoSplit64++",
            f"AutoSplit64++ quit unexpectedly last time. What happened is in {Path(logs.OLD_LOG_FILE).absolute()}. "
            "Please send it with a bug report before starting AutoSplit64++ again, which replaces it.")


def main():
    # First, so the log has everything that goes wrong
    handler = logs.start_session(VERSION)
    logs.install_crash_handlers(handler, show_error)

    # Create QT Application
    qt_app = QtWidgets.QApplication(sys.argv)

    qt_app.setStyle("Fusion")
    theme.apply(config.get("general", "theme"))

    # Add font to database
    QtGui.QFontDatabase.addApplicationFont(FONT_PATH)

    # Create main application
    autosplit64 = AutoSplit64(qt_app)
    tell_about_previous_crash()

    # Exit
    sys.exit(qt_app.exec())
