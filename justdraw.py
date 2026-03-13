import json
import logging
import os
import subprocess
import sys
import tempfile
import threading
import time

# Avoid Windows style plugin dependency issues in some PyQt6 installations.
os.environ.setdefault('QT_QUICK_CONTROLS_STYLE', 'Basic')

try:
    from PyQt6.QtQml import QQmlApplicationEngine
    from PyQt6.QtGui import QColor, QFont, QImage, QIcon, QPainter
    from PyQt6.QtCore import QTimer, QObject, QRectF, QUrl, Qt, QtMsgType, pyqtSignal, pyqtSlot, qInstallMessageHandler
    from PyQt6.QtWidgets import QApplication, QFileDialog, QInputDialog
except ImportError:
    from PyQt5.QtQml import QQmlApplicationEngine
    from PyQt5.QtGui import QColor, QFont, QImage, QIcon, QPainter
    from PyQt5.QtCore import QTimer, QObject, QRectF, QUrl, Qt, QtMsgType, pyqtSignal, pyqtSlot, qInstallMessageHandler
    from PyQt5.QtWidgets import QApplication, QFileDialog, QInputDialog

from images import ImageList
import video_tools

print(os.getcwd())


def get_log_file_path():
    log_dir = os.path.join(os.getcwd(), 'log.')
    os.makedirs(log_dir, exist_ok=True)
    return os.path.join(log_dir, 'latest.log')


LOG_FILE_PATH = get_log_file_path()


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE_PATH, mode='w', encoding='utf-8')
    ]
)

logger = logging.getLogger('justdraw')
logger.info('Application startup')
logger.info('Working directory: %s', os.getcwd())
logger.info('Log file: %s', LOG_FILE_PATH)


def qt_message_handler(msg_type, context, message):
    if msg_type == QtMsgType.QtDebugMsg:
        level = logging.DEBUG
    elif msg_type == QtMsgType.QtInfoMsg:
        level = logging.INFO
    elif msg_type == QtMsgType.QtWarningMsg:
        level = logging.WARNING
    elif msg_type == QtMsgType.QtCriticalMsg:
        level = logging.ERROR
    else:
        level = logging.CRITICAL

    file_name = getattr(context, 'file', '') or ''
    line_no = getattr(context, 'line', 0) or 0
    function_name = getattr(context, 'function', '') or ''
    logger.log(level, 'QT %s:%s %s | %s', file_name, line_no, function_name, message)


qInstallMessageHandler(qt_message_handler)


def get_app_resource_dir():
    if getattr(sys, 'frozen', False):
        # PyInstaller onefile extracts bundled files to this directory.
        return getattr(sys, '_MEIPASS', os.path.dirname(sys.executable))
    return os.path.dirname(os.path.realpath(__file__))


app_dir = get_app_resource_dir()

imgList = ImageList()
imgList.load()

app = QApplication(sys.argv)
app.setWindowIcon(QIcon(os.path.join(app_dir, 'images', 'icon.png')))

engine = QQmlApplicationEngine()
engine.quit.connect(app.quit)
engine.load(QUrl.fromLocalFile(os.path.join(app_dir, 'main.qml')))

if len(engine.rootObjects()) == 0:
    print('Failed to load QML UI (main.qml).')
    logger.error('Failed to load QML UI (main.qml)')
    sys.exit(-1)


def log_qml_warnings(warnings):
    for warning in warnings:
        try:
            logger.warning('QML warning: %s', warning.toString())
        except Exception:
            logger.warning('QML warning: %r', warning)


if hasattr(engine, 'warnings'):
    try:
        engine.warnings.connect(log_qml_warnings)
    except Exception:
        logger.exception('Failed to attach QML warning logger')


