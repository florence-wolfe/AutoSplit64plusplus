"""
Replays recorded runs through split detection, for tests.

A recording is a video of a run, with a .json in tests/recordings of where the game is in it and when
each split should happen. The videos aren't in the repository: `uv run python -m tests.replay` downloads
them into tests/recordings/cache, and tests that need one are skipped without it.

Split detection runs as in the app, with the app's default settings, except:
- Frames come from the video, at the time of a clock that replaces time.time() and time.sleep(). Sleeping
  advances the clock instead of waiting, so a run replays as fast as the computer allows. Detection itself
  takes no time on the clock, unlike in the app, where a slow computer has fewer frames to look at.
- LiveSplit is a timer that records the commands it gets.
"""
import contextlib
import copy
import importlib
import io
import json
import logging
import math
import os
from dataclasses import dataclass
from pathlib import Path
from unittest import mock

import cv2

from autosplit64 import core, main
from autosplit64.core import base, config, route_loader
from autosplit64.core.constants import RESET_REGION
from autosplit64.core.game_capture import GameCapture
from autosplit64.core.image_utils import is_black
from autosplit64.gui.dialogs import reset_generator_dialog

RECORDINGS = Path(__file__).parent / "recordings"
CACHE = RECORDINGS / "cache"
DEFAULTS = Path(__file__).parent.parent / "defaults.ini"
# The runner's timer in a video shows a split a little after split detection sends it, once LiveSplit and the
# recording show it: NoraSM64's LiveSplit shows AutoSplit64+'s splits 0.03 to 0.08 s after the replay sends them
DISPLAY_DELAY = 0.1
# Leeway for adding up floating point numbers
ROUNDING = 1e-6


@dataclass
class Recording:
    name: str
    title: str
    url: str
    height: int
    game_region: list
    route: str
    # Seconds the video is ahead of the runner's timer
    timer_offset: float
    # What the runner's timer starts at
    timer_start: float
    # (title, the runner's split time as their timer shows it, e.g. "1:35.1")
    splits: list

    @classmethod
    def load(cls, name):
        data = json.loads((RECORDINGS / f"{name}.json").read_text())
        data.pop("labels")
        return cls(name, **data)

    @property
    def video(self):
        return CACHE / f"{self.name}.mp4"

    @property
    def route_path(self):
        return RECORDINGS / self.route

    def available(self):
        return self.video.exists()

    def _window(self, time, shown_for):
        """
        When split detection did what the runner's timer shows at `time`, which it shows for `shown_for` seconds:
        the offset is exact to within a frame, and detection is up to DISPLAY_DELAY ahead of the timer
        """
        start = time + self.timer_offset
        return start - 1 / self.fps() - DISPLAY_DELAY - ROUNDING, start + shown_for + ROUNDING

    def start_window(self):
        """ When split detection started the timer """
        return self._window(self.timer_start, 0)

    def split_windows(self):
        """ (title, earliest, latest) in the video of each of the runner's splits """
        windows = []
        for title, shown in self.splits:
            minutes, _, seconds = shown.rpartition(":")
            # The timer shows tenths, cut off
            windows.append((title, *self._window(int(minutes or 0) * 60 + float(seconds), 0.1)))
        return windows

    def _video_property(self, *properties):
        video = cv2.VideoCapture(str(self.video))
        try:
            return [video.get(p) for p in properties]
        finally:
            video.release()

    def fps(self):
        return self._video_property(cv2.CAP_PROP_FPS)[0]

    def length(self):
        frames, fps = self._video_property(cv2.CAP_PROP_FRAME_COUNT, cv2.CAP_PROP_FPS)
        return frames / fps

    def capture_size(self):
        return [int(size) for size in self._video_property(cv2.CAP_PROP_FRAME_WIDTH, cv2.CAP_PROP_FRAME_HEIGHT)]


class Clock:
    """ Stands in for time.time() and time.sleep(). `now` is the time in the video. """

    # time.time() is seconds since 1970. Detection starts e.g. its last split at 0, which must be long ago.
    EPOCH = 1_700_000_000

    def __init__(self, now, end):
        self.now = now
        self.end = end
        # Called once the clock reaches the end
        self.on_end = None

    def time(self):
        return self.EPOCH + self.now

    def sleep(self, seconds):
        if seconds < 0:
            raise ValueError("sleep length must be non-negative")
        self.now += seconds
        if self.now >= self.end and self.on_end:
            self.on_end()


