# JustDraw

JustDraw is a desktop reference viewer for drawing practice. It combines a timed image viewer, a standalone color-block drill mode, a color-photo study mode, and a protected short-video export tool in one small PyQt app.

## What The App Includes

- `Photo Switching` mode for timed reference rotation
- `Color Blocks` mode for quick palette and shape drills
- `Color Photo` mode for color-study browsing with an optional crystallized look
- per-image zoom / pan / rotation memory
- per-path playback resume, saved image order, and recent-path history
- clipboard and file-explorer helpers
- protected short-video export powered by `ffmpeg` / `ffprobe`
- Windows one-file packaging via PyInstaller and GitHub Actions

## Requirements

- Python 3.x
- `PyQt6` preferred: `pip install PyQt6`
- `PyQt5` fallback: `pip install PyQt5`
- `ffmpeg` + `ffprobe` only if you want protected video export
- `Pillow` is optional when running from source; if it is installed, the exporter uses Pillow-generated watermark / noise assets that more closely match `video-generator`

The app looks for `ffmpeg` / `ffprobe` on `PATH` and in a few common Windows install folders.

## Run From Source

```bash
python justdraw.py
```

Startup notes:
- startup command-line options are not used
- if the active image-based mode does not have a saved source path, the app opens the folder picker after launch
- `Photo Switching` starts paused
- default window size is `840 x 1120`
- default timer value is `90` seconds
- `Stay On Top` defaults to enabled until you toggle it off

## Modes

### Photo Switching

Use this mode for gesture, figure, composition, or reference rotation practice.

Features:
- sequential or random playback
- previous / next navigation
- previous-in-folder / next-in-folder navigation
- configurable countdown timer
- timer pause / resume
- timer end modes for auto-advance, hold, or overtime counting
- optional 3-second pre-start countdown before a timer run starts
- per-path resume for last image, list order, random-play state, and timer settings
- per-image zoom / pan / rotation persistence
- current-image and current-path view-state reset actions
- global horizontal / vertical flip state shared across image-viewing modes

### Color Blocks

This is a standalone color drill view. It does not depend on the current photo source.

Features:
- generates a palette of constrained random colors instead of sampling an input photo
- adjustable color count from `1` to `20`
- luma and saturation thresholds:
  - minimum luma
  - maximum luma
  - minimum saturation
- regular stripe presentation
- irregular `Shape Mode` presentation
- quick refresh for a new palette
- copy helpers:
  - one color copies a single solid patch
  - multiple colors copy a stripe image
- saved color-block settings across launches

### Color Photo

This is a separate image-browsing mode for color study.

Features:
- its own saved source path, recent-path history, last image, and random-play state
- sequential or random browsing
- previous / next navigation
- per-image zoom / pan / rotation persistence
- global horizontal / vertical flip state
- optional `Crystallize` display effect for simplified color reading
- copy image, copy image path, reveal in file explorer, and reset-state actions

## Image Sources

`Set Image Folder...` is available in `Photo Switching` and `Color Photo`.

Supported image sources:
- image files: `.jpg`, `.png`, `.bmp`, `.gif`
- `.zip` files found inside the selected folder tree

Source behavior:
- folders are scanned recursively
- zip archives inside the tree are extracted to temporary folders and their images are included in the browsing list
- zip-backed images can be viewed and copied normally
- `Show In File Explorer` is disabled for zip-backed images
- recent image roots are tracked and exposed through `File -> Recent Paths`
- the recent-path menu returns up to `10` remembered paths
- playback state is separated by playback profile, so `Photo Switching` and `Color Photo` keep independent resume data even for the same folder

## Navigation And View Controls

Mouse controls:
- mouse wheel zooms around the cursor
- left drag pans the image
- double-click resets the current image view state
- right-click opens the mode-specific context menu

Keyboard shortcuts:
- `Ctrl+C`: copy the currently rendered image area
- `PgUp`: previous image
- `PgDown`: next image
- `Space`: pause / resume timer in `Photo Switching`

Photo Switching bottom toolbar:
- previous image
- previous image in the same folder
- flip horizontal
- flip vertical
- rotate `+90`
- rotate `-90`
- next image in the same folder
- next image

Color Photo bottom toolbar:
- previous image
- next image
- crystallize toggle

View-state persistence:
- zoom, pan, and rotation are stored per image and per path
- horizontal / vertical flips are stored globally
- `Reset Current Image State` clears only the active image's saved transform
- `Reset Current Path Image States` clears all saved per-image transforms for the active source path

## Timer Behavior

Timer features apply only to `Photo Switching`.

Controls:
- click the timer display to pause / resume
- `Space` also pauses / resumes
- `Timer -> Set Timer...`
- `Timer -> Reset Timer`
- `Timer -> Random Play`
- `Timer -> 3-second Pre-start Countdown`
- `Timer -> Timer End Mode`

Timer end modes:
- `Auto Next Image`: moves to the next image immediately on expiry
- `Stay On Current Image`: stops at `00:00`
- `Overtime Count Up`: shows `+MM:SS` after expiry

Display behavior:
- paused timer is yellow and blinking
- the final 5 seconds turn red
- hold mode stays at `00:00`
- overtime mode turns red and counts upward after expiry
- opening `Set Timer...` pauses the timer while the popup is open
- if the popup is dismissed without applying a new value, the previous timer state resumes
- when pre-start countdown is enabled, each fresh timer run starts with a full-screen 3-second countdown overlay

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

### Photo Switching Context Menu

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

## Clipboard And Explorer Integration