class Backend(QObject):
    # update timer value in the upper right corner
    setcurtimer = pyqtSignal(str, str, arguments=['cur_timer, color'])

    # set current image
    setcurimage = pyqtSignal(str, arguments=['img_path'])

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

    # restore per-image view state (scale, offsets and rotation) from persisted path state
    setimageviewstate = pyqtSignal(
        float, float, float, int, bool,
        arguments=['scale, offset_x, offset_y, rotation, has_state']
    )

    # restore global flip settings from config
    setglobalflipstate = pyqtSignal(bool, bool, arguments=['flip_horizontal, flip_vertical'])

    # whether current image can be revealed in file explorer (hidden for zip-backed images)
    setcanrevealinexplorer = pyqtSignal(bool, arguments=['enabled'])

    # set whether 3-second pre-start countdown is enabled
    setprestartenabled = pyqtSignal(bool, arguments=['enabled'])

    # set full-screen pre-start countdown state
    setprestartcountdown = pyqtSignal(int, bool, arguments=['seconds, active'])

    # set whether color practice mode is enabled
    setcolorpracticeenabled = pyqtSignal(bool, arguments=['enabled'])

    # set current color-practice sub-mode: palette / photo
    setcolorpracticesubmode = pyqtSignal(str, arguments=['mode'])

    # set current app mode: photo_switching / color_blocks / color_photo
    setappmode = pyqtSignal(str, arguments=['mode'])

    # set color-practice color thresholds
    setcolorpracticethresholds = pyqtSignal(
        float, float, float,
        arguments=['min_luma, max_luma, min_saturation']
    )

    # set color-blocks settings (stripe count + thresholds)
    setcolorblocksettings = pyqtSignal(
        int, float, float, float,
        arguments=['stripe_count, min_luma, max_luma, min_saturation']
    )

    # set color-blocks shape mode toggle
    setcolorblockshapemodeenabled = pyqtSignal(bool, arguments=['enabled'])

    # set color-photo crystallize toggle
    setcolorphotocrystallizeenabled = pyqtSignal(bool, arguments=['enabled'])

    # set ffmpeg-based export availability/busy state
    setprotectedvideoexportavailable = pyqtSignal(bool, arguments=['enabled'])
    setprotectedvideoexportbusy = pyqtSignal(bool, arguments=['enabled'])

    # surface backend status messages to QML toast
    showtoast = pyqtSignal(str, arguments=['message'])

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
        self.image_source_prompt_pending = False
        self.video_tools = video_tools.find_ffmpeg_tools()
        self.video_export_busy = False
        self.video_export_thread = None

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
            self.setimageviewstate.emit(1.0, 0.0, 0.0, 0, False)
            return

        self.setimageviewstate.emit(
            float(view_state.get('scale', 1.0)),
            float(view_state.get('offset_x', 0.0)),
            float(view_state.get('offset_y', 0.0)),
            int(view_state.get('rotation', 0)),
            True
        )

    def emit_global_flip_state(self):
        global imgList
        self.setglobalflipstate.emit(imgList.getGlobalFlipHorizontal(), imgList.getGlobalFlipVertical())

    def set_cur_timer(self):
        global imgList

        if imgList.getAppMode() != 'photo_switching':
            self.emit_timer_visual_state(imgList.getCurTimer(False))
            return

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

    def color_practice_enabled(self):
        global imgList
        self.setcolorpracticeenabled.emit(imgList.isColorPracticeEnabled())

    def app_mode(self):
        global imgList
        self.setappmode.emit(imgList.getAppMode())

    def color_practice_sub_mode(self):
        global imgList
        self.setcolorpracticesubmode.emit(imgList.getColorPracticeSubMode())

    def color_practice_thresholds(self):
        global imgList
        thresholds = imgList.getColorPracticeThresholds()
        self.setcolorpracticethresholds.emit(
            float(thresholds.get('min_luma', 0.22)),
            float(thresholds.get('max_luma', 0.82)),
            float(thresholds.get('min_saturation', 0.35))
        )

    def color_block_settings(self):
        global imgList
        settings = imgList.getColorBlocksSettings()
        self.setcolorblocksettings.emit(
            int(settings.get('stripe_count', 1)),
            float(settings.get('min_luma', 0.22)),
            float(settings.get('max_luma', 0.82)),
            float(settings.get('min_saturation', 0.35))
        )

    def color_block_shape_mode_enabled(self):
        global imgList
        self.setcolorblockshapemodeenabled.emit(imgList.getColorBlocksShapeModeEnabled())

    def color_photo_crystallize_enabled(self):
        global imgList
        self.setcolorphotocrystallizeenabled.emit(imgList.getColorPhotoCrystallizeEnabled())

    def protected_video_export_available(self):
        self.setprotectedvideoexportavailable.emit(bool(self.video_tools.get('available')))

    def protected_video_export_busy_state(self):
        self.setprotectedvideoexportbusy.emit(bool(self.video_export_busy))

    def emit_mode_state(self, reload_image=True):
        global imgList
        self.app_mode()
        self.color_practice_enabled()
        self.color_practice_sub_mode()
        self.color_practice_thresholds()
        self.color_block_settings()
        self.color_block_shape_mode_enabled()
        self.color_photo_crystallize_enabled()
        self.protected_video_export_available()
        self.protected_video_export_busy_state()
        self.setplaymode.emit('RND' if imgList.isRandomPlayMode() else 'SEQ')
        self.settimervalue.emit(imgList.getTimerSeconds())
        self.settimerendmode.emit(imgList.getTimerEndMode())
        self.setprestartenabled.emit(imgList.isPrestartCountdownEnabled())
        if reload_image:
            self.reload()
        self.emit_timer_visual_state(imgList.getCurTimer(False))

    def initialize_current_image(self):
        global imgList

        if not imgList.hasImages():
            return

        imgList.change(1)
        self.reload()
        self.restart_timer_tick_phase()
        if imgList.getAppMode() == 'photo_switching':
            self.prestart_pending = imgList.isPrestartCountdownEnabled()
            self.clear_prestart_countdown()
        else:
            self.prestart_pending = False
            self.clear_prestart_countdown()
        self.emit_timer_visual_state()

    def ensure_image_source_for_current_mode(self, async_open=True):
        global imgList

        if imgList.getAppMode() not in ('photo_switching', 'color_photo'):
            return False
        if imgList.hasImages():
            return False
        if self.image_source_prompt_pending:
            return False

        self.image_source_prompt_pending = True
        if async_open:
            QTimer.singleShot(0, self._open_queued_image_source_prompt)
        else:
            self._open_queued_image_source_prompt()
        return True

    def _open_queued_image_source_prompt(self):
        global imgList

        if not self.image_source_prompt_pending:
            return False
        if imgList.getAppMode() not in ('photo_switching', 'color_photo') or imgList.hasImages():
            self.image_source_prompt_pending = False
            return False

        print('Opening image folder picker...')
        return self._open_image_root_path_dialog()

    def _open_image_root_path_dialog(self):
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
            self.image_source_prompt_pending = False

        if not folder:
            return False

        if not imgList.setImageRootPath(folder):
            print('Invalid image folder or no supported images: {0}'.format(folder))
            return False

        self.emit_mode_state(reload_image=True)
        if imgList.getAppMode() == 'photo_switching':
            self.schedule_timer_start()
        else:
            self.prestart_pending = False
            self.clear_prestart_countdown()
        return True

    def stay_on_top(self):
        global imgList
        self.setstayontop.emit(imgList.isStayOnTop())

    def toast(self, message):
        text = str(message)
        print(text)
        self.showtoast.emit(text)

    def _run_with_window_not_topmost(self, callback):
        root = engine.rootObjects()[0] if len(engine.rootObjects()) > 0 else None
        was_stay_on_top = False
        if root is not None:
            try:
                was_stay_on_top = bool(root.property('stayOnTop'))
            except Exception:
                was_stay_on_top = False

        if root is not None and was_stay_on_top:
            root.setProperty('stayOnTop', False)
            app.processEvents()

        try:
            return callback()
        finally:
            if root is not None and was_stay_on_top:
                root.setProperty('stayOnTop', True)

    def _create_text_watermark_image(self, username):
        text = str(username).strip()
        if text == '':
            raise ValueError('Username must not be empty')

        temp_handle = tempfile.NamedTemporaryFile(prefix='justdraw_watermark_', suffix='.png', delete=False)
        temp_path = temp_handle.name
        temp_handle.close()

        if hasattr(QImage, 'Format'):
            image = QImage(960, 260, QImage.Format.Format_ARGB32_Premultiplied)
        else:
            image = QImage(960, 260, QImage.Format_ARGB32_Premultiplied)
        image.fill(Qt.GlobalColor.transparent if hasattr(Qt, 'GlobalColor') else Qt.transparent)

        painter = QPainter(image)
        try:
            if hasattr(QPainter, 'RenderHint'):
                painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
                painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
            else:
                painter.setRenderHint(QPainter.Antialiasing, True)
                painter.setRenderHint(QPainter.TextAntialiasing, True)

            target_rect = QRectF(36.0, 28.0, 888.0, 204.0)
            if hasattr(Qt, 'AlignmentFlag'):
                alignment = int(Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap)
            else:
                alignment = int(Qt.AlignCenter | Qt.TextWordWrap)
            font_size = 54
            while font_size >= 20:
                font = QFont()
                font.setBold(True)
                font.setPixelSize(font_size)
                painter.setFont(font)
                bounding = painter.boundingRect(target_rect, alignment, text)
                if bounding.width() <= target_rect.width() and bounding.height() <= target_rect.height():
                    break
                font_size -= 2

            painter.setPen(Qt.PenStyle.NoPen if hasattr(Qt, 'PenStyle') else Qt.NoPen)
            painter.setBrush(QColor(0, 0, 0, 88))
            painter.drawRoundedRect(target_rect, 18.0, 18.0)
            painter.setPen(QColor(255, 255, 255, 206))
            painter.drawText(target_rect, alignment, text)
        finally:
            painter.end()

        if not image.save(temp_path):
            try:
                os.remove(temp_path)
            except OSError:
                pass
            raise RuntimeError('Failed to save generated watermark image')

        return temp_path

    def _collect_protected_video_export_options(self):
        if not self.video_tools.get('available'):
            return None

        video_filter = (
            'Video Files (*.mp4 *.mov *.mkv *.avi *.webm *.m4v *.wmv *.flv *.ts *.mts *.m2ts);;'
            'All Files (*)'
        )
        image_filter = 'Image Files (*.png *.jpg *.jpeg *.bmp *.gif *.webp);;All Files (*)'

        def pick_input():
            return QFileDialog.getOpenFileName(
                None,
                'Export Protected Short Video',
                os.path.expanduser('~'),
                video_filter
            )

        selected_path, _ = self._run_with_window_not_topmost(pick_input)
        if not selected_path:
            return None

        def ask_duration():
            return QInputDialog.getInt(
                None,
                'Target Duration',
                'Target total duration (15-30 seconds):',
                20,
                15,
                30,
                1
            )

        target_duration, ok = self._run_with_window_not_topmost(ask_duration)
        if not ok:
            return None

        def ask_username():
            return QInputDialog.getText(
                None,
                'Watermark Username',
                'Username for watermark fallback:'
            )

        username, ok = self._run_with_window_not_topmost(ask_username)
        if not ok:
            return None
        username = str(username).strip()
        if username == '':
            self.toast('Export cancelled: username is required')
            return None

        def pick_watermark():
            return QFileDialog.getOpenFileName(
                None,
                'Optional Watermark Image (Cancel to use text watermark)',
                os.path.dirname(selected_path) or os.path.expanduser('~'),
                image_filter
            )

        watermark_image_path, _ = self._run_with_window_not_topmost(pick_watermark)

        cleanup_paths = []
        if watermark_image_path:
            resolved_watermark_path = watermark_image_path
        else:
            resolved_watermark_path = self._create_text_watermark_image(username)
            cleanup_paths.append(resolved_watermark_path)

        return {
            'input_path': selected_path,
            'output_path': video_tools.build_output_path(selected_path),
            'target_duration': int(target_duration),
            'username': username,
            'watermark_path': resolved_watermark_path,
            'cleanup_paths': cleanup_paths,
        }

    def _video_export_log(self, message):
        logger.info('Video export %s', str(message))

    def _set_video_export_busy(self, enabled):
        self.video_export_busy = bool(enabled)
        self.protected_video_export_busy_state()

    def _run_protected_video_export_worker(self, options):
        try:
            result = video_tools.export_protected_short_video(
                ffmpeg_path=self.video_tools.get('ffmpeg', ''),
                ffprobe_path=self.video_tools.get('ffprobe', ''),
                input_path=options['input_path'],
                output_path=options['output_path'],
                target_total_duration=options['target_duration'],
                watermark_path=options['watermark_path'],
                logger=self._video_export_log,
            )
            message = 'Protected video exported: {0}'.format(os.path.basename(result.get('output_path', options['output_path'])))
            logger.info(
                'Protected video export complete: input=%s output=%s final_duration=%.3f speed_factor=%.4f audio_preserved=%s',
                options['input_path'],
                result.get('output_path', options['output_path']),
                float(result.get('final_duration', 0.0)),
                float(result.get('speed_factor', 1.0)),
                bool(result.get('audio_preserved'))
            )
            self.toast(message)
        except Exception as exc:
            logger.exception('Protected video export failed')
            self.toast('Protected video export failed: {0}'.format(exc))
        finally:
            for path in options.get('cleanup_paths', []):
                try:
                    os.remove(path)
                except OSError:
                    pass
            self._set_video_export_busy(False)
            self.video_export_thread = None

    @pyqtSlot(str)
    def debug_log(self, message):
        logger.info('QML %s', str(message))

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
        if self.image_source_prompt_pending:
            return False

        self.image_source_prompt_pending = True
        return self._open_image_root_path_dialog()

    @pyqtSlot(str, result=bool)
    def set_image_root_path(self, path):
        global imgList

        if not imgList.setImageRootPath(path):
            return False

        self.emit_mode_state(reload_image=True)
        if imgList.getAppMode() == 'photo_switching':
            self.schedule_timer_start()
        else:
            self.prestart_pending = False
            self.clear_prestart_countdown()
        return True

    @pyqtSlot(result='QStringList')
    def get_recent_image_paths(self):
        global imgList
        return imgList.getRecentPlaybackPaths(10)

    def reload(self):
        global imgList

        image_path = imgList.getImagePath()
        if image_path:
            self.setcurimage.emit(QUrl.fromLocalFile(image_path).toString())
        else:
            self.setcurimage.emit('')
        self.emit_image_view_state()

    def after_image_navigation(self):
        global imgList
        if imgList.getAppMode() == 'photo_switching':
            self.schedule_timer_start()
        else:
            self.emit_timer_visual_state(imgList.getCurTimer(False))

    @pyqtSlot()
    def prev_in_folder(self):
        global imgList
        imgList.change(-2)
        self.reload()
        self.after_image_navigation()

    @pyqtSlot()
    def prev(self):
        global imgList
        imgList.change(-1)
        self.reload()
        self.after_image_navigation()

    @pyqtSlot()
    def next(self):
        global imgList
        imgList.change(1)
        self.reload()
        self.after_image_navigation()

    @pyqtSlot()
    def next_in_folder(self):
        global imgList
        imgList.change(2)
        self.reload()
        self.after_image_navigation()

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
        if imgList.getAppMode() != 'photo_switching':
            return
        imgList.resetTimer()
        self.schedule_timer_start()
        self.settimervalue.emit(imgList.getTimerSeconds())

    @pyqtSlot(result=bool)
    def reset_image_order_and_pick_random(self):
        global imgList
        if not imgList.resetImageOrderAndPickRandom():
            return False

        self.reload()
        self.after_image_navigation()
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
        if imgList.getAppMode() != 'photo_switching':
            return

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
        if imgList.getAppMode() != 'photo_switching':
            return
        enabled = imgList.togglePrestartCountdownEnabled()
        self.setprestartenabled.emit(enabled)

        if enabled:
            self.arm_prestart_countdown()
            self.emit_timer_visual_state(imgList.getCurTimer(False))
        else:
            self.prestart_pending = False
            self.clear_prestart_countdown()
            self.emit_timer_visual_state(imgList.getCurTimer(False))

    @pyqtSlot(str, result=bool)
    def set_app_mode(self, mode):
        global imgList

        changed = imgList.setAppMode(mode)
        if not changed:
            self.emit_mode_state(reload_image=False)
            self.ensure_image_source_for_current_mode(async_open=True)
            return False

        self.emit_mode_state(reload_image=True)
        if imgList.getAppMode() == 'photo_switching':
            self.prestart_pending = imgList.isPrestartCountdownEnabled() and imgList.hasImages()
            self.clear_prestart_countdown()
            if not imgList.isTimerPaused():
                self.schedule_timer_start()
            else:
                self.emit_timer_visual_state(imgList.getCurTimer(False))
        else:
            self.prestart_pending = False
            self.clear_prestart_countdown()
            self.emit_timer_visual_state(imgList.getCurTimer(False))
        self.ensure_image_source_for_current_mode(async_open=True)
        return True

    @pyqtSlot(bool, result=bool)
    def set_color_practice_enabled(self, enabled):
        target_mode = 'color_blocks' if bool(enabled) else 'photo_switching'
        return self.set_app_mode(target_mode)

    @pyqtSlot(str, result=bool)
    def set_color_practice_sub_mode(self, mode):
        normalized = str(mode).strip().lower()
        if normalized not in ('palette', 'photo'):
            return False
        target_mode = 'color_blocks' if normalized == 'palette' else 'color_photo'
        return self.set_app_mode(target_mode)

    @pyqtSlot(str, str, str, result=bool)
    def set_color_practice_thresholds(self, min_luma, max_luma, min_saturation):
        global imgList
        changed = imgList.setColorPracticeThresholds(min_luma, max_luma, min_saturation)
        self.color_practice_thresholds()
        self.color_block_settings()
        return changed

    @pyqtSlot(str, result=bool)
    def set_playback_profile(self, profile):
        normalized = str(profile).strip().lower()
        if normalized not in ('photo_switching', 'color_photo'):
            return False
        return self.set_app_mode(normalized)

    @pyqtSlot(str, str, str, str, result=bool)
    def set_color_blocks_settings(self, stripe_count, min_luma, max_luma, min_saturation):
        global imgList
        changed = imgList.setColorBlocksSettings(stripe_count, min_luma, max_luma, min_saturation)
        self.color_block_settings()
        self.color_practice_thresholds()
        return changed

    @pyqtSlot(bool, result=bool)
    def set_color_blocks_shape_mode_enabled(self, enabled):
        global imgList
        changed = imgList.setColorBlocksShapeModeEnabled(enabled)
        self.color_block_shape_mode_enabled()
        return changed

    @pyqtSlot(bool, result=bool)
    def set_color_photo_crystallize_enabled(self, enabled):
        global imgList
        changed = imgList.setColorPhotoCrystallizeEnabled(enabled)
        self.color_photo_crystallize_enabled()
        return changed

    @pyqtSlot(result=bool)
    def export_protected_short_video(self):
        if not self.video_tools.get('available'):
            return False
        if self.video_export_busy:
            self.toast('Protected video export is already running')
            return False

        try:
            options = self._collect_protected_video_export_options()
        except Exception as exc:
            logger.exception('Failed to collect protected video export options')
            self.toast('Protected video export failed: {0}'.format(exc))
            return False
        if not options:
            return False

        self._set_video_export_busy(True)
        self.toast('Protected video export started')
        self.video_export_thread = threading.Thread(
            target=self._run_protected_video_export_worker,
            args=(options,),
            daemon=True
        )
        self.video_export_thread.start()
        return True

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
        if imgList.getAppMode() != 'photo_switching':
            return
        advanced = imgList.setTimerEndMode(mode)
        self.settimerendmode.emit(imgList.getTimerEndMode())
        if advanced:
            self.reload()
        self.emit_timer_visual_state()

    @pyqtSlot(str, str, str, str, result=bool)
    def save_image_view_state(self, scale, offset_x, offset_y, rotation):
        global imgList
        return imgList.saveCurrentImageViewState(scale, offset_x, offset_y, rotation)

    @pyqtSlot(str, str, result=bool)
    def save_global_flip_state(self, flip_horizontal, flip_vertical):
        global imgList
        changed = imgList.setGlobalFlipState(flip_horizontal, flip_vertical)
        if changed:
            self.emit_global_flip_state()
        return True

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

    @pyqtSlot(str, str, str, result=bool)
    def copy_color_patch(self, color_hex, width, height):
        if not color_hex:
            return False

        q_color = QColor(str(color_hex))
        if not q_color.isValid():
            return False

        try:
            w = int(width)
            h = int(height)
        except (TypeError, ValueError):
            w = 512
            h = 512

        w = max(1, w)
        h = max(1, h)

        if hasattr(QImage, 'Format'):
            image = QImage(w, h, QImage.Format.Format_RGB32)
        else:
            image = QImage(w, h, QImage.Format_RGB32)
        image.fill(q_color.rgb())

        app.clipboard().setImage(image)
        return True

    @pyqtSlot(str, str, str, result=bool)
    def copy_color_stripes(self, colors_json, width, height):
        if not colors_json:
            return False

        try:
            parsed = json.loads(str(colors_json))
        except ValueError:
            return False

        if not isinstance(parsed, list) or len(parsed) == 0:
            return False

        q_colors = []
        for value in parsed:
            q_color = QColor(str(value))
            if not q_color.isValid():
                return False
            q_colors.append(q_color)

        try:
            w = int(width)
            h = int(height)
        except (TypeError, ValueError):
            w = 512
            h = 512

        w = max(1, w)
        h = max(1, h)

        if hasattr(QImage, 'Format'):
            image = QImage(w, h, QImage.Format.Format_RGB32)
        else:
            image = QImage(w, h, QImage.Format_RGB32)

        painter = QPainter(image)
        try:
            total = len(q_colors)
            for idx, q_color in enumerate(q_colors):
                x0 = int(idx * w / total)
                x1 = int((idx + 1) * w / total)
                painter.fillRect(x0, 0, max(1, x1 - x0), h, q_color)
        finally:
            painter.end()

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
backend.stay_on_top()
backend.emit_mode_state(reload_image=False)
backend.emit_global_flip_state()

if imgList.getAppMode() in ('photo_switching', 'color_photo') and imgList.hasImages():
    backend.initialize_current_image()

# start in paused mode; click timer once to begin playback
if imgList.getAppMode() == 'photo_switching':
    backend.pause()


def save_session_state():
    global imgList
    imgList.saveResumeState()


app.aboutToQuit.connect(save_session_state)
QTimer.singleShot(0, lambda: backend.ensure_image_source_for_current_mode(async_open=True))

sys.exit(app.exec())
