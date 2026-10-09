# TODO

Ranked by what matters most to a runner, then by what makes the rest safer to do.

1. **More recorded runs.** `tests/recordings` has two clean 16 Star No LBLJ runs on console with the JP version: greensuigi's and NoraSM64's. Add runs with deaths, resets during the run and star skips, the LBLJ route, other versions and captures (VC, emulators), and the other split types (X-Cam, fade-only, File Select and Up RTA timing). A run is only ground truth when the runner split with AutoSplit64: BigCheeseSR's and DharcLicht's splits differ from split detection by up to 0.2 s either way, so they split some other way. Recordings of your own could run in CI, without YouTube or Twitch. The replay doesn't charge detection's processing time to the clock, so it can't show splits that a slow computer would be late for.

2. **Capture cards on Windows without the OBS Plugin.** Windows has no Video Device source yet, so capture card users who run OBS need the plugin: capturing the OBS window gets the scaled preview with overlays, and most capture cards can't be opened by a second program while OBS uses them. Add a Video Device source on Windows like the macOS one, so the OBS Virtual Camera (with its output set to the capture card source) and capture cards can be captured directly, e.g. with OpenCV, which is already a dependency. Then compare it with the plugin for latency and image quality (the virtual camera always uses OBS's output resolution, and can only output one thing at a time), and if it's good enough, retire the plugin, its build and `capture_shmem.py`.

3. **Fadein oscillation** (`TODO: BUG` in `processes/standard.py`). `ProcessFadein` returns `COMPLETE` while the screen is still white, transitions to the star count process, which transitions straight back. A fade-in split happens before it starts, but it changes how often split detection looks while the screen is white. Only fix it if the traces in `tests/recordings/traces` stay the same, the `fade-ins` ones in particular, or every change in them is understood: split timing must not change.

4. **Probability mode lags a frame.** In `_analyze_star_count_probability_mode`, `total_predictions` is read before the new prediction is appended, so `prev_two_probabilities` looks at the two predictions before the current one. The thresholds were tuned with this lag, so whether reading the current prediction is better needs more recorded runs (1) to judge.

5. **Video files as a capture source in the Capture Editor.** The replay's video capture (`tests/replay.py`) is most of it. Lets people check their region, thresholds and route against a recording, and send one along with a bug report.

6. **Save the last 30 seconds of capture.** A menu item or hotkey that saves the frames split detection looked at in the last 30 seconds, so a bug report has the moment it went wrong even without a recording, and the replay in `tests/replay.py` can run on it. Keep them compressed in memory, roughly 30 MB for 30 seconds by estimate; measure the memory and CPU it takes first.

7. **Keep the macOS permissions across updates.** Every update needs the Screen Recording and Camera permissions again. macOS probably ties them to the code signature, so signing every release with the same self-signed certificate in CI may keep them, without an Apple developer account. Unverified: try it with two builds first.
