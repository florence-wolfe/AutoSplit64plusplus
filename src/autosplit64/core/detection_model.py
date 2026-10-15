"""
The detection model, as model.detection. Releases before it only know model.legacy, true for the legacy model, so
it's saved with that too: they read it right, and keep model.detection, which they don't know, when they save.
"""
from . import config

# AutoSplit64's star predictor
LEGACY = "legacy"
# AutoSplit64+'s star predictor
STAR_PREDICTOR = "star_predictor"
# AutoSplit64+'s star predictor, with the Grand Star found after Bowser's last words
AS64PP = "as64pp"
MODELS = [LEGACY, STAR_PREDICTOR, AS64PP]
# What settings call them, for the log
NAMES = {LEGACY: "AS64 Legacy Model", STAR_PREDICTOR: "AS64+ Star Predictor", AS64PP: "AS64++ Detection"}


def get():
    legacy = config.get("model", "legacy")
    chosen = config.get("model", "detection")
    # A release before it chose with model.legacy since, or a later one saved a model this one doesn't know
    if chosen not in MODELS or (chosen == LEGACY) != legacy:
        return LEGACY if legacy else STAR_PREDICTOR
    return chosen


def legacy(model):
    """ model.legacy for the model, for releases before model.detection """
    return model == LEGACY
