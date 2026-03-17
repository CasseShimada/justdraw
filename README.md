# JustDraw!

JustDraw is a desktop reference viewer for drawing practice. It supports timed photo switching, color-block reduction studies, color-photo studies, per-image view memory, and protected short video export.

## Requirements

- Python 3.x
- PyQt6 preferred: `pip install PyQt6`
- PyQt5 fallback: `pip install PyQt5`
- `ffmpeg` + `ffprobe` only if you want protected video export

The app looks for `ffmpeg` / `ffprobe` on `PATH` and in a few common Windows install folders.

## Run

```bash
python justdraw.py
```

Notes:
- Startup command-line options are no longer used.
- If no saved image source is available for the current mode, the app opens the folder picker after launch.
- The timer starts paused in `Photo Switching` mode.

## Build A Windows EXE

### Double-click build

On Windows, run:

`build_windows_exe.bat`

Output:

`dist\JustDraw.exe`

### Command-line build

```bash
py -3 -m pip install --upgrade pyinstaller
py -3 build_exe.py
```

The build bundles:
- `main.qml`
- `images/`

## Core Modes

### Photo Switching

Timed image rotation for gesture, figure, or composition practice.

Features:
- countdown timer with pause/resume
- sequential or random playback
- recent-path switching
- per-path playback restore
- per-image zoom / pan / rotation restore

### Color Blocks

Reduces the current reference into simplified color masses for value and color-shape study.

Features:
- adjustable stripe / color count
- min luma, max luma, and min saturation thresholds
- optional shape mode
- copy generated color blocks to the clipboard

### Color Photo

Uses the original image as a color-study reference with the same navigation and transform tools as photo mode.

Features:
- sequential or random playback
- optional crystallize effect
- per-image zoom / pan / rotation restore
- flip / rotate / copy / reveal actions

## Image Sources

Use `File -> Set Image Folder...` in photo-based modes.

Supported sources:
- image files: `.jpg`, `.png`, `.bmp`, `.gif`
- `.zip` files found inside the selected folder tree

Behavior:
- folders are scanned recursively
- recent paths are tracked per playback profile
- playback progress and list order are restored per path
- zip-backed images can be viewed normally, but `Show In File Explorer` is hidden for them

## Navigation And View Controls

Bottom toolbar:
- previous image
- previous image in same folder
- next image in same folder
- next image
- flip horizontal
- flip vertical
- rotate `-90`
- rotate `+90`
- copy image
- info / utility actions depending on mode

Mouse:
- mouse wheel zooms
- left drag pans
- double-click resets the current image view state

Keyboard shortcuts:
- `Ctrl+C`: copy the currently visible image area
- `PgUp`: previous image
- `PgDown`: next image
- `Space`: pause / resume timer in `Photo Switching`

View persistence:
- zoom, pan, and rotation are stored per image
- horizontal / vertical flip are stored globally
- current path image states can be reset without affecting other paths

## Timer Behavior

Available in `Photo Switching` mode.

Controls:
- click the timer to pause / resume
- `Timer -> Set Timer...`
- `Timer -> Reset Timer`
- `Timer -> Random Play`
- `Timer -> 3-second Pre-start Countdown`

Timer end modes:
- `Auto Next Image`
- `Stay On Current Image`
- `Overtime Count Up`

Details:
- opening `Set Timer...` temporarily pauses the timer
- if no new value is applied, the timer resumes
- paused timer stays numeric and blinks yellow
- hold mode turns the timer red and blinking at expiry
- overtime mode shows the configured time plus a red overtime counter
- optional pre-start countdown runs before each timer start and after resuming

## Menus

### File

Visible in `Photo Switching` and `Color Photo`.

- `Set Image Folder...`
- `Recent Paths`
- `Delete Path Playback State...`
- `Refresh List Order + Random Image`
- `Reset Current Path Image States`

### Window

- `Protected Video Export...`
- `Stay On Top`

### Mode

- `Photo Switching`
- `Color Blocks`
- `Color Photo`

### Timer

Visible in `Photo Switching`.

- `Pause Timer` / `Resume Timer`
- `Set Timer...`
- `Reset Timer`
- `Random Play`
- `3-second Pre-start Countdown`
- `Timer End Mode`

### Color Sense Tools

Visible in `Color Blocks`.

- `Increase Colors`
- `Decrease Colors`
- `Refresh Colors`
- `Copy Colors`
- `Shape Mode`
- `Set Min Luma...`
- `Set Max Luma...`
- `Set Min Saturation...`

## Context Menus

### Photo / Image Context Menu

- pause / resume timer
- reset timer
- random play
- set image folder
- random image
- copy image
- copy image path
- show in file explorer
- reset current image state
- reset current path image states
- flip horizontal / vertical
- rotate `-90` / `+90`
- stay on top

### Color Blocks Context Menu

- increase / decrease colors
- refresh colors
- copy colors
- shape mode
- threshold editing
- stay on top

### Color Photo Context Menu

- set image folder
- random play
- next random photo
- copy image
- copy image path
- show in file explorer
- reset current image state
- reset current path image states
- flip horizontal / vertical
- rotate `-90` / `+90`
- crystallize
- stay on top

## Protected Video Export

Protected video export is available when both `ffmpeg` and `ffprobe` are found.

Open it from:
- `Window -> Protected Video Export...`

Current behavior:
- opens a dedicated export settings window, separate from the main app window
- uses a separate progress window during export
- the export progress window stays quiet in the background while rendering
- the progress window comes to the front when export completes or fails
- supports a reorderable multi-video queue and exports each item one by one
- lets you choose `mp4` or `gif` output format
- can optionally delete each source video after its export succeeds
- remembers the last selected source-video queue and watermark path
- file pickers prefer the remembered path on the next browse

Export pipeline:
- uses the `video-generator`-style protected export flow
- removes duplicate frames from the source first
- outputs an auto-named file like `source_HHMMSS_15s.mp4` or `source_HHMMSS_15s.gif`
- creates a 1-second intro hold before the accelerated main content
- shows the final frame once at the very end
- applies watermark before the intro-to-main transition
- supports centered watermark text or watermark image
- supports optional noise overlay
- cleans temporary files automatically unless changed in code

## Clipboard And Explorer

- `Ctrl+C` or `Copy Image` copies the currently visible rendered image area
- `Copy Image Path` copies the source image path as text
- `Show In File Explorer` reveals the current file in the system file manager
- explorer reveal is disabled for zip-backed images

## Notifications And Window Behavior

- actions use toast notifications
- the main window size is remembered
- stay-on-top is remembered
- auxiliary export windows follow the stay-on-top setting

## Persistence

### `justdraw_config.json`

Stores app-wide and mode-scoped settings such as:
- current app mode
- saved image source paths per mode
- last image path per mode
- random play mode per mode
- timer seconds
- timer end mode
- pre-start countdown
- color-block settings
- color-photo crystallize setting
- window size
- stay-on-top
- global flip state
- protected video export form state

### `justdraw_playback_state.json`

Stores per-path playback data such as:
- last image path
- restored image order for that path
- random play mode
- timer seconds
- timer end mode
- recent usage timestamp
- per-image view states

When running from source, these files are saved in the project folder.
When running as a packaged app, they are saved under the app data directory, for example on Windows:

- `%APPDATA%\JustDraw\`
