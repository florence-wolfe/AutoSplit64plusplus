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

# What split detection does with each model. A new feature that changes which splits happen or when goes in AS64++
# only, so the others split as they did, which runners' times and golds are compared against, and the changelog says
# what changed for which.
# Telling a death from other fadeouts, by Bowser's iris or a life lost: in every model since 0.8.0
DEATHS = "deaths"
# Looking at a frame between looks that starts a fade or shows the reset logo, which moves splits by a frame either way
LOOKS_BETWEEN = "looks_between"
# Fitting irises that end up to 5 frames after the centre goes black, as over a dark stage, instead of 3: tells more
# deaths, e.g. in the BitFS fight
IRISES_ENDING_LATE = "irises_ending_late"
# Resetting once each time the SM64 logo shows, instead of on each look that sees it, which it can be for two
RESET_LOGO_ONCE = "reset_logo_once"
# Sending no split within general.split_cooldown seconds of the last. AS64++ sends a split once per fade or X-Cam
# instead, which every model does, and which the cooldown no longer stops any split over the recordings for.
SPLIT_COOLDOWN = "split_cooldown"
# Splitting Mips when Mario's hat drops out of sight at once, as he enters the painting, instead of on the first look
# without it, which can be as the portal first shows after the door clip, or while he's far and in shadow
MIPS_HAT_DROP = "mips_hat_drop"
FEATURES = {
    LEGACY: {DEATHS, SPLIT_COOLDOWN},
    STAR_PREDICTOR: {DEATHS, SPLIT_COOLDOWN},
    AS64PP: {DEATHS, LOOKS_BETWEEN, IRISES_ENDING_LATE, RESET_LOGO_ONCE, MIPS_HAT_DROP},
}


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


def has(feature):
    """ Whether the model chosen has the feature """
    return feature in FEATURES[get()]
