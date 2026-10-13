"""
Changes to the settings between releases. config.ini records the ones it has had, each with the steps that undo it,
so a later release can bring it up to date and an earlier one, from the first with migrations on, can take it back
down by itself, without knowing what the later release changed.

A release that changes a setting adds its version and steps to MIGRATIONS, in order, and never edits them once
released. A step is plain JSON, so it can be stored and undone:
- {"set": [section, key], "from": old, "to": new}: changes the value, if it's still `from`. With a "name" and a
  "reason", the upgrade prompt offers it instead of changing it silently: a changed default, say.
- {"move": [[section, key], [section, key]]}: renames or moves a key, if it's there.
Releases before migrations ignore the record and keep it, but read a moved key at its old place, so they get its
default there.
"""
import logging

KEY = "_migrations"

MIGRATIONS = [
    ("0.6.0", [
        {"set": ["advanced", "reset_frame_one"], "from": "templates/default_reset_one.jpg",
         "to": "templates/default_reset_one_v2.jpg", "name": "Reset Frame One",
         "reason": "New default reset templates, from a console capture, that catch resets the old ones missed. "
                   "The timer starts one frame (33 ms) earlier with them, like with generated templates."},
        {"set": ["advanced", "reset_frame_two"], "from": "templates/default_reset_two.jpg",
         "to": "templates/default_reset_two_v2.jpg", "name": "Reset Frame Two",
         "reason": "The other new default reset template."},
    ]),
]

_MISSING = object()


def _value(data, section, key):
    return data.get(section, {}).get(key, _MISSING)


def _holds(data, step):
    """ Whether the step would change data """
    if "set" in step:
        return _value(data, *step["set"]) == step["from"]
    return _value(data, *step["move"][0]) is not _MISSING


def _apply(data, step):
    """ Changes data by the step, if it holds. Returns whether it did. """
    if not _holds(data, step):
        return False
    if "set" in step:
        section, key = step["set"]
        data[section][key] = step["to"]
    else:
        (old_section, old_key), (new_section, new_key) = step["move"]
        data.setdefault(new_section, {})[new_key] = data[old_section].pop(old_key)
        # An empty section would hide its defaults
        if not data[old_section]:
            del data[old_section]
    return True


def _inverse(step):
    if "set" in step:
        return {"set": step["set"], "from": step["to"], "to": step["from"]}
    return {"move": step["move"][::-1]}


def offers(data):
    """ The steps the upgrade prompt offers for data """
    applied = len(data.get(KEY, []))
    return [step for _, steps in MIGRATIONS[applied:] for step in steps if "reason" in step and _holds(data, step)]


def migrate(data, choose=None):
    """
    Brings data to this release's settings: undoes what later releases changed, then applies this release's
    changes. choose(offered steps) returns the offered ones to apply; without it, all of them are. Returns whether
    data changed.
    """
    applied = data.setdefault(KEY, [])
    known = [version for version, _ in MIGRATIONS]
    changed = False

    # Settings from a later release, or another line of releases: undo the changes this one doesn't know, newest first
    while applied and [record["version"] for record in applied] != known[:len(applied)]:
        record = applied.pop()
        for step in record["down"]:
            _apply(data, step)
        logging.getLogger(".log").info("Undid the settings changes of %s", record["version"])
        changed = True

    offered = offers(data)
    accepted = choose(offered) if choose and offered else offered
    for version, steps in MIGRATIONS[len(applied):]:
        down = []
        for step in steps:
            if ("reason" not in step or any(step is a for a in accepted)) and _apply(data, step):
                down.insert(0, _inverse(step))
        applied.append({"version": version, "down": down})
        logging.getLogger(".log").info("Applied the settings changes of %s", version)
        changed = True

    return changed


def stamp(data):
    """ Records new settings, made from this release's defaults, as having every change, so they can go back down """
    data[KEY] = [{"version": version, "down": [_inverse(step) for step in reversed(steps)]}
                 for version, steps in MIGRATIONS]
