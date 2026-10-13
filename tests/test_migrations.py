""" Settings changes between releases, up and back down: see core/migrations.py """
import copy
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from PyQt6 import QtWidgets

from autosplit64.core import config, migrations
from autosplit64.gui.dialogs.settings_changes_dialog import SettingsChangesDialog
from tests.qt import close_window, qml, qml_items

_app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

THRESHOLD = {"set": ["thresholds", "reset_threshold"], "from": 0.1, "to": 0.3, "name": "Reset Threshold",
             "reason": "Catches more resets."}
MOVE = {"move": [["general", "old_name"], ["advanced", "new_name"]]}
RENAME_THEME = {"set": ["general", "theme"], "from": "Dark", "to": "Night"}

# Settings from a release before migrations
OLD = {"general": {"theme": "Dark", "old_name": 5}, "thresholds": {"reset_threshold": 0.1}}


def releases(*versions):
    """ MIGRATIONS of a release that knows these versions' changes """
    steps = {"0.6.0": [THRESHOLD], "0.7.0": [MOVE, RENAME_THEME], "0.7.0-fork": [RENAME_THEME]}
    return mock.patch.object(migrations, "MIGRATIONS", [(version, steps[version]) for version in versions])


def migrated(data, *versions, choose=None):
    data = copy.deepcopy(data)
    with releases(*versions):
        migrations.migrate(data, choose)
    return data


def without_record(data):
    return {section: values for section, values in data.items() if section != migrations.KEY}


class UpgradeTest(unittest.TestCase):
    def test_applies_each_release_in_order(self):
        data = migrated(OLD, "0.6.0", "0.7.0")
        self.assertEqual(without_record(data), {"general": {"theme": "Night"}, "advanced": {"new_name": 5},
                                                "thresholds": {"reset_threshold": 0.3}})
        self.assertEqual([record["version"] for record in data[migrations.KEY]], ["0.6.0", "0.7.0"])

    def test_offers_a_changed_default(self):
        offered = []
        migrated(OLD, "0.6.0", choose=lambda steps: offered.extend(steps) or steps)
        self.assertEqual(offered, [THRESHOLD])

    def test_keeps_an_offered_change_that_isnt_chosen(self):
        data = migrated(OLD, "0.6.0", choose=lambda steps: [])
        self.assertEqual(data["thresholds"]["reset_threshold"], 0.1)
        # Done with, so it isn't offered again
        self.assertEqual(data[migrations.KEY], [{"version": "0.6.0", "down": []}])

    def test_doesnt_offer_to_change_a_value_the_runner_chose(self):
        choose = mock.Mock()
        data = migrated({"thresholds": {"reset_threshold": 0.2}}, "0.6.0", choose=choose)
        choose.assert_not_called()
        self.assertEqual(data["thresholds"]["reset_threshold"], 0.2)

    def test_nothing_to_do_once_migrated(self):
        data = migrated(OLD, "0.6.0")
        with releases("0.6.0"):
            self.assertFalse(migrations.migrate(data, mock.Mock(side_effect=AssertionError)))


class DowngradeTest(unittest.TestCase):
    def test_an_earlier_release_undoes_what_it_doesnt_know(self):
        # Without the later release's code: only what the settings recorded
        data = migrated(migrated(OLD, "0.6.0", "0.7.0"), "0.6.0")
        self.assertEqual(data, migrated(OLD, "0.6.0"))

    def test_back_to_before_migrations(self):
        self.assertEqual(without_record(migrated(migrated(OLD, "0.6.0", "0.7.0"))), OLD)

    def test_keeps_what_changed_since(self):
        data = migrated(OLD, "0.6.0", "0.7.0")
        data["advanced"]["new_name"] = 8
        data["general"]["theme"] = "Light"
        data = migrated(data, "0.6.0")
        self.assertEqual(data["general"], {"theme": "Light", "old_name": 8})

    def test_up_again_after_going_down(self):
        data = migrated(migrated(migrated(OLD, "0.6.0", "0.7.0"), "0.6.0"), "0.6.0", "0.7.0")
        self.assertEqual(data, migrated(OLD, "0.6.0", "0.7.0"))

    def test_another_line_of_releases(self):
        # Settings from a fork's 0.7.0: its changes are undone before this 0.7.0's apply
        data = migrated(migrated(OLD, "0.6.0", "0.7.0-fork"), "0.6.0", "0.7.0")
        self.assertEqual(data, migrated(OLD, "0.6.0", "0.7.0"))