class VideoCapture(GameCapture):
    """ Captures the video's frame at the clock's time, instead of a window or device """

    def __init__(self, path, clock, game_region, version):
        # Like a video device, which needs no window
        super().__init__(False, False, "", game_region, version, device=str(path))
        self._clock = clock
        self._video = cv2.VideoCapture(str(path))
        self._fps = self._video.get(cv2.CAP_PROP_FPS)
        self._index = int(clock.now * self._fps) - 1
        self._video.set(cv2.CAP_PROP_POS_FRAMES, self._index + 1)
        self._frame = None

    def is_valid(self):
        pass

    def capture(self):
        target = int(self._clock.now * self._fps)
        while self._index < target or self._frame is None:
            ok, frame = self._video.read()
            # Past the end, keep the last frame
            if not ok:
                break
            self._index += 1
            self._frame = frame
        # The time of the frame in the video, which split detection decides on
        self.frame_time = self._index / self._fps
        self._window_image = self._frame
        self._region_images = {}

    def get_capture_size(self):
        return [int(self._video.get(p)) for p in (cv2.CAP_PROP_FRAME_WIDTH, cv2.CAP_PROP_FRAME_HEIGHT)]

    def close(self):
        pass

    def release(self):
        self._video.release()


class Timer:
    """ Stands in for the livesplit module: a timer with the route's splits, which records the commands it gets """

    def __init__(self, now, split_count, index=-1):
        # When a command happens, in the video
        self._now = now
        self._split_count = split_count
        # -1 while the timer isn't running, like LiveSplit's getsplitindex, and the split count once it ended
        self.index = index
        # (time, command, split index afterwards)
        self.commands = []

    def _record(self, command):
        self.commands.append((self._now(), command, self.index))

    def connect(self):
        return self

    def disconnect(self, timer):
        pass

    def check_connection(self, timer):
        return True

    def split_index(self, timer):
        return self.index

    def split(self, timer):
        # Starts the timer when it isn't running
        if self.index < self._split_count:
            self.index += 1
        self._record("split")

    def reset(self, timer):
        self.index = -1
        self._record("reset")

    def restart(self, timer):
        self.index = 0
        self._record("restart")

    def skip(self, timer):
        if 0 <= self.index < self._split_count:
            self.index += 1
        self._record("skip")

    def undo(self, timer):
        if self.index > 0:
            self.index -= 1
        self._record("undo")


@dataclass
class Replay:
    # (time, command, split index afterwards) of each command split detection sent to the timer
    commands: list
    # The errors split detection reported, which stop it
    errors: list
    # The warnings and errors it logged
    log: list

    def run_commands(self):
        """ The commands from the console reset the run starts with, if any. Videos can start in the attempt before. """
        start = next((i for i, (_, command, _) in enumerate(self.commands) if command == "reset"), 0)
        return self.commands[start:]

    def split_times(self):
        """ When the timer moved on to each split in the run, by the index of the split that ended """
        return {index - 1: time for time, command, index in self.run_commands() if command == "split" and index > 0}


class _LogRecorder(logging.Handler):
    def __init__(self):
        super().__init__(logging.WARNING)
        self.records = []

    def emit(self, record):
        self.records.append(self.format(record))


def _settings(recording, templates):
    """ The default settings, set up for the recording """
    settings = copy.deepcopy(json.loads(DEFAULTS.read_text()))
    settings["route"]["path"] = str(recording.route_path)
    settings["game"].update(use_obs=False, vc_fix=False, capture_source="window", override_version=False,
                            game_region=recording.game_region, capture_size=recording.capture_size())
    if templates:
        settings["advanced"].update(reset_frame_one=str(templates[0]), reset_frame_two=str(templates[1]))
    settings["general"]["srl_mode"] = False
    return settings


@contextlib.contextmanager
def _replaying(recording, clock, settings):
    """ The clock and settings in place of the real ones, with what detection prints and logs captured """
    recorder = _LogRecorder()
    root = logging.getLogger()
    root.addHandler(recorder)
    try:
        with mock.patch("time.time", clock.time), mock.patch("time.sleep", clock.sleep), \
             mock.patch.object(config, "_config", settings), mock.patch.object(config, "load_config"), \
             contextlib.redirect_stdout(io.StringIO()):
            yield recorder.records
    finally:
        root.removeHandler(recorder)


