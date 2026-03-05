import os
import subprocess
import sys
import tempfile
import time

# Avoid Windows style plugin dependency issues in some PyQt6 installations.
os.environ.setdefault('QT_QUICK_CONTROLS_STYLE', 'Basic')

try:
    from PyQt6.QtQml import QQmlApplicationEngine
    from PyQt6.QtGui import QImage, QIcon
    from PyQt6.QtCore import QTimer, QObject, QUrl, pyqtSignal, pyqtSlot
    from PyQt6.QtWidgets import QApplication, QFileDialog, QInputDialog
except ImportError:
    from PyQt5.QtQml import QQmlApplicationEngine
    from PyQt5.QtGui import QImage, QIcon
    from PyQt5.QtCore import QTimer, QObject, QUrl, pyqtSignal, pyqtSlot
    from PyQt5.QtWidgets import QApplication, QFileDialog, QInputDialog

from images import ImageList

print(os.getcwd())
app_dir = os.path.dirname(os.path.realpath(__file__))

imgList = ImageList()
imgList.load()

app = QApplication(sys.argv)
app.setWindowIcon(QIcon('./images/icon.png'))

engine = QQmlApplicationEngine()
engine.quit.connect(app.quit)
engine.load(QUrl.fromLocalFile(os.path.join(app_dir, 'main.qml')))

if len(engine.rootObjects()) == 0:
    print('Failed to load QML UI (main.qml).')
    sys.exit(-1)


