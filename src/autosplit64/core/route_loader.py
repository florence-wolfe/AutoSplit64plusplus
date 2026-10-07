import json
import logging

from .route import (
    Route,
    Split,
    FILE_PATH,
    ROUTE,
    TITLE,
    CATEGORY,
    INITIAL_STAR,
    TIMING,
    STAR_COUNT,
    VERSION,
    FADEOUT,
    FADEIN,
    XCAM,
    SPLITS,
    SPLIT_TYPE,
    ICON
)

from .constants import (
    SPLIT_NORMAL,
    SPLIT_FADE_ONLY,
    TIMING_RTA,
    TIMING_UP_RTA,
    TIMING_FILE_SELECT
)


def load(file_path):
    """
    Returns the route in file_path, or None if there's no such file.
    Raises JSONDecodeError or KeyError for an invalid route file.
    """
    try:
        # utf-8-sig also reads files starting with a byte order mark
        with open(file_path, encoding="utf-8-sig") as route_data:
            data = json.load(route_data)
    except FileNotFoundError:
        return None

    if not isinstance(data, dict) or not data.get(ROUTE):
        raise KeyError(ROUTE)
    data[FILE_PATH] = file_path
    return _decode(data)


def load_or_none(file_path):
    """ Like load, but also returns None for an invalid route file """
    try:
        return load(file_path)
    except (ValueError, KeyError, TypeError, OSError):
        logging.getLogger(".log").warning("Could not load route %s", file_path, exc_info=True)
        return None


def save(route_data, file):
    with open(file, "w") as write_file:
        json.dump(route_data, write_file, indent=4, cls=RouteEncoder)


def _decode(data):
    """ The Route of a route file's data """
    # Routes from v0.1.x have no X-Cam counts or timing
    splits = [Split(split[TITLE],
                    split[STAR_COUNT],
                    split[FADEOUT],
                    split[FADEIN],
                    split.get(XCAM, -1),
                    split[SPLIT_TYPE],
                    split[ICON]) for split in data[SPLITS]]

    return Route(data[FILE_PATH],
                 data[TITLE],
                 splits,
                 data[INITIAL_STAR],
                 data[VERSION],
                 data.get(CATEGORY, ""),
                 data.get(TIMING, TIMING_RTA))


class RouteEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, Route):
            splits = []
            for split in o.splits:
                splits.append({TITLE: split.title,
                               STAR_COUNT: split.star_count,
                               FADEOUT: split.on_fadeout,
                               FADEIN: split.on_fadein,
                               XCAM: split.on_xcam,
                               SPLIT_TYPE: split.split_type,
                               ICON: split.icon_path})

            return {ROUTE: True,
                    TITLE: o.title,
                    CATEGORY: o.category,
                    INITIAL_STAR: o.initial_star,
                    VERSION: o.version,
                    TIMING: o.timing,
                    SPLITS: splits}
        else:
            return super().default(o)


def validate_route(route):
    if route.length < 1:
        return "Route must contain at least one split."

    if route.initial_star < 0 or route.initial_star > 120:
        return "Invalid initial star."

    if route.timing not in (TIMING_RTA, TIMING_UP_RTA, TIMING_FILE_SELECT):
        return "Invalid timing method."

    prev_star_count = -1

    for split in route.splits:
        # Check Split Title
        if type(split.title) != str:
            return "Invalid split title."

        if route.initial_star > split.star_count != -1:
            return "Initial star must be lower than first split star."

        # Check split star
        if type(split.star_count) != int:
            return "Split Star is not a valid integer"

        if split.star_count < 0 or split.star_count > 120:
            if split.split_type != SPLIT_FADE_ONLY:
                return "Split: {} - Invalid Split Star.".format(split.title)

        if split.star_count < prev_star_count:
            return "Split: {} - Split star must be greater than previous split.".format(split.title)

        prev_star_count = split.star_count

        # Check fadeout/in
        if type(split.on_fadeout) != int or split.on_fadeout < 0:
            if split.split_type == SPLIT_NORMAL:
                return "Split: {} - Fadeout count is not a valid integer.".format(split.title)

        if type(split.on_fadein) != int or split.on_fadein < 0:
            if split.split_type == SPLIT_NORMAL:
                return "Split: {} - Fadein count is not a valid integer.".format(split.title)

        if split.on_fadein == 0 and split.on_fadeout == 0:
            if split.split_type == SPLIT_NORMAL:
                return "Split: {} - Fadein and Fadeout are both set to zero.".format(split.title)

        # Check icon path
        if type(split.icon_path) != str and split.icon_path is not None:
            return "Split: {} - Invalid icon_path".format(split.title)

    return None
