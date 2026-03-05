# JustDraw!
This tool helps artists practice gesture drawing with images on local storage.

## 1. Requirements

- Python 3.x: https://www.python.org/getit/
- PyQt6 (preferred): `pip install PyQt6`
- PyQt5 fallback (if PyQt6 is unavailable): `pip install PyQt5`

## 2. Run

```bash
python justdraw.py
```

- Startup command-line parameters were removed.
- If no valid image source is saved, the app opens the folder picker after startup.

## 3. Image Source

- Use `File -> Set Image Folder...` to choose an image folder.
- The folder is scanned recursively for supported image files:
  - `.jpg`, `.png`, `.bmp`, `.gif`
- `.zip` files found in the selected folder are also included as image sources.

## 4. Navigation

- Bottom control panel keeps 4 image-switch buttons:
  - previous image
  - previous image in same folder
  - next image in same folder
  - next image
- Keyboard shortcuts:
  - `PgUp`: previous image
  - `PgDown`: next image
  - `Space`: pause/resume timer

## 5. Image View Controls

- Mouse wheel zooms the image (zoom center follows mouse position).
- Left mouse drag pans the image.
- Bottom bar provides quick transform controls:
  - `H`
  - `V`
  - `+90`
  - `-90`
- These 4 transform buttons are in the same row, between previous/next navigation buttons.
- Double-click image: reset current image state.
- Image state is remembered per image path:
  - zoom scale
  - pan offsets
  - rotation (multiples of 90 degrees)
- Horizontal/vertical flip are global settings (shared across all images and remembered in config).

## 6. Timer

- Click timer (top-right) to pause/resume.
- Timer starts in paused state after launch.
- Set timer value from `Timer -> Set Timer...`.
- Right-click menu always provides `Reset Timer`.
- Opening `Set Timer...` temporarily pauses the timer.
- If the dialog closes without applying a new value, timer resumes.

Timer end modes (`Timer -> Timer End Mode`):

- `Auto Next Image`: switch to next image when countdown reaches `00:00`.
- `Stay On Current Image`: stay on current image; timer turns red and blinks.
- `Overtime Count Up`: after countdown ends, timer becomes two lines:
  - line 1: configured timer value
  - line 2: overtime value (`+mm:ss`) in red

Paused timer behavior:

- Displays current numeric time (not `PAUSE`).
- Text color is yellow and blinking.

## 7. Menus

### File menu

- `Set Image Folder...`
- `Recent Paths`
- `Delete Path Playback State...`
- `Refresh List Order + Random Image`
  - In random mode: reshuffles current list and jumps to a random image.
  - In sequence mode: jumps to a random image.
- `Reset Current Path Image States`

### Timer menu

- `Set Timer...`
- `3-second Pre-start Countdown` (checkbox)
- `Timer End Mode`

When `3-second Pre-start Countdown` is enabled:

- before each timer start, a full-screen `3 -> 2 -> 1` countdown is shown
- resuming from pause also runs the same `3 -> 2 -> 1` countdown
- the normal image timer starts after that countdown finishes

### Right-click menu

- `Reset Timer`
- `Random Play` (checkbox)
- `Stay On Top` (checkbox)
- `Copy Image`
- `Copy Image Path`
- `Show In File Explorer` (hidden for zip-backed images)
- `Reset Current Image State`

## 8. Clipboard and Explorer

- `Ctrl+C` (window focused): copy currently visible image area in the window to clipboard.
- `Copy Image`: same behavior as `Ctrl+C`.
- `Copy Image Path`: copy current image file path text.
- `Show In File Explorer`: reveal current image in system file explorer (only for non-zip images).

## 9. Toast Notifications

- Actions show a semi-transparent toast message.
- If a new action happens while toast is visible, toast text is immediately replaced with the latest action.

## 10. Window Size

- Default window size: `840x1120`.
- Resized window size is remembered.

## 11. Persistence Files

### `justdraw_config.json` (project root)
Stores global settings:

- last image source path
- window width and height
- timer seconds
- playback mode (`sequential` / `random`)
- stay-on-top mode
- timer end mode
- last image path

### `justdraw_playback_state.json` (project root)
Stores per-path playback data:

- last image path
- playback mode
- timer seconds
- timer end mode
- per-image view states
- global flip settings
- recent usage timestamp