class Backend(QObject):
    # update timer value in the upper right corner
    setcurtimer = pyqtSignal(str, str, arguments=['cur_timer, color'])

    # set current image
    setcurimage = pyqtSignal(str, arguments=['img_path'])

    # set current image flipped horizontally
    setcurimagemirror = pyqtSignal(str, arguments=['img_path'])

    # set window size from command line parameters
    setwindowsize = pyqtSignal(int, int, arguments=['w, h'])

    # set play mode text in UI: RND or SEQ
    setplaymode = pyqtSignal(str, arguments=['mode'])

    # set current timer seconds value in UI editor
    settimervalue = pyqtSignal(int, arguments=['seconds'])

    # set always-on-top mode in UI
    setstayontop = pyqtSignal(bool, arguments=['enabled'])

    # set timer end mode: auto_next / hold / overtime
    settimerendmode = pyqtSignal(str, arguments=['mode'])

    # set whether timer is currently expired and waiting on current image
    settimerexpiredhold = pyqtSignal(bool, arguments=['enabled'])

    # set paused state to drive UI style/animation
    settimerpaused = pyqtSignal(bool, arguments=['enabled'])

    # restore per-image view state (scale, offsets and flip states) from persisted path state
    setimageviewstate = pyqtSignal(
        float, float, float, bool, bool, int, bool,
        arguments=['scale, offset_x, offset_y, flip_horizontal, flip_vertical, rotation, has_state']
    )

    # whether current image can be revealed in file explorer (hidden for zip-backed images)
    setcanrevealinexplorer = pyqtSignal(bool, arguments=['enabled'])

    # set whether 3-second pre-start countdown is enabled
    setprestartenabled = pyqtSignal(bool, arguments=['enabled'])

    # set full-screen pre-start countdown state
    setprestartcountdown = pyqtSignal(int, bool, arguments=['seconds, active'])

    def __init__(self):
        super().__init__()

        # Define timer.
        self.timer = QTimer()
        self.timer.setInterval(1000)
        self.timer.timeout.connect(self.set_cur_timer)
        self.timer.start()
        self.prestart_active = False
        self.prestart_pending = False
        self.prestart_remaining = 0

    def restart_timer_tick_phase(self):
        # Ensure the next decrement happens one full interval after user-triggered resets.
        self.timer.start()

    def clear_prestart_countdown(self):
        self.prestart_active = False
        self.prestart_remaining = 0
        self.setprestartcountdown.emit(0, False)

    def start_prestart_countdown(self):
        global imgList
        if not imgList.isPrestartCountdownEnabled() or imgList.isTimerPaused() or not imgList.hasImages():
            return False

        self.prestart_pending = False
        self.prestart_active = True
        self.prestart_remaining = 3
        self.setprestartcountdown.emit(self.prestart_remaining, True)
        self.restart_timer_tick_phase()
        return True

    def arm_prestart_countdown(self):
        global imgList
        if not imgList.isPrestartCountdownEnabled() or not imgList.hasImages():
            self.prestart_pending = False
            self.clear_prestart_countdown()
            return False

        self.prestart_pending = True
        self.clear_prestart_countdown()
        if not imgList.isTimerPaused():
            self.start_prestart_countdown()
        return True

    def schedule_timer_start(self):
        global imgList
        if self.arm_prestart_countdown():
            self.emit_timer_visual_state(imgList.getCurTimer(False))
            return

        self.restart_timer_tick_phase()
        self.emit_timer_visual_state()

    def emit_timer_visual_state(self, cur_timer=None):
        global imgList
        timer_value = cur_timer if cur_timer is not None else imgList.getCurTimer(False)
        self.setcurtimer.emit(timer_value, imgList.getCurTimerColor())
        self.settimerexpiredhold.emit(imgList.isTimerExpiredHold())
        self.settimerpaused.emit(imgList.isTimerPaused())

    def emit_image_view_state(self):
        global imgList
        view_state = imgList.getCurrentImageViewState()
        self.setcanrevealinexplorer.emit(imgList.canRevealCurrentImageInExplorer())
        if not view_state:
            self.setimageviewstate.emit(1.0, 0.0, 0.0, False, False, 0, False)
            return

        self.setimageviewstate.emit(
            float(view_state.get('scale', 1.0)),
            float(view_state.get('offset_x', 0.0)),
            float(view_state.get('offset_y', 0.0)),
            bool(view_state.get('mirror', False)),
            bool(view_state.get('flip_vertical', False)),
            int(view_state.get('rotation', 0)),
            True
        )

    def set_cur_timer(self):
        global imgList

        if self.prestart_active:
            if imgList.isTimerPaused():
                self.clear_prestart_countdown()
                self.emit_timer_visual_state(imgList.getCurTimer(False))
                return

            self.prestart_remaining -= 1
            if self.prestart_remaining > 0:
                self.setprestartcountdown.emit(self.prestart_remaining, True)
            else:
                self.clear_prestart_countdown()
                # Keep one full second between end of pre-countdown and first decrement.
                self.restart_timer_tick_phase()

            self.emit_timer_visual_state(imgList.getCurTimer(False))
            return

        if self.prestart_pending and imgList.isPrestartCountdownEnabled() and not imgList.isTimerPaused():
            self.start_prestart_countdown()
            self.emit_timer_visual_state(imgList.getCurTimer(False))
            return

        cur_timer = imgList.getCurTimer()

        if cur_timer == 'expired':
            # set new image
            self.reload()
            self.schedule_timer_start()
            return

        self.emit_timer_visual_state(cur_timer)

    def windowsize(self):
        global imgList
        self.setwindowsize.emit(imgList.getWindowWidth(), imgList.getWindowHeight())

    def play_mode(self):
        global imgList
        self.setplaymode.emit('RND' if imgList.isRandomPlayMode() else 'SEQ')

    def timer_value(self):
        global imgList
        self.settimervalue.emit(imgList.getTimerSeconds())

    def timer_end_mode(self):
        global imgList
        self.settimerendmode.emit(imgList.getTimerEndMode())
        self.settimerexpiredhold.emit(imgList.isTimerExpiredHold())

    def prestart_countdown_enabled(self):
        global imgList
        self.setprestartenabled.emit(imgList.isPrestartCountdownEnabled())

    def initialize_current_image(self):
        global imgList

        if not imgList.hasImages():
            return

        imgList.change(1)
        self.reload()
        self.restart_timer_tick_phase()
        self.prestart_pending = imgList.isPrestartCountdownEnabled()
        self.clear_prestart_countdown()
        self.emit_timer_visual_state()

    def stay_on_top(self):
        global imgList
        self.setstayontop.emit(imgList.isStayOnTop())

    @pyqtSlot(str, str, result=bool)
    def save_window_size(self, width, height):
        global imgList

        try:
            width_int = int(width)
            height_int = int(height)
        except (TypeError, ValueError):
            print('Invalid window size: {0}x{1}'.format(width, height))
            return False

        if not imgList.setDefaultWindowSize(width_int, height_int):
            print('Window size must be positive: {0}x{1}'.format(width_int, height_int))
            return False

        return True

    @pyqtSlot(result=bool)
    def select_image_root_path(self):
        global imgList

        root = engine.rootObjects()[0] if len(engine.rootObjects()) > 0 else None
        was_stay_on_top = False
        if root is not None:
            try:
                was_stay_on_top = bool(root.property('stayOnTop'))
            except Exception:
                was_stay_on_top = False

        # Native folder picker can appear behind an always-on-top window on Windows.
        if root is not None and was_stay_on_top:
            root.setProperty('stayOnTop', False)
            app.processEvents()

        default_path = imgList.getImageRootPath() if imgList.getImageRootPath() else os.path.expanduser('~')
        try:
            folder = QFileDialog.getExistingDirectory(None, 'Select Image Folder', default_path)
        finally:
            if root is not None and was_stay_on_top:
                root.setProperty('stayOnTop', True)

        if not folder:
            return False

        if not imgList.setImageRootPath(folder):
            print('Invalid image folder or no supported images: {0}'.format(folder))
            return False

        self.settimervalue.emit(imgList.getTimerSeconds())
        self.setplaymode.emit('RND' if imgList.isRandomPlayMode() else 'SEQ')
        self.settimerendmode.emit(imgList.getTimerEndMode())
        self.reload()
        self.schedule_timer_start()
        return True

    @pyqtSlot(str, result=bool)
    def set_image_root_path(self, path):
        global imgList

        if not imgList.setImageRootPath(path):
            return False

        self.settimervalue.emit(imgList.getTimerSeconds())
        self.setplaymode.emit('RND' if imgList.isRandomPlayMode() else 'SEQ')
        self.settimerendmode.emit(imgList.getTimerEndMode())
        self.reload()
        self.schedule_timer_start()
        return True

    @pyqtSlot(result='QStringList')
    def get_recent_image_paths(self):
        global imgList
        return imgList.getRecentPlaybackPaths(10)

    def reload(self, mirror=False):
        global imgList

        if mirror:
            self.setcurimagemirror.emit(QUrl.fromLocalFile(imgList.getImagePath()).toString())
        else:
            self.setcurimage.emit(QUrl.fromLocalFile(imgList.getImagePath()).toString())
        self.emit_image_view_state()

    @pyqtSlot()
    def prev_in_folder(self):
        global imgList
        imgList.change(-2)
        self.reload()
        self.schedule_timer_start()

    @pyqtSlot()
    def prev(self):
        global imgList
        imgList.change(-1)
        self.reload()
        self.schedule_timer_start()

    @pyqtSlot()
    def next(self):
        global imgList
        imgList.change(1)
        self.reload()
        self.schedule_timer_start()

    @pyqtSlot()
    def next_in_folder(self):
        global imgList
        imgList.change(2)
        self.reload()
        self.schedule_timer_start()

    @pyqtSlot()
    def pause(self):
        global imgList
        imgList.pause()
        if imgList.isTimerPaused():
            if imgList.isPrestartCountdownEnabled() and imgList.hasImages():
                # When resuming later, run full pre-start countdown again.
                self.prestart_pending = True
            if self.prestart_active:
                self.clear_prestart_countdown()
        elif imgList.isPrestartCountdownEnabled() and imgList.hasImages():
            self.prestart_pending = True
            self.start_prestart_countdown()
        elif self.prestart_pending:
            self.start_prestart_countdown()
        self.emit_timer_visual_state()

    @pyqtSlot()
    def reset_timer(self):
        global imgList
        imgList.resetTimer()
        self.schedule_timer_start()
        self.settimervalue.emit(imgList.getTimerSeconds())

    @pyqtSlot(result=bool)
    def reset_image_order_and_pick_random(self):
        global imgList
        if not imgList.resetImageOrderAndPickRandom():
            return False

        self.reload()
        self.schedule_timer_start()
        return True

    @pyqtSlot(result=bool)
    def reset_current_path_image_states(self):
        global imgList
        if not imgList.clearCurrentPathImageViewStates():
            return False

        self.emit_image_view_state()
        return True

    @pyqtSlot(result=bool)
    def reset_current_image_state(self):
        global imgList
        if not imgList.clearCurrentImageViewState():
            return False

        self.emit_image_view_state()
        return True

    @pyqtSlot(result=bool)
    def reveal_current_image_in_explorer(self):
        global imgList

        if not imgList.canRevealCurrentImageInExplorer():
            return False

        image_path = imgList.getImagePath()
        if not image_path:
            return False

        try:
            if sys.platform.startswith('win'):
                windows_path = os.path.normpath(image_path).replace('/', '\\')
                # Explorer selection is unreliable for UNC/NAS paths.
                # For network shares, open the containing folder directly.
                if windows_path.startswith('\\\\'):
                    folder_path = os.path.dirname(windows_path)
                    subprocess.Popen(['explorer.exe', folder_path if folder_path else windows_path])
                else:
                    subprocess.Popen(['explorer.exe', '/select,', windows_path])
            elif sys.platform == 'darwin':
                subprocess.Popen(['open', '-R', image_path])
            else:
                subprocess.Popen(['xdg-open', os.path.dirname(image_path)])
        except Exception:
            return False

        return True

    @pyqtSlot(str)
    def set_timer_value(self, seconds):
        global imgList

        try:
            seconds_int = int(seconds)
        except (TypeError, ValueError):
            print('Invalid timer value: {0}'.format(seconds))
            return

        if not imgList.setTimerSeconds(seconds_int):
            print('Timer value must be positive')
            return

        self.settimervalue.emit(imgList.getTimerSeconds())
        self.schedule_timer_start()

    @pyqtSlot()
    def toggle_prestart_countdown_enabled(self):
        global imgList
        enabled = imgList.togglePrestartCountdownEnabled()
        self.setprestartenabled.emit(enabled)

        if enabled:
            self.arm_prestart_countdown()
            self.emit_timer_visual_state(imgList.getCurTimer(False))
        else:
            self.prestart_pending = False
            self.clear_prestart_countdown()
            self.emit_timer_visual_state(imgList.getCurTimer(False))

    @pyqtSlot()
    def toggle_play_mode(self):
        global imgList
        self.setplaymode.emit('RND' if imgList.togglePlayMode() else 'SEQ')

    @pyqtSlot()
    def toggle_stay_on_top(self):
        global imgList
        self.setstayontop.emit(imgList.toggleStayOnTop())

    @pyqtSlot(str)
    def set_timer_end_mode(self, mode):
        global imgList
        advanced = imgList.setTimerEndMode(mode)
        self.settimerendmode.emit(imgList.getTimerEndMode())
        if advanced:
            self.reload()
        self.emit_timer_visual_state()

    @pyqtSlot(str, str, str, str, str, str, result=bool)
    def save_image_view_state(self, scale, offset_x, offset_y, flip_horizontal, flip_vertical, rotation):
        global imgList
        return imgList.saveCurrentImageViewState(scale, offset_x, offset_y, flip_horizontal, flip_vertical, rotation)

    @pyqtSlot(result=bool)
    def delete_path_playback_state(self):
        global imgList

        paths = imgList.getSavedPlaybackPaths()
        if len(paths) == 0:
            print('No saved path playback state found.')
            return False

        selected_path, ok = QInputDialog.getItem(
            None,
            'Delete Path Playback State',
            'Select path to delete:',
            paths,
            0,
            False
        )

        if not ok or not selected_path:
            return False

        if not imgList.deletePlaybackState(selected_path):
            return False

        print('Deleted path playback state: {0}'.format(selected_path))
        return True

    @pyqtSlot()
    def mirror(self):
        self.reload(mirror=True)

    @pyqtSlot(result=bool)
    def copy(self):
        global imgList

        image = QImage(imgList.getImagePath())
        if image.isNull():
            return False

        app.clipboard().setImage(image)
        return True

    @pyqtSlot(str, result=bool)
    def copy_rendered_image(self, rendered_image_url):
        if not rendered_image_url:
            return False

        local_path = QUrl(rendered_image_url).toLocalFile()
        if not local_path:
            # Accept plain local paths from QML saveToFile as well.
            local_path = str(rendered_image_url)
        if not local_path:
            return False

        image = QImage(local_path)
        if image.isNull():
            return False

        app.clipboard().setImage(image)
        return True

    @pyqtSlot(result=str)
    def allocate_temp_capture_path(self):
        temp_dir = tempfile.gettempdir()
        file_name = 'justdraw_capture_{0}.png'.format(int(time.time() * 1000))
        return os.path.join(temp_dir, file_name)

    @pyqtSlot(result=bool)
    def copy_image_path(self):
        global imgList

        image_path = imgList.getImagePath()
        if not image_path:
            return False

        app.clipboard().setText(image_path)
        return True


# define our backend object, which we pass to QML
backend = Backend()

# some pyqt magic
engine.rootObjects()[0].setProperty('backend', backend)

# apply window size from command line
backend.windowsize()
backend.play_mode()
backend.timer_value()
backend.stay_on_top()
backend.timer_end_mode()
backend.prestart_countdown_enabled()

if imgList.hasImages():
    backend.initialize_current_image()

# start in paused mode; click timer once to begin playback
backend.pause()


def save_session_state():
    global imgList
    imgList.saveResumeState()


app.aboutToQuit.connect(save_session_state)

def prompt_for_image_folder_if_needed():
    if imgList.hasImages():
        return

    print('Opening image folder picker...')
    backend.select_image_root_path()


# Run folder picker after UI is shown to avoid startup freeze/hang.
QTimer.singleShot(0, prompt_for_image_folder_if_needed)

sys.exit(app.exec())