class NewSettingsTest(unittest.TestCase):
    def test_new_settings_can_go_back_down(self):
        data = {"general": {"theme": "Night"}, "advanced": {"new_name": 5}, "thresholds": {"reset_threshold": 0.3}}
        with releases("0.6.0", "0.7.0"):
            migrations.stamp(data)
        self.assertEqual(without_record(migrated(data)), OLD)


class LoadConfigTest(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.path = os.path.join(directory.name, "config.ini")
        defaults = os.path.join(directory.name, "defaults.ini")
        with open(defaults, "w") as file:
            # load_defaults sets the connection type outside Windows
            json.dump(without_record(migrated(OLD, "0.6.0")) | {"connection": {}}, file)
        for patcher in (mock.patch.object(config, "_CONFIG_FILE_NAME", self.path),
                        mock.patch.object(config, "_DEFAULTS_FILE_NAME", defaults),
                        mock.patch.object(config, "_config", {}), mock.patch.object(config, "_defaults", None),
                        releases("0.6.0")):
            patcher.start()
            self.addCleanup(patcher.stop)

    def saved(self):
        with open(self.path) as file:
            return json.load(file)

    def test_saves_migrated_settings(self):
        with open(self.path, "w") as file:
            json.dump(OLD, file)
        config.load_config()
        self.assertEqual(self.saved()["thresholds"]["reset_threshold"], 0.3)
        self.assertEqual(config.get("thresholds", "reset_threshold"), 0.3)

    def test_new_settings_record_every_change(self):
        config.load_config()
        self.assertEqual([record["version"] for record in self.saved()[migrations.KEY]], ["0.6.0"])

    def test_leaves_up_to_date_settings_alone(self):
        with open(self.path, "w") as file:
            json.dump(migrated(OLD, "0.6.0"), file, indent=1)
        config.load_config()
        with open(self.path) as file:
            self.assertEqual(file.read(), json.dumps(migrated(OLD, "0.6.0"), indent=1))


class SettingsChangesDialogTest(unittest.TestCase):
    def dialog(self):
        dialog = SettingsChangesDialog([THRESHOLD, RENAME_THEME | {"name": "Theme", "reason": "Nicer."}])
        self.addCleanup(close_window, dialog)
        return dialog

    def test_shows_each_change_and_why(self):
        texts = [item.property("text") for item in qml_items(self.dialog().view)]
        self.assertIn("Reset Threshold: 0.1 → 0.3", texts)
        self.assertIn("Catches more resets.", texts)

    def test_apply_the_checked_ones(self):
        dialog = self.dialog()
        qml(dialog.view, "change1").setProperty("checked", False)
        dialog.accept()
        self.assertEqual(dialog.accepted_steps(), [THRESHOLD])

    def test_keep_my_settings(self):
        dialog = self.dialog()
        dialog.reject()
        self.assertEqual(dialog.accepted_steps(), [])


class ReleasedMigrationsTest(unittest.TestCase):
    def test_every_step_can_be_undone(self):
        for version, steps in migrations.MIGRATIONS:
            for step in steps:
                self.assertEqual(migrations._inverse(migrations._inverse(step)),
                                 {k: v for k, v in step.items() if k not in ("name", "reason")}, version)

    def test_offered_steps_say_what_and_why(self):
        for version, steps in migrations.MIGRATIONS:
            for step in steps:
                if "reason" in step:
                    self.assertIn("name", step, version)

    def test_defaults_are_the_latest_settings(self):
        # New settings are copied from them, as having every change
        for version, steps in migrations.MIGRATIONS:
            for step in steps:
                if "set" in step:
                    self.assertEqual(config.get_default(*step["set"]), step["to"], version)

    def test_shipped_templates_both_old_and_new(self):
        # The old ones for releases that go back down to them
        root = Path(__file__).parent.parent
        for version, steps in migrations.MIGRATIONS:
            for step in steps:
                if "set" in step and step["set"][1].startswith("reset_frame_"):
                    self.assertTrue((root / step["from"]).exists(), step["from"])
                    self.assertTrue((root / step["to"]).exists(), step["to"])

if __name__ == "__main__":
    unittest.main()
