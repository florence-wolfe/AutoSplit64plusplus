import contextlib
import logging
import threading
import uuid
import shutil
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from PyQt6 import QtCore, QtGui, QtWidgets

from autosplit64.core import config, logs
from autosplit64.core.model import PredictionInfo
from autosplit64.gui.dialogs import debug_dialog
from autosplit64.gui.dialogs.debug_dialog import DebugDialog, describe
from PyQt6.QtTest import QTest

from tests.qt import qml, run_queued, wait_until

OUTPUT = {"fade_status": "FADEOUT_PARTIAL", "fadeout_count": 2, "fadein_count": 1, "xcam_percent": 0.123456789,
          "xcam_count": 3, "xcam_status": True, "prediction": 16, "probability": 0.987654321, "execution": 0.0123456,
          "status": None, "livesplit": "LiveSplit connected"}

STATUS = {"running": True, "in_game": True, "split_index": 2, "split_count": 12, "split": "CCM 8", "split_type": "Normal",
          "needs_stars": 8, "needs_fadeouts": 1, "needs_fadeins": 0, "needs_xcams": -1,
          "stars": 7, "fadeouts": 0, "fadeins": 1, "xcams": 0}


class DescribeTest(unittest.TestCase):
    """ What split detection is doing, in words """

    def test_in_a_run(self):
        self.assertEqual(describe(STATUS, "LiveSplit connected"), (
            "Running, in a run · LiveSplit connected", "Split 3 of 12: CCM 8",
            "8 stars · fadeout 1 · fade-in 0", "7 stars · fadeouts 0 · fade-ins 1"))

    def test_waiting_for_a_run(self):
        status = dict(STATUS, in_game=False)
        self.assertEqual(describe(status, "LiveSplit connected")[0], "Running, waiting for a run · LiveSplit connected")

    def test_not_running(self):
        for status in (None, dict(STATUS, running=False), {"running": False, "in_game": False}):
            with self.subTest(status):
                self.assertEqual(describe(status, "LiveSplit not connected"), ("Not running · LiveSplit not connected", "", "", ""))

    def test_one_star(self):
        self.assertEqual(describe(dict(STATUS, needs_stars=1, stars=1), "")[2:], ("1 star · fadeout 1 · fade-in 0", "1 star · fadeouts 0 · fade-ins 1"))

    def test_what_each_split_type_needs(self):
        for split_type, needs, counted in [
                ("Fade", "fadeout 1 · fade-in 0", "7 stars · fadeouts 0 · fade-ins 1"),
                ("X-Cam", "8 stars · fadeout 1 · fade-in 0 · X-Cam 2", "7 stars · fadeouts 0 · fade-ins 1 · X-Cams 1"),
                ("Mips", "entering the DDD painting", "7 stars · fadeouts 0 · fade-ins 1"),
                ("Mips-X", "an X-Cam at the DDD painting", "7 stars · X-Cams 1"),
                ("Final", "grabbing the Grand Star", "7 stars · fadeouts 0 · fade-ins 1")]:
            with self.subTest(split_type):
                status = dict(STATUS, split_type=split_type, needs_xcams=2, xcams=1)
                self.assertEqual(describe(status, "")[2:], (needs, counted))