- `Ctrl+C` or `Copy Image` copies the currently rendered image area, not just the raw file bytes
- `Copy Image Path` copies the current source image path as text
- `Copy Colors` copies either a single swatch image or a stripe image, depending on the current color count
- `Show In File Explorer` reveals the current file when the source is a normal file path
- explorer reveal is intentionally disabled for zip-backed images

## Window Behavior And Feedback

- actions surface short toast notifications inside the UI
- the main window size is remembered
- `Stay On Top` is remembered
- auxiliary protected-video-export windows follow the app-wide `Stay On Top` setting

## Protected Video Export

Protected video export is available when both `ffmpeg` and `ffprobe` are found.

Open it from:
- `Window -> Protected Video Export...`

If the tools are missing:
- the `Window` menu shows an unavailable state
- trying to open the exporter surfaces a toast with the missing-tool reason

Exporter UI behavior:
- uses a separate export-settings window
- uses a separate progress window
- the export button becomes busy while work is running
- the progress window stays quiet while rendering, then comes to the front on success or failure
- auxiliary export windows follow the app's `Stay On Top` setting

Input queue features:
- reorderable multi-video queue
- drag-and-drop video files into the export dialog
- batch export runs one item at a time
- remembers the last queued video list and watermark path
- file pickers prefer the remembered path on the next browse

Supported video input extensions:
- `.mp4`
- `.mov`
- `.mkv`
- `.avi`
- `.webm`
- `.m4v`
- `.wmv`
- `.flv`
- `.ts`
- `.mts`
- `.m2ts`

Watermark and output options:
- output format: `mp4` or `gif`
- centered text watermark or watermark image
- watermark image picker accepts common image formats including `.png`, `.jpg`, `.jpeg`, `.bmp`, `.gif`, and `.webp`
- overlay mode: `Noise Overlay` or `No Overlay`
- optional deletion of the original source file after a successful export
- output file names are generated automatically from processed duration and target seconds, for example `source_000031_15s.mp4`

Export pipeline:
- probes source metadata with `ffprobe`
- removes duplicate frames first with `mpdecimate`
- rebuilds the output to an exact target duration
- uses matching intro / outro still holds around the accelerated main content
- uses 1-second intro / outro holds when the target duration is at least 2 seconds
- applies centered watermark and optional noise overlay in the final render graph
- writes `mp4` output with H.264 / `yuv420p`
- writes `gif` output through a palette generation + palette use pass
- cleans temporary files automatically unless changed in code

Implementation notes:
- the exporter is implemented in `video_tools.py`
- when Pillow is installed, temporary watermark / noise assets are generated with Pillow to better match `video-generator`
- when Pillow is not installed, export still works by falling back to ffmpeg-generated static assets

## Persistence

### Config Storage

When running from source, the app stores state next to the project files.

Important files:
- `justdraw_config.json`
- `justdraw_playback_state.json`

When running as a packaged app:
- Windows: `%APPDATA%\JustDraw\` or `%LOCALAPPDATA%\JustDraw\` fallback behavior depending on availability
- Linux-like systems: `~/.config/JustDraw/`

### What `justdraw_config.json` Stores

- current app mode
- per-mode source paths
- per-mode last image path
- per-mode random-play state
- photo-switching timer seconds
- photo-switching timer end mode
- photo-switching pre-start countdown toggle
- color-block stripe count and thresholds
- color-block shape-mode toggle
- color-photo crystallize toggle
- window size
- stay-on-top flag
- global flip state
- protected video export dialog state

### What `justdraw_playback_state.json` Stores

Per path and per playback profile:
- last image path
- saved image order
- random-play state
- timer seconds
- timer end mode
- last-used timestamp
- per-image zoom / pan / rotation state

## Build A Windows EXE

### Double-click Build

On Windows, run:

`build_windows_exe.bat`

Behavior:
- checks for the `py` launcher
- installs or upgrades `pyinstaller`
- checks for `PyQt6` / `PyQt5`
- installs `PyQt6` automatically if neither Qt package is found
- builds `dist\JustDraw.exe`

### Command-line Build

```bash
py -3 -m pip install --upgrade pyinstaller
py -3 -m pip install --upgrade PyQt6
py -3 build_exe.py
```

`build_exe.py` creates a one-file, windowed PyInstaller build and bundles:
- `main.qml`
- `images/`
- the detected Qt package (`PyQt6` preferred, `PyQt5` fallback)

### GitHub Actions Build

Workflow file:
- `.github/workflows/build-windows-exe.yml`

Behavior:
- manual build: `Actions -> Build Windows EXE -> Run workflow`
- release build: push a tag like `v1.2.0`
- prerelease build: push a tag like `v1.0.0-beta.1` or `v1.0.0-rc.1`
- uses `windows-latest`
- uses Python `3.12`
- installs `pyinstaller`, `PyQt6`, and `Pillow`
- uploads:
  - `dist/JustDraw.exe`
  - `dist/JustDraw.exe.sha256`
- tag builds also attach both files to the GitHub Release automatically
- tags containing `-` are published as GitHub prereleases automatically

## Project Layout

- `justdraw.py` - PyQt backend, dialogs, timer control, clipboard helpers, explorer integration, and export orchestration
- `main.qml` - the main UI, menus, viewports, toolbars, popups, and toast notifications
- `images.py` - image-source scanning, ZIP handling, playback persistence, timer state, and mode-scoped config
- `video_tools.py` - `ffmpeg` / `ffprobe` helpers and protected-video export pipeline
- `build_exe.py` - PyInstaller one-file build entry point
- `build_windows_exe.bat` - Windows helper script for local EXE packaging
- `.github/workflows/build-windows-exe.yml` - GitHub Actions workflow for Windows build artifacts and tagged releases

## License

See `LICENSE`.
