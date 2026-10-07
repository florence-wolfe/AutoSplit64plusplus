<h1 align="center"> AutoSplit64++ </h1><br>
<p align="center">
    <img alt="AS64+" title="AS64+" src="resources\gui\icons\as64plus.png" width="256">
</p>

## Introduction
AutoSplit64++ is a fork of [AutoSplit64+](https://github.com/DaviBe92/AutoSplit64plus) that adds macOS (Apple Silicon) support, direct window capture on macOS, LiveSplit One support and a resizable window. The rest of this README is based on AutoSplit64+'s.

AutoSplit64+ is an enhanced fork of [AutoSplit64](https://github.com/Kainev/AutoSplit64), providing automated splitting for Super Mario 64 speedruns on console. 
It analyzes captured gameplay to control LiveSplit timer events automatically. 

The project's main objectives are to simplify setup and enhance reliability.

## Key Features
### Core Functionality
- Automatic split timing
- Console reset detection
- Star count detection
- DDD entry, Final star, X-Cam and Death detection
- Custom route creation
- LiveSplit .lss file conversion

### AS64+ Enhancements
- **Direct OBS Integration**
  - Native OBS capture support via Plugin
  - Changing size, switching scenes, adding Overlays, etc. dont influence the capture
  - AmaRecTV is no longer required
- **Streamlined Setup**
  - Automatic LiveSplit Server connection
  - No manual server starting needed
- **Autostart Split Detection**
  - Automatically start Split Detection when AS64+ is launched
  - Tries to connect to LiveSplit and start Game Capture for 5 minutes
  - Once setup, AS64+ can run entirely in the background
- **Improved Recognition**
  - Enhanced star detection accuracy
  - Resilient to inaccurate capture region 
  - Automatic capture region detection

## System Requirements
- Windows 10 or later
- LiveSplit 1.8.29 or newer
- OBS Studio 30.0 or newer (for OBS integration)
- Capture device/card

## Quick Setup

1. Download the latest [Release](https://github.com/florence-wolfe/AutoSplit64plusplus/releases) for your platform.
2. Windows: extract the zip and run `AutoSplit64++.exe`. macOS: see [Installing on macOS](#installing-on-macos).
3. Set LiveSplit to start at 1.36 seconds.
4. Set Game Capture method and region.
5. Generate Reset Templates.
6. Press Start.

### Installing on macOS

1. Open the downloaded zip and drag `AutoSplit64++.app` into your `Applications` folder.
2. Open AutoSplit64++. The first time, macOS says it can't verify that AutoSplit64++ is free of malware and doesn't open it, because AutoSplit64++ isn't signed by a registered Apple developer. Click `Done`.
3. Open `System Settings -> Privacy & Security`, scroll down to `Security`, where it says AutoSplit64++ was blocked, and click `Open Anyway`. Confirm with your password or Touch ID, then click `Open`.

On macOS 14 and earlier, you can instead Control-click (or right-click) the app, choose `Open`, and confirm.

Alternatively, remove the flag macOS puts on downloaded files in Terminal, which only makes sense for apps you trust:

```
xattr -dr com.apple.quarantine /Applications/AutoSplit64++.app
```

This is only needed once for each version you download yourself: updates installed by AutoSplit64++ open without it. If you open AutoSplit64++ before moving it, it offers to move itself to Applications: until it's moved, macOS may run it from a temporary read-only copy, where updates can't be installed. Choose `Don't Ask Again` if you keep it elsewhere on purpose.

### Interface

All windows and options are accessed via the right-click menu, which the menu button (☰) in the bottom right corner also opens. On macOS, the same menu is also available as `Options` in the menu bar:

![Interface](repo/menu_screen.png)

## Usage Guide

### LiveSplit

AutoSplit64++ directly communicates with LiveSplit using a Named Pipe. There is no need to manually start the LiveSplit Server.

The dot in the top right corner shows the connection to LiveSplit: green while split detection is connected, grey until it starts, and red if connecting failed. Hover it for the address, and click it to copy the address.

Since AS64+ recognizes the reset only when the Super Mario 64 logo appears, we need to set the Timer to Start at 1.36 seconds.

In LiveSplit `Right-Click -> Edit Splits...` &rarr; Set `Start Timer at:` to **1.36**

#### LiveSplit One

AutoSplit64++ can also control [LiveSplit One](https://one.livesplit.org) (the web timer):

1. In AutoSplit64++, `Settings -> Connection` &rarr; set `Connection Mode` to **LiveSplit One** (the default on macOS). It listens on port `16835` by default. The dot in the top right corner shows the server state (green: connected, amber: waiting for LiveSplit One, red: could not start). Hover it for the URL and click it to copy the URL.
2. In LiveSplit One, `Settings -> Server Connection -> Connect` &rarr; enter `ws://localhost:16835`.
3. Click `OK` to leave LiveSplit One's settings. LiveSplit One ignores timer commands while its settings are open.

In LiveSplit One, `Splits -> Edit` &rarr; Set `Start Timer at` to **1.36**.

### Game Capture

There are 2 options to capture the game:
- **OBS Plugin** (*preffered*)
- **Window Capture** 

#### OBS Plugin

The AutoSplit64+ Grabber OBS plugin sends the gameplay directly to AutoSplit64+ before any modifications are done to it. Changing size, adding effects, overlays, etc. are not captured do not influence the result. 

##### Install Plugin:
- Close OBS
- Copy the plugin file `autosplit64plus-framegrabber.dll` located in `AutpSplit64plus/OBS-Plugin` to your OBS plugin folder
- Usually located in `C:\Program Files\obs-studio\obs-plugins\64bit`
- Open OBS
- Open the Filters Menu of your capture card source (`Right-Click -> Filters`)
- Add (+) Effects Filter and choose `AS64+ Frame Grabber`
![OBS Filter Menu](repo/obs_filters_screen.png)
![OBS Plugin](repo/obs_plugin_screen.png)

- If you have any other Filters applied, make sure `AS64+ Frame Grabber` is at the very top
- Close Filters Menu
##### Setup AutoSplit64++:
- Open the Capture Editor in AutoSplit64++ (`Right-Click -> Edit Coordinates`):

![OBS Plugin Capture](repo/capture_screen_obs.png)

- Check `Use OBS Plugin`
- Pressing `Capture Screen` will update the shown frame.
- Make sure a frame in a bright environment is shown, like the one above.
- Pressing `Auto Detect Region` should correctly position the `Game Region selector` as shown. 

If the region was not detected poperly, adjust the region manually and ensure it is as accurate as possible for best results. When in doubt, its better to select 1-2 pixels into the game as shown above. Selecting even 1 pixel outside of the game area will cause issues!

- Press `Apply` to save changes.

#### Window Capture
Window Capture streams the selected program's window with Windows.Graphics.Capture (the API used by screen sharing apps and OBS), also while the window is covered by other windows. It needs Windows 10 version 1903 or newer; on older versions it takes a screenshot of the window 30 times/second instead.

- On Windows 10, Windows draws a yellow border around a window while it's captured. Windows 11 lets AutoSplit64++ turn it off.
- The whole window is captured, where earlier versions cut it off at the bottom and right, and its framing may differ slightly. If you set up your `Game Region` with an earlier version, check that it still covers only the game.

- Make sure you have your capture software open (i.e.AmaRecTV)
- Open the Capture Editor in AutoSplit64++ (`Right-Click -> Edit Coordinates`):
 
![Window Capture](repo/capture_screen_window.png)

- Uncheck `Use OBS Plugin`
- Select the desired process from the `Process` drop-down.
- Pressing `Capture Screen` will update the shown frame.
- Make sure a frame in a bright environment is shown, like the one above.
- When using AmaRecTV, pressing `Auto Detect Region` should correctly position the `Game Region selector` as shown. 

When capturing another progamm or the region was not detected poperly, adjust the region manually and ensure it is as accurate as possible for best results. When in doubt, its better to select 1-2 pixels into the game as shown above. Selecting even 1 pixel outside of the game area will cause issues!

- Press `Apply` to save changes.

**NOTE:**
If you are using a correctly configured version of AmaRecTV as shown (with windows size at 100% `Right-Click AmaRecTV -> 100%`), the default settings should already be set appropriately.

#### Capture on macOS
On macOS, the Capture Editor's `Source` chooses what to capture. Each source needs its own permission, and the editor only asks for the one of the selected source. While it's missing, the editor shows a button that asks macOS for it, and an `Open System Settings` button in case it was denied before. When running from source, the permissions are for your terminal app instead.

**Video Device** captures a capture card, the OBS Virtual Camera or a webcam. Select it in the `Device` drop-down. It needs the Camera permission.

**Window** streams the emulator window directly with ScreenCaptureKit (the same API used by screen sharing apps), so neither OBS nor a virtual camera is needed. It needs the Screen Recording permission; restart AutoSplit64++ after allowing it if the editor doesn't pick it up.
- The window can be behind other windows, but not minimized.
- Select your emulator in the `Process` drop-down. The capture includes the window's title bar, so make sure the `Game Region` only covers the game.
- Don't resize the emulator window after setting the region. If you do, set the region again.

### Updates
The installed version is shown at the bottom, next to the menu button. Click it to check for an update. With `Check for Updates` on (in `Settings`), AutoSplit64++ also checks when it opens and offers a new version, and a green dot appears next to the version: click it to update.

Updating downloads the new version, checks it, and installs it either right away (AutoSplit64++ restarts) or when you quit. Split detection has to be stopped before updating, in case you're in a run. Your settings, routes and reset templates are kept.

On macOS, each new version needs the Screen Recording and Camera permissions again, as it isn't signed by an Apple developer account.

### Routes

We must let AutoSplit 64 know when we want splits to occur. This can be done by using the Route Editor (`Right-Click -> Edit Route`) to generate route files.

A regular split will trigger when the specified number of stars have been collected, and a set amount of fadeouts or fadeins have occurred after the star count was reached, or the last split occurred.

Every time a star is collected, or a split, undo or skip is triggered, the fadeout and fadein count are reset to 0.
The Route Editor has been designed to look and function similar to the split editor found in LiveSplit to make it as familiar as possible.

**The easiest method of creating routes is to import your splits you use for LiveSplit. To do this, press `Open` in the Route Editor and select the `.lss` file you use with LiveSplit. AutoSplit 64 will attempt to fill in as many details as possible to simplify the route creation process, however it is important you check each split to make sure it is correct.**

## Troubleshooting

If you encounter any issues, please run through all steps below.

- Check capture coordinates are correct (`Right Click -> Edit Coordinates`)
- When using TCP connection, ensure LiveSplit server is running (`Right Click LiveSplit -> Control -> Start Server')
- Check the correct route is loaded, and that the route file is accurate (i.e. correct star counts, fadeout/fadein counts)
- Make sure SRL Mode (Right Click -> SRL Mode) is disabled if you want AutoSplit64 to detect console resets
- Generate reset templates (`Right Click -> Generate Reset Templates`)
- Enlarge your game capture window if it is very small
- Make sure the captures colour settings (i.e. saturation) are default or close to default
- If using an unpowered splitter, compare the whiteness of your star select screens to other players. If it is extremely dull you may need to increase your capture brightness
- Ensure your capture is set to a 4:3 aspect ratio (or close to)

## Development
AutoSplit64++ uses [uv](https://docs.astral.sh/uv/) to manage Python and its dependencies. [Install uv](https://docs.astral.sh/uv/getting-started/installation/), then run these from the repository. uv sets up Python 3.12 and the dependencies from `uv.lock` the first time.

- Start AutoSplit64++: `uv run AutoSplit64.py`
- Run the tests: `uv run python -m unittest`
- Add or update a dependency: `uv add <package>`, which updates `pyproject.toml` and `uv.lock`

### Releases
Releases are versioned by their git tag. Pushing a tag like `v0.4.0` runs the tests and builds the macOS app and the Windows app on GitHub Actions, then publishes them as a GitHub release, with a `SHA256SUMS` file for the updater:

```
git tag v0.4.0
git push origin v0.4.0
```

Tags with a suffix, like `v0.4.0-rc.1`, are published as pre-releases.

### Building
Run `uv run build.py` on the platform you're building for:
- Windows: creates `dist/AutoSplit64++/` with `AutoSplit64++.exe`. Keep the exe together with the other files in that folder.
- macOS: creates `dist/AutoSplit64++.app`. Move it to `Applications` (or anywhere else) to install it.

### macOS (Apple Silicon)
On macOS, the Named Pipe connection and the OBS Plugin are not available. Use the LiveSplit One (or TCP) connection mode.

The app stores its settings, log, routes and reset templates in `~/Library/Application Support/AutoSplit64++/`. Installing a new build keeps them.

## Support
- For help join our [Discord](https://discord.gg/VmrQQBpPSK)

## Credits
Developed with ❤️ by [Davi Be](https://github.com/DaviBe92)

Synozure - [AutoSplit64](https://github.com/Kainev/AutoSplit64)

Gerardo Cervantes - [Star Classifier](https://github.com/gerardocervantes8/Star-Classifier-For-Mario-64)

#### TODO

- RetroSpy integration for reset detection
