# TODO

Ranked by what matters most to a runner, then by what makes the rest safer to do.

1. **More recorded runs.** `tests/recordings` has one clean run, on the JP version, captured through one runner's setup. Add runs with deaths, resets during the run and star skips, other versions and captures (VC, emulators), and the other split types (X-Cam, fade-only, File Select and Up RTA timing). Recordings of your own could run in CI, without YouTube. The replay doesn't charge detection's processing time to the clock, so it can't show splits that a slow computer would be late for.

2. **Make the core stateful.** `core/__init__.py` is a module of stub functions and globals that `Base` overwrites with its own methods and values when split detection starts. Replace it with an object that holds the state and that the processes are given, so it can be created, tested and thrown away without patching a module.

3. **Capture cards on Windows without the OBS Plugin.** Windows has no Video Device source yet, so capture card users who run OBS need the plugin: capturing the OBS window gets the scaled preview with overlays, and most capture cards can't be opened by a second program while OBS uses them. Add a Video Device source on Windows like the macOS one, so the OBS Virtual Camera (with its output set to the capture card source) and capture cards can be captured directly, e.g. with OpenCV, which is already a dependency. Then compare it with the plugin for latency and image quality (the virtual camera always uses OBS's output resolution, and can only output one thing at a time), and if it's good enough, retire the plugin, its build and `capture_shmem.py`.

4. **Fadein oscillation** (`TODO: BUG` in `processes/standard.py`). `ProcessFadein` returns `COMPLETE` while the screen is still white, transitions to the star count process, which transitions straight back.

5. **Probability mode lags a frame.** In `_analyze_star_count_probability_mode`, `total_predictions` is read before the new prediction is appended, so `prev_two_probabilities` looks at the two predictions before the current one. The thresholds were tuned with this lag, so whether reading the current prediction is better needs more recorded runs (1) to judge.

6. **Video files as a capture source in the Capture Editor.** The replay's video capture (`tests/replay.py`) is most of it. Lets people check their region, thresholds and route against a recording, and send one along with a bug report.

7. **Save debug info.** The log only records warnings, and processor transitions only go to `print`. Add a menu item that saves the config, route, log, capture size and a frame with the regions drawn on it, for bug reports.

8. **Keep the macOS permissions across updates.** Every update needs the Screen Recording and Camera permissions again. macOS probably ties them to the code signature, so signing every release with the same self-signed certificate in CI may keep them, without an Apple developer account. Unverified: try it with two builds first.

9. **The updater's log line is never written.** `main.py` sets the log level to `WARNING`, but `updater.py` logs where the installer's log is with `.info(...)`.

10. **`test_split_list` in `tests/test_theme.py` is flaky.** It fails about one in three runs of the whole suite: the selected row is sometimes drawn in the inactive highlight colour (grey), probably because the window doesn't have focus. Releases run the tests first, so it can fail a release.
