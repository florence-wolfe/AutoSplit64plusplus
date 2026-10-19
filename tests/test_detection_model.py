""" The detection model setting, and releases before it, which only know model.legacy: see core/detection_model.py """
import unittest
from unittest import mock

from autosplit64.core import config, detection_model


def chosen(**model):
    with mock.patch.object(config, "_config", {"model": model}):
        return detection_model.get()


class DetectionModelTest(unittest.TestCase):
    def test_chosen(self):
        for model in detection_model.MODELS:
            with self.subTest(model):
                self.assertEqual(chosen(legacy=detection_model.legacy(model), detection=model), model)

    def test_settings_from_before_it(self):
        self.assertEqual(chosen(legacy=True), detection_model.LEGACY)
        self.assertEqual(chosen(legacy=False), detection_model.STAR_PREDICTOR)

    def test_legacy_chosen_since_in_a_release_before_it(self):
        for model in (detection_model.STAR_PREDICTOR, detection_model.AS64PP):
            with self.subTest(model):
                self.assertEqual(chosen(legacy=True, detection=model), detection_model.LEGACY)

    def test_star_predictor_chosen_since_in_a_release_before_it(self):
        self.assertEqual(chosen(legacy=False, detection=detection_model.LEGACY), detection_model.STAR_PREDICTOR)

    def test_a_model_from_a_later_release(self):
        self.assertEqual(chosen(legacy=False, detection="as64pp_2"), detection_model.STAR_PREDICTOR)
        self.assertEqual(chosen(legacy=True, detection="as64pp_2"), detection_model.LEGACY)

    def test_features_of_the_model_chosen(self):
        with mock.patch.object(config, "_config", {"model": {"legacy": False, "detection": detection_model.AS64PP}}):
            self.assertTrue(detection_model.has(detection_model.LOOKS_BETWEEN))
            self.assertTrue(detection_model.has(detection_model.DEATHS))
        with mock.patch.object(config, "_config", {"model": {"legacy": False, "detection": detection_model.STAR_PREDICTOR}}):
            self.assertFalse(detection_model.has(detection_model.LOOKS_BETWEEN))
            self.assertTrue(detection_model.has(detection_model.DEATHS))

    def test_every_model_has_features_listed(self):
        self.assertEqual(set(detection_model.FEATURES), set(detection_model.MODELS))

    def test_defaults(self):
        # Opting in to AS64++ is up to the runner
        self.assertEqual(config.get_default("model", "detection"), detection_model.STAR_PREDICTOR)
        self.assertIs(config.get_default("model", "legacy"), False)


if __name__ == "__main__":
    unittest.main()