def generate_reset_templates(recording, directory):
    """
    Reset templates from the console reset the recording starts with, like Generate Reset Templates does with
    the default frames: two and three after the fadeout. Returns their paths.
    """
    at, length = 0, recording.start_window()[1] + 5
    clock = Clock(at, at + length)
    settings = _settings(recording, None)
    with _replaying(recording, clock, settings), \
         mock.patch.object(reset_generator_dialog.ResetGeneratorDialog, "TEMPLATE_DIR", f"{directory}{os.sep}"), \
         mock.patch.object(reset_generator_dialog, "GameCapture",
                           lambda *args: VideoCapture(recording.video, clock, args[3], args[4])):
        generator = reset_generator_dialog.ResetGenerator()
        errors = []
        generator.error.connect(errors.append)
        clock.on_end = generator.stop
        generator.run()
        generator._game_capture.release()
        frames = [Path(reset_generator_dialog.ResetGeneratorDialog._temp_path(n)) for n in (2, 3)]

    if errors or not all(frame.exists() for frame in frames):
        raise RuntimeError(f"No console reset between {at} and {at + length} s: {errors}")
    return frames


def first_black_centre(recording, earliest, latest):
    """
    The time of the first frame from `earliest` to `latest` where the centre of the game is black, which a split
    at a fadeout waits for, or None
    """
    black_threshold = json.loads(DEFAULTS.read_text())["thresholds"]["black_threshold"]
    version = route_loader.load(recording.route_path).version
    clock = Clock(earliest, latest)
    capture = VideoCapture(recording.video, clock, recording.game_region, version)
    try:
        fps = recording.fps()
        # Frame times times fps are whole numbers, give or take rounding
        for frame in range(math.ceil(earliest * fps - ROUNDING), math.floor(latest * fps + ROUNDING) + 1):
            # Within the frame, so it's the frame that's captured
            clock.now = (frame + 0.5) / fps
            capture.capture()
            if is_black(capture.get_region(RESET_REGION), black_threshold):
                return capture.frame_time
        return None
    finally:
        capture.release()


def replay(recording, start, end, templates, split_index=-1):
    """
    Split detection over the video from `start` to `end` seconds, with the timer at `split_index`
    (-1: not running). Returns what it did.
    """
    clock = Clock(start, end)
    timer = Timer(lambda: captures[-1].frame_time, len(route_loader.load(recording.route_path).splits), split_index)
    captures = []

    def video_capture(use_obs, vc_fix, process_name, game_region, version, device):
        captures.append(VideoCapture(recording.video, clock, game_region, version))
        return captures[-1]

    errors = []
    with _replaying(recording, clock, _settings(recording, templates)) as log, \
         mock.patch.object(base, "livesplit", timer), mock.patch.object(base, "GameCapture", video_capture):
        # Split detection keeps its state in the core module, which starts afresh like when the app opens
        importlib.reload(core)
        try:
            core.init()
            main.register_processes()
            failed = main.register_split_processors()
            if failed:
                raise RuntimeError(f"{failed} failed to generate")
            # Like main.AutoSplit64.start, which sets all three
            core.set_update_listener(lambda index, star_count, split_star: None)
            core.set_start_listener(lambda: None)
            core.set_error_listener(errors.append)
            detection = core._base
            clock.on_end = lambda: setattr(detection, "_running", False)
            detection.run()
            detection.stop()
        finally:
            for capture in captures:
                capture.release()
            importlib.reload(core)

    return Replay(timer.commands, errors, log)


def download(recording):
    import yt_dlp

    CACHE.mkdir(exist_ok=True)
    # Only the video, so no ffmpeg is needed to merge it with the audio, or else one file with both, like on Twitch
    video = f"[height={recording.height}][ext=mp4]"
    options = {"format": f"bestvideo{video}/bv*{video}", "outtmpl": str(recording.video)}
    with yt_dlp.YoutubeDL(options) as downloader:
        downloader.download([recording.url])


if __name__ == "__main__":
    for path in sorted(RECORDINGS.glob("*.json")):
        recording = Recording.load(path.stem)
        if recording.available():
            print(f"{recording.name}: already downloaded")
        else:
            download(recording)
