""" Settings for a test, instead of the ones it would read """
from unittest import mock

from autosplit64.core import config


def patch_settings(values, real=False):
    """
    config.get answering from values, by (section, key), which a test may change as it goes. Only from them, so a test
    fails on a setting it didn't expect, or with real, from the real settings for the rest.
    """
    real_get = config.get

    def get(section, key=None):
        if real and (section, key) not in values:
            return real_get(section, key)
        return values[(section, key)]
    return mock.patch.object(config, "get", side_effect=get)