class DebugDialogTest(unittest.TestCase):
    def setUp(self):
        for patcher in [mock.patch.object(config, "_config", {"general": {"output_update_rate": 10}}),
                        mock.patch.object(config, "save_config")]:
            patcher.start()
            self.addCleanup(patcher.stop)
        self.dialog = DebugDialog()
        self.addCleanup(self.dialog.deleteLater)

    def qml(self, name):
        return qml(self.dialog.view, name)

    def text(self, name):
        return self.qml(name).property("text")

    def click(self, name):
        QtCore.QMetaObject.invokeMethod(self.qml(name), "clicked")

    def set_update_rate(self, rate):
        """ Like typing it in the spin box """
        spin_box = self.qml("updateRate")
        spin_box.setProperty("value", rate)
        QtCore.QMetaObject.invokeMethod(spin_box, "valueModified")

    def scene_box(self, name):
        item = self.qml(name)
        origin = item.mapToScene(QtCore.QPointF(0, 0))
        return origin.y(), origin.y() + item.height()

    def test_the_buttons_have_space_between_them(self):
        QtWidgets.QDialog.show(self.dialog)
        self.addCleanup(self.dialog.hide)
        run_queued()
        logs, old = self.scene_box("openLog"), self.scene_box("openOldLog")
        save = self.scene_box("saveInfo")
        self.assertEqual(logs, old)
        self.assertGreaterEqual(save[0] - logs[1], 6)

    def drag_grip(self, dy):
        grip = self.qml("eventsGrip")
        start = grip.mapToScene(QtCore.QPointF(grip.width() / 2, grip.height() / 2)).toPoint()
        left, none = QtCore.Qt.MouseButton.LeftButton, QtCore.Qt.KeyboardModifier.NoModifier
        QTest.mousePress(self.dialog.view, left, none, start)
        for step in range(1, 11):
            QTest.mouseMove(self.dialog.view, start + QtCore.QPoint(0, dy * step // 10))
        QTest.mouseRelease(self.dialog.view, left, none, start + QtCore.QPoint(0, dy))
        run_queued()
        wait_until(lambda: False, timeout=0.15)

    def test_dragging_the_grip_resizes_the_recent_events_and_the_window_with_them(self):
        self.dialog.resize(360, 600)
        QtWidgets.QDialog.show(self.dialog)
        self.addCleanup(self.dialog.hide)
        run_queued()
        box, window = self.qml("eventsBox").height(), self.dialog.height()
        self.drag_grip(60)
        self.assertAlmostEqual(self.qml("eventsBox").height(), box + 60, delta=3)
        self.assertAlmostEqual(self.dialog.height(), window + 60, delta=3)
        self.drag_grip(-40)
        self.assertAlmostEqual(self.qml("eventsBox").height(), box + 20, delta=3)
        self.assertAlmostEqual(self.dialog.height(), window + 20, delta=3)

    def test_the_recent_events_stay_at_least_a_few_lines_tall(self):
        self.dialog.resize(360, 600)
        QtWidgets.QDialog.show(self.dialog)
        self.addCleanup(self.dialog.hide)
        run_queued()
        self.drag_grip(-2000)
        self.assertGreaterEqual(self.qml("eventsBox").height(), 79)
        self.assertGreaterEqual(self.dialog.height(), self.dialog.minimumHeight())

    def test_shows_the_output_in_advanced(self):
        self.dialog.display_output(OUTPUT)
        keys = ["fade_status", "fadeout_count", "fadein_count", "xcam_percent", "xcam_count", "xcam_status",
                "prediction", "probability", "execution"]
        self.assertEqual({key: self.text(key) for key in keys}, {
            "fade_status": "FADEOUT_PARTIAL", "fadeout_count": "2", "fadein_count": "1",
            "xcam_percent": "0.1234", "xcam_count": "3", "xcam_status": "True",
            "prediction": "16", "probability": "0.9876", "execution": "0.0123"})

    def test_changing_the_update_rate_saves_it(self):
        self.dialog.output_reader = SimpleNamespace(update_rate=10)
        self.set_update_rate(25)
        self.assertEqual(self.dialog.output_reader.update_rate, 25)
        self.assertEqual(config.get("general", "output_update_rate"), 25)
        config.save_config.assert_called_once()

    def test_what_split_detection_is_doing(self):
        self.dialog.display_output(dict(OUTPUT, status=STATUS))
        self.assertEqual(tuple(self.text(name) for name in ("status", "split", "needs", "counted")),
                         describe(STATUS, "LiveSplit connected"))

    def test_only_the_status_while_not_running(self):
        self.dialog.display_output(dict(OUTPUT, status=None))
        self.assertTrue(self.qml("status").property("visible"))
        for name in ("split", "progress"):
            self.assertFalse(self.qml(name).property("visible"))
        self.dialog.display_output(dict(OUTPUT, status=STATUS))
        for name in ("split", "progress"):
            self.assertTrue(self.qml(name).property("visible"))

    def test_advanced_is_collapsed_at_first(self):
        self.assertFalse(self.qml("advanced").property("visible"))
        self.click("advancedButton")
        self.assertTrue(self.qml("advanced").property("visible"))
        self.assertIs(config.get("general", "debug_advanced"), True)
        config.save_config.assert_called_once()

    def test_advanced_stays_open(self):
        config.set_key("general", "debug_advanced", True)
        again = DebugDialog()
        self.addCleanup(again.deleteLater)
        self.assertTrue(qml(again.view, "advanced").property("visible"))

    def test_showing_advanced_makes_the_window_tall_enough(self):
        self.dialog.resize(360, 200)
        self.click("advancedButton")
        QtWidgets.QApplication.processEvents()
        self.assertGreaterEqual(self.dialog.height(), self.dialog.view.rootObject().property("implicitHeight"))

    def test_title_and_resizable(self):
        self.assertEqual(self.dialog.windowTitle(), "Debug")
        self.assertLess(self.dialog.minimumSize().width(), self.dialog.maximumSize().width())
        self.assertLess(self.dialog.minimumSize().height(), self.dialog.maximumSize().height())

    def test_remembers_its_size(self):
        self.dialog.show()
        self.dialog.resize(420, 610)
        self.dialog.close()
        self.assertEqual(config.get("general", "debug_window_size"), [420, 610])
        again = DebugDialog()
        self.addCleanup(again.deleteLater)
        self.assertEqual((again.width(), again.height()), (420, 610))

    def test_opens_the_logs_in_the_text_editor(self):
        with mock.patch.object(QtGui.QDesktopServices, "openUrl") as open_url:
            self.click("openLog")
        self.assertEqual(open_url.call_args.args[0], QtCore.QUrl.fromLocalFile(str(Path(logs.LOG_FILE).absolute())))

    def test_previous_log_only_when_there_is_one(self):
        directory = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, directory)
        with contextlib.chdir(directory):
            self.dialog.update_log_buttons()
            self.assertFalse(self.qml("openOldLog").property("enabled"))
            Path(logs.OLD_LOG_FILE).write_text("previous session")
            self.dialog.update_log_buttons()
            self.assertTrue(self.qml("openOldLog").property("enabled"))
            with mock.patch.object(QtGui.QDesktopServices, "openUrl") as open_url:
                self.click("openOldLog")
            self.assertEqual(open_url.call_args.args[0], QtCore.QUrl.fromLocalFile(str(Path(logs.OLD_LOG_FILE).absolute())))

    def test_save_debug_info(self):
        saved = mock.Mock()
        self.dialog.save_debug_info.connect(saved)
        self.click("saveInfo")
        saved.assert_called_once()

    def test_update_rate_is_explained(self):
        self.assertIn("times a second", self.text("updateRateHelp"))
        self.assertIn("Split detection itself isn't affected", self.text("updateRateHelp"))

    def test_update_rate_is_1_to_30(self):
        spin_box = self.qml("updateRate")
        self.assertEqual((spin_box.property("from"), spin_box.property("to")), (1, 30))

    def test_saved_update_rate_of_0_is_1(self):
        # Allowed before, which divided by zero in the thread
        config.set_key("general", "output_update_rate", 0)
        self.dialog.show()
        self.addCleanup(self.dialog.close)
        self.assertEqual(self.dialog.output_reader.update_rate, 1)
        self.assertEqual(self.qml("updateRate").property("value"), 1)

    def test_reopening_shows_the_changed_update_rate(self):
        self.dialog.show()
        self.set_update_rate(25)
        self.dialog.close()
        self.dialog.show()
        self.addCleanup(self.dialog.close)
        self.assertEqual(self.qml("updateRate").property("value"), 25)

    def test_closing_stops_the_output_reader(self):
        # Deleting the window while its thread runs would abort AutoSplit64++
        config.set_key("general", "output_update_rate", 1)
        self.dialog.show()
        reader = self.dialog.output_reader
        self.dialog.close()
        self.assertTrue(reader.isFinished())

    def test_closing_before_it_was_shown(self):
        # The main window closes it when quitting, also when it was never shown. An exception in
        # closeEvent would abort the app, so it's called directly here to fail the test instead.
        self.dialog.closeEvent(QtGui.QCloseEvent())
        self.dialog.hide()
        # Which doesn't change the settings
        config.save_config.assert_not_called()


class OutputReaderTest(unittest.TestCase):
    """ What the Debug window shows, read from the split detection that started last """

    def setUp(self):
        for patcher in [mock.patch.object(config, "_config", {"general": {"output_update_rate": 10}}),
                        mock.patch.object(debug_dialog, "livesplit_state", return_value="LiveSplit connected")]:
            patcher.start()
            self.addCleanup(patcher.stop)

    def read(self, detection):
        """ The reader's first output """
        reader = debug_dialog.OutputReader(lambda: detection)
        self.addCleanup(reader.deleteLater)
        outputs = []
        reader.output.connect(lambda output: (outputs.append(output), reader.stop()))
        reader.run()
        return outputs[0]

    def test_before_split_detection_starts(self):
        self.assertEqual(self.read(None), {
            "fade_status": "NO_FADE", "fadeout_count": 0, "fadein_count": 0, "xcam_percent": 0.0, "xcam_count": 0,
            "xcam_status": False, "prediction": None, "probability": None, "execution": 0.0, "status": None,
            "livesplit": "LiveSplit connected"})

    def test_from_split_detection(self):
        detection = SimpleNamespace(fade_status="FADEOUT_PARTIAL", fadeout_count=2, fadein_count=1, xcam_percent=0.5,
                                    xcam_count=3, in_xcam=True, prediction_info=PredictionInfo(16, 0.9),
                                    execution_time=0.01, status=lambda: STATUS)
        self.assertEqual(self.read(detection), {
            "fade_status": "FADEOUT_PARTIAL", "fadeout_count": 2, "fadein_count": 1, "xcam_percent": 0.5,
            "xcam_count": 3, "xcam_status": True, "prediction": 16, "probability": 0.9, "execution": 0.01,
            "status": STATUS, "livesplit": "LiveSplit connected"})


class RecentEventsTest(unittest.TestCase):
    """ This session's last detection log lines, in the Debug window """

    def setUp(self):
        for patcher in [mock.patch.object(config, "_config", {"general": {"output_update_rate": 10}}),
                        mock.patch.object(config, "save_config")]:
            patcher.start()
            self.addCleanup(patcher.stop)
        self.dialog = DebugDialog()
        self.addCleanup(self.dialog.deleteLater)

    def log(self, text=None):
        """ Log a detection line, which is unique, and return it """
        text = text or f"Split: {uuid.uuid4()}"
        logging.getLogger("detection").info(text)
        return text

    def lines(self, dialog=None):
        model = qml((dialog or self.dialog).view, "lines")
        role = next(role for role, name in model.roleNames().items() if name == b"line")
        return [model.data(model.index(row, 0), role) for row in range(model.rowCount())]

    def test_new_lines_with_their_time(self):
        text = self.log()
        last = self.lines()[-1]
        self.assertTrue(last.endswith(" " + text))
        self.assertRegex(last, r"^\d\d:\d\d:\d\d ")

    def test_lines_from_split_detection_thread(self):
        text = f"Fadeout 1: {uuid.uuid4()}"
        thread = threading.Thread(target=self.log, args=(text,))
        thread.start()
        thread.join()
        # They arrive through the GUI thread
        QtWidgets.QApplication.processEvents()
        self.assertTrue(self.lines()[-1].endswith(text))

    def test_lines_from_before_the_window_was_made(self):
        text = self.log()
        again = DebugDialog()
        self.addCleanup(again.deleteLater)
        self.assertTrue(self.lines(again)[-1].endswith(text))

    def test_the_last_lines_only(self):
        texts = [self.log() for _ in range(debug_dialog.DetectionEvents.MAX + 10)]
        again = DebugDialog()
        self.addCleanup(again.deleteLater)
        for dialog in (self.dialog, again):
            lines = self.lines(dialog)
            self.assertEqual(len(lines), debug_dialog.DetectionEvents.MAX)
            self.assertTrue(lines[-1].endswith(texts[-1]))
            self.assertTrue(lines[0].endswith(texts[10]))

    def test_reading_further_up_stays_there(self):
        # Wrapping, as with Windows' wider font: then ListView estimates the lines' heights
        for i in range(50):
            self.log(f"Split: {uuid.uuid4()}" + (" and a longer explanation of what split detection did" * (1 + i % 2)))
        events = qml(self.dialog.view, "events")
        self.dialog.show()
        self.addCleanup(self.dialog.close)
        # Laid out and following the latest, as when it's read: one processEvents() isn't always enough, e.g. on Windows
        wait_until(lambda: 0 < events.height() < events.property("contentHeight") and events.property("atYEnd"))
        QtCore.QMetaObject.invokeMethod(events, "positionViewAtBeginning")
        self.log()
        self.assertTrue(events.property("atYBeginning"), self.scrolled(events))
        QtCore.QMetaObject.invokeMethod(events, "positionViewAtEnd")
        self.log()
        self.assertTrue(events.property("atYEnd"), self.scrolled(events))

    @staticmethod
    def scrolled(events):
        """ Where the list is scrolled, for a failure """
        return {name: events.property(name) for name in ("contentY", "originY", "contentHeight", "height", "count", "following")}


if __name__ == "__main__":
    unittest.main()
