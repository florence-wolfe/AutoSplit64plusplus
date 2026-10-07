from dataclasses import dataclass

from .constants import SPLIT_NORMAL, TIMING_RTA

FILE_PATH = "file_path"
ROUTE = "__route__"
TITLE = "title"
CATEGORY = "category"
INITIAL_STAR = "initial_star"
TIMING = "timing"
FINAL_STAR = "final_star"
FINAL_SPLIT = "final_split"
STAR_COUNT = "star_count"
VERSION = "version"
FADEOUT = "fade_out"
FADEIN = "fade_in"
XCAM = "xcam"
SPLIT_TYPE = "split_type"
SPLITS = "splits"
TIMEOUT = "timeout"
ICON = "icon_path"


# Splits and routes compare by identity: split detection finds the current split with list.index
@dataclass(eq=False)
class Split:
    title: str = ""
    star_count: int = 0
    on_fadeout: int = 0
    on_fadein: int = 0
    on_xcam: int = -1
    split_type: str = SPLIT_NORMAL
    icon_path: str | None = None


@dataclass(eq=False)
class Route:
    file_path: str
    title: str
    splits: list[Split]
    initial_star: int = 0
    version: str = "JP"
    category: str = ""
    timing: str = TIMING_RTA

    @property
    def length(self):
        return len(self.splits)

    def insert_split(self, index):
        self.splits.insert(index, Split())

    def remove_split(self, index):
        self.splits.pop(index)
