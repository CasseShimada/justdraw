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
    from PyQt6.QtGui import QColor, QImage, QIcon, QPainter
    from PyQt6.QtCore import QTimer, QObject, QUrl, Qt, QtMsgType, pyqtSignal, pyqtSlot, qInstallMessageHandler
    from PyQt6.QtWidgets import (
        QAbstractItemView,
        QApplication,
        QCheckBox,
        QComboBox,
        QDialog,
        QFileDialog,
        QHBoxLayout,
        QInputDialog,
        QLabel,
        QLineEdit,
        QListWidget,
        QPushButton,
        QProgressBar,
        QSpinBox,
        QVBoxLayout,
        QWidget,
    )
except ImportError:
    from PyQt5.QtQml import QQmlApplicationEngine
    from PyQt5.QtGui import QColor, QImage, QIcon, QPainter
    from PyQt5.QtCore import QTimer, QObject, QUrl, Qt, QtMsgType, pyqtSignal, pyqtSlot, qInstallMessageHandler
    from PyQt5.QtWidgets import (
        QAbstractItemView,
        QApplication,
        QCheckBox,
        QComboBox,
        QDialog,
        QFileDialog,
        QHBoxLayout,
        QInputDialog,
        QLabel,
        QLineEdit,
        QListWidget,
        QPushButton,
        QProgressBar,
        QSpinBox,
        QVBoxLayout,
        QWidget,
    )

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

APPLICATION_EXIT_REQUESTED = False


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


def _qt_window_flag():
    return Qt.WindowType.Window if hasattr(Qt, 'WindowType') else Qt.Window


def _qt_window_stays_on_top_hint():
    return Qt.WindowType.WindowStaysOnTopHint if hasattr(Qt, 'WindowType') else Qt.WindowStaysOnTopHint


def _qt_non_modal():
    return Qt.WindowModality.NonModal if hasattr(Qt, 'WindowModality') else Qt.NonModal


def _qt_extended_selection():
    if hasattr(QAbstractItemView, 'SelectionMode'):
        return QAbstractItemView.SelectionMode.ExtendedSelection
    return QAbstractItemView.ExtendedSelection


def _qt_internal_move():
    if hasattr(QAbstractItemView, 'DragDropMode'):
        return QAbstractItemView.DragDropMode.InternalMove
    return QAbstractItemView.InternalMove


class ProtectedVideoInputListWidget(QListWidget):
    filesDropped = pyqtSignal(list)

    def __init__(self):
        super().__init__()
        self.setAcceptDrops(True)

    def _extract_video_paths(self, event):
        mime_data = event.mimeData()
        if mime_data is None or not mime_data.hasUrls():
            return []

        allowed_extensions = {
            '.mp4', '.mov', '.mkv', '.avi', '.webm', '.m4v', '.wmv', '.flv', '.ts', '.mts', '.m2ts'
        }
        paths = []
        seen = set()
        for url in mime_data.urls():
            if not url.isLocalFile():
                continue
            path_value = str(url.toLocalFile() or '').strip()
            if path_value == '' or path_value in seen:
                continue
            if not os.path.isfile(path_value):
                continue
            if os.path.splitext(path_value)[1].strip().lower() not in allowed_extensions:
                continue
            seen.add(path_value)
            paths.append(path_value)
        return paths

    def dragEnterEvent(self, event):
        if self._extract_video_paths(event):
            event.acceptProposedAction()
            return
        super().dragEnterEvent(event)

    def dragMoveEvent(self, event):
        if self._extract_video_paths(event):
            event.acceptProposedAction()
            return
        super().dragMoveEvent(event)

    def dropEvent(self, event):
        paths = self._extract_video_paths(event)
        if paths:
            event.acceptProposedAction()
            self.filesDropped.emit(paths)
            return
        super().dropEvent(event)


class ProtectedVideoExportDialog(QDialog):
    def __init__(self, backend):
        super().__init__(None)
        self.backend = backend
        self._stay_on_top = False
        self._export_busy = False
        self.setAcceptDrops(True)
        self._build_ui()

    def _build_ui(self):
        self.setWindowTitle('Protected Video Export')
        self.setModal(False)
        self.setWindowModality(_qt_non_modal())
        self.resize(620, 420)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        title_label = QLabel('Protected Video Export')
        title_label.setStyleSheet('font-weight: bold; font-size: 15px;')
        layout.addWidget(title_label)

        info_label = QLabel(
            'Matches video-generator: exact target duration with a 1-second intro hold '
            'before the accelerated main content, then shows the final frame once at the end.'
        )
        info_label.setWordWrap(True)
        layout.addWidget(info_label)

        source_label = QLabel('Source Videos')
        source_label.setStyleSheet('font-weight: bold;')
        layout.addWidget(source_label)

        self.input_list_widget = ProtectedVideoInputListWidget()
        self.input_list_widget.setSelectionMode(_qt_extended_selection())
        self.input_list_widget.setDragDropMode(_qt_internal_move())
        layout.addWidget(self.input_list_widget, 1)
        self.input_list_widget.model().rowsMoved.connect(self._persist_state_after_reorder)
        self.input_list_widget.filesDropped.connect(self._append_input_paths)

        input_buttons_row = QHBoxLayout()
        input_buttons_row.setSpacing(8)
        self.input_add_button = QPushButton('Add Videos...')
        self.input_add_button.clicked.connect(self._browse_input_paths)
        self.input_remove_button = QPushButton('Remove Selected')
        self.input_remove_button.clicked.connect(self._remove_selected_input_paths)
        self.input_clear_button = QPushButton('Clear')
        self.input_clear_button.clicked.connect(self._clear_input_paths)
        input_buttons_row.addWidget(self.input_add_button)
        input_buttons_row.addWidget(self.input_remove_button)
        input_buttons_row.addWidget(self.input_clear_button)
        input_buttons_row.addStretch(1)
        layout.addLayout(input_buttons_row)

        options_row = QHBoxLayout()
        options_row.setSpacing(8)
        self.duration_spin = QSpinBox()
        self.duration_spin.setRange(1, 86400)
        self.duration_spin.setPrefix('Seconds: ')
        self.duration_spin.setValue(15)
        self.output_format_combo = QComboBox()
        self.output_format_combo.addItem('MP4 Video', 'mp4')
        self.output_format_combo.addItem('GIF Animation', 'gif')
        self.overlay_combo = QComboBox()
        self.overlay_combo.addItem('Noise Overlay', 'noise')
        self.overlay_combo.addItem('No Overlay', 'off')
        options_row.addWidget(self.duration_spin)
        options_row.addWidget(self.output_format_combo)
        options_row.addWidget(self.overlay_combo, 1)
        layout.addLayout(options_row)

        self.watermark_mode_combo = QComboBox()
        self.watermark_mode_combo.addItem('Text Watermark', 'text')
        self.watermark_mode_combo.addItem('Image Watermark', 'image')
        self.watermark_mode_combo.currentIndexChanged.connect(self._sync_watermark_mode)
        layout.addWidget(self.watermark_mode_combo)

        self.watermark_text_row = QWidget()
        watermark_text_layout = QHBoxLayout(self.watermark_text_row)
        watermark_text_layout.setContentsMargins(0, 0, 0, 0)
        self.watermark_text_edit = QLineEdit()
        self.watermark_text_edit.setPlaceholderText('Watermark text')
        watermark_text_layout.addWidget(self.watermark_text_edit)
        layout.addWidget(self.watermark_text_row)

        self.watermark_path_row = QWidget()
        watermark_path_layout = QHBoxLayout(self.watermark_path_row)
        watermark_path_layout.setContentsMargins(0, 0, 0, 0)
        watermark_path_layout.setSpacing(8)
        self.watermark_path_edit = QLineEdit()
        self.watermark_path_edit.setPlaceholderText('Watermark image path')
        self.watermark_browse_button = QPushButton('Browse...')
        self.watermark_browse_button.clicked.connect(self._browse_watermark_path)
        watermark_path_layout.addWidget(self.watermark_path_edit, 1)
        watermark_path_layout.addWidget(self.watermark_browse_button)
        layout.addWidget(self.watermark_path_row)

        self.delete_source_checkbox = QCheckBox('Delete original video after successful export')
        layout.addWidget(self.delete_source_checkbox)

        self.status_label = QLabel('Output file name is generated automatically from the processed duration.')
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        buttons_row = QHBoxLayout()
        buttons_row.setSpacing(8)
        buttons_row.addStretch(1)
        self.close_button = QPushButton('Close')
        self.close_button.clicked.connect(self.close)
        buttons_row.addWidget(self.close_button)
        self.export_button = QPushButton('Export')
        self.export_button.clicked.connect(self._start_export)
        buttons_row.addWidget(self.export_button)
        layout.addLayout(buttons_row)

        self._sync_watermark_mode()
        self._refresh_status()

    def _set_combo_value(self, combo_box, value):
        index = combo_box.findData(value)
        combo_box.setCurrentIndex(index if index >= 0 else 0)

    def _sync_watermark_mode(self):
        image_mode = self.watermark_mode_combo.currentData() == 'image'
        self.watermark_text_row.setVisible(not image_mode)
        self.watermark_path_row.setVisible(image_mode)

    def _video_paths(self):
        return [
            self.input_list_widget.item(index).text().strip()
            for index in range(self.input_list_widget.count())
            if self.input_list_widget.item(index).text().strip() != ''
        ]

    def _set_video_paths(self, paths):
        self.input_list_widget.clear()
        seen = set()
        for path in paths or []:
            path_value = str(path or '').strip()
            if path_value == '' or path_value in seen:
                continue
            seen.add(path_value)
            self.input_list_widget.addItem(path_value)
        self._refresh_status()

    def _append_input_paths(self, paths):
        merged_paths = self._video_paths()
        changed = False
        for path in paths or []:
            path_value = str(path or '').strip()
            if path_value == '' or path_value in merged_paths:
                continue
            merged_paths.append(path_value)
            changed = True
        if not changed:
            return
        self._set_video_paths(merged_paths)
        self.backend.persist_protected_video_export_state(self.collect_state())

    def _persist_state_after_reorder(self, *_args):
        self._refresh_status()
        self.backend.persist_protected_video_export_state(self.collect_state())

    def _refresh_status(self):
        queued_count = self.input_list_widget.count()
        self.export_button.setEnabled((not self._export_busy) and queued_count > 0)
        self.export_button.setText('Exporting...' if self._export_busy else 'Export')
        if self._export_busy:
            self.status_label.setText('Export is running in a separate progress window.')
        elif queued_count == 0:
            self.status_label.setText(
                'Add one or more source videos. Output file names are generated automatically from the processed duration.'
            )
        else:
            self.status_label.setText(
                '{0} video(s) queued. Output file names are generated automatically from the processed duration.'.format(
                    queued_count
                )
            )

    def _browse_input_paths(self):
        selected_paths = self.backend.pick_protected_video_input_paths(self._video_paths())
        if not selected_paths:
            return
        self._append_input_paths(selected_paths)

    def _remove_selected_input_paths(self):
        selected_items = list(self.input_list_widget.selectedItems())
        if not selected_items:
            return
        for item in selected_items:
            self.input_list_widget.takeItem(self.input_list_widget.row(item))
        self._refresh_status()
        self.backend.persist_protected_video_export_state(self.collect_state())

    def _clear_input_paths(self):
        if self.input_list_widget.count() == 0:
            return
        self.input_list_widget.clear()
        self._refresh_status()
        self.backend.persist_protected_video_export_state(self.collect_state())

    def _browse_watermark_path(self):
        selected_path = self.backend.pick_protected_video_watermark_path(
            self._video_paths()[0] if self._video_paths() else '',
            self.watermark_path_edit.text()
        )
        if selected_path:
            self.watermark_path_edit.setText(selected_path)
            self.backend.persist_protected_video_export_state(self.collect_state())

    def _start_export(self):
        self.backend.export_protected_short_video_with_options(
            self._video_paths(),
            str(self.duration_spin.value()),
            self.output_format_combo.currentData(),
            self.overlay_combo.currentData(),
            self.watermark_text_edit.text(),
            self.watermark_path_edit.text(),
            self.delete_source_checkbox.isChecked(),
        )

    def collect_state(self):
        video_paths = self._video_paths()
        return {
            'input_path': video_paths[0] if video_paths else '',
            'input_paths': video_paths,
            'duration_seconds': int(self.duration_spin.value()),
            'output_format': str(self.output_format_combo.currentData() or 'mp4'),
            'overlay_mode': str(self.overlay_combo.currentData() or 'noise'),
            'watermark_mode': str(self.watermark_mode_combo.currentData() or 'text'),
            'watermark_text': self.watermark_text_edit.text().strip(),
            'watermark_path': self.watermark_path_edit.text().strip(),
            'delete_source_after_export': self.delete_source_checkbox.isChecked(),
        }

    def apply_state(self, state):
        data = dict(state or {})
        input_paths = data.get('input_paths')
        if not isinstance(input_paths, list) or len(input_paths) == 0:
            legacy_path = str(data.get('input_path', '')).strip()
            input_paths = [legacy_path] if legacy_path else []
        self._set_video_paths(input_paths)
        try:
            duration_seconds = int(data.get('duration_seconds', 15))
        except (TypeError, ValueError):
            duration_seconds = 15
        self.duration_spin.setValue(max(1, duration_seconds))
        self._set_combo_value(self.output_format_combo, str(data.get('output_format', 'mp4')).strip().lower())
        self._set_combo_value(self.overlay_combo, str(data.get('overlay_mode', 'noise')).strip().lower())
        self._set_combo_value(self.watermark_mode_combo, str(data.get('watermark_mode', 'text')).strip().lower())
        self.watermark_text_edit.setText(str(data.get('watermark_text', '')).strip())
        self.watermark_path_edit.setText(str(data.get('watermark_path', '')).strip())
        self.delete_source_checkbox.setChecked(bool(data.get('delete_source_after_export', False)))
        self._sync_watermark_mode()
        self._refresh_status()

    def set_export_busy(self, enabled):
        self._export_busy = bool(enabled)
        self.input_list_widget.setEnabled(not self._export_busy)
        self.input_add_button.setEnabled(not self._export_busy)
        self.input_remove_button.setEnabled(not self._export_busy)
        self.input_clear_button.setEnabled(not self._export_busy)
        self.duration_spin.setEnabled(not self._export_busy)
        self.output_format_combo.setEnabled(not self._export_busy)
        self.overlay_combo.setEnabled(not self._export_busy)
        self.watermark_mode_combo.setEnabled(not self._export_busy)
        self.watermark_text_edit.setEnabled(not self._export_busy)
        self.watermark_path_edit.setEnabled(not self._export_busy)
        self.watermark_browse_button.setEnabled(not self._export_busy)
        self.delete_source_checkbox.setEnabled(not self._export_busy)
        self._refresh_status()

    def set_stay_on_top(self, enabled):
        enabled_value = bool(enabled)
        if self._stay_on_top == enabled_value:
            return
        was_visible = self.isVisible()
        self._stay_on_top = enabled_value
        self.setWindowFlag(_qt_window_stays_on_top_hint(), enabled_value)
        if was_visible:
            self.show()

    def is_stay_on_top(self):
        return self._stay_on_top

    def closeEvent(self, event):
        self.backend.persist_protected_video_export_state(self.collect_state())
        super().closeEvent(event)

    def dragEnterEvent(self, event):
        if self.input_list_widget._extract_video_paths(event):
            event.acceptProposedAction()
            return
        super().dragEnterEvent(event)

    def dragMoveEvent(self, event):
        if self.input_list_widget._extract_video_paths(event):
            event.acceptProposedAction()
            return
        super().dragMoveEvent(event)

    def dropEvent(self, event):
        dropped_paths = self.input_list_widget._extract_video_paths(event)
        if dropped_paths:
            event.acceptProposedAction()
            self._append_input_paths(dropped_paths)
            return
        super().dropEvent(event)


class ProtectedVideoExportProgressDialog(QDialog):
    def __init__(self):
        super().__init__(None)
        self._stay_on_top = False
        self._busy = False
        self._build_ui()

    def _build_ui(self):
        self.setWindowTitle('Protected Video Export Progress')
        self.setModal(False)
        self.setWindowModality(_qt_non_modal())
        self.resize(420, 150)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        self.stage_label = QLabel('Preparing export...')
        self.stage_label.setStyleSheet('font-weight: bold;')
        layout.addWidget(self.stage_label)

        self.detail_label = QLabel('')
        self.detail_label.setWordWrap(True)
        layout.addWidget(self.detail_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        layout.addWidget(self.progress_bar)

        buttons_row = QHBoxLayout()
        buttons_row.addStretch(1)
        self.close_button = QPushButton('Close')
        self.close_button.clicked.connect(self.close)
        buttons_row.addWidget(self.close_button)
        layout.addLayout(buttons_row)

        self._apply_busy_state(False)

    def _apply_busy_state(self, enabled):
        self._busy = bool(enabled)
        self.close_button.setEnabled(not self._busy)

    def update_progress(self, percent, stage, detail):
        clamped = max(0, min(100, int(percent)))
        self._apply_busy_state(True)
        self.stage_label.setText(str(stage))
        self.detail_label.setText(str(detail))
        self.progress_bar.setValue(clamped)
        was_visible = self.isVisible()
        self.show()
        if not was_visible:
            self.raise_()
            self.activateWindow()

    def show_success(self, title, detail):
        self._apply_busy_state(False)
        self.stage_label.setText(str(title))
        self.detail_label.setText(str(detail))
        self.progress_bar.setValue(100)
        self.show()
        self.raise_()
        self.activateWindow()

    def show_error(self, title, detail):
        self._apply_busy_state(False)
        self.stage_label.setText(str(title))
        self.detail_label.setText(str(detail))
        self.show()
        self.raise_()
        self.activateWindow()

    def set_stay_on_top(self, enabled):
        enabled_value = bool(enabled)
        if self._stay_on_top == enabled_value:
            return
        was_visible = self.isVisible()
        self._stay_on_top = enabled_value
        self.setWindowFlag(_qt_window_stays_on_top_hint(), enabled_value)
        if was_visible:
            self.show()

    def is_stay_on_top(self):
        return self._stay_on_top

    def closeEvent(self, event):
        if self._busy and not APPLICATION_EXIT_REQUESTED:
            event.ignore()
            self.raise_()
            self.activateWindow()
            return
        super().closeEvent(event)


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
    videoexportbusychanged = pyqtSignal(bool)
    videoexportprogress = pyqtSignal(int, str, str)
    videoexportfinished = pyqtSignal(bool, str, str)

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
        self.video_export_dialog = None
        self.video_export_progress_dialog = None
        self.videoexportbusychanged.connect(self._handle_video_export_busy_changed)
        self.videoexportprogress.connect(self._handle_video_export_progress)
        self.videoexportfinished.connect(self._handle_video_export_finished)
        logger.info(
            'Video tools detected: ffmpeg=%s ffprobe=%s available=%s reason=%s',
            self.video_tools.get('ffmpeg', ''),
            self.video_tools.get('ffprobe', ''),
            bool(self.video_tools.get('available')),
            self.video_tools.get('missing_reason', '')
        )

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

        if not imgList.getImagePath():
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
        self._sync_auxiliary_window_stay_on_top()

    def toast(self, message):
        text = str(message)
        print(text)
        self.showtoast.emit(text)

    @pyqtSlot()
    def quit_application(self):
        global APPLICATION_EXIT_REQUESTED
        APPLICATION_EXIT_REQUESTED = True
        for window in self._iter_auxiliary_video_windows():
            try:
                window.close()
            except Exception:
                pass
        app.quit()

    def _iter_auxiliary_video_windows(self):
        for window in (self.video_export_dialog, self.video_export_progress_dialog):
            if window is not None:
                yield window

    def _sync_auxiliary_window_stay_on_top(self):
        global imgList
        stay_on_top = imgList.isStayOnTop()
        for window in self._iter_auxiliary_video_windows():
            window.set_stay_on_top(stay_on_top)

    def _ensure_video_export_dialog(self):
        if self.video_export_dialog is None:
            self.video_export_dialog = ProtectedVideoExportDialog(self)
            self.video_export_dialog.setWindowFlag(_qt_window_flag(), True)
            self.video_export_dialog.set_export_busy(self.video_export_busy)
            self._sync_auxiliary_window_stay_on_top()
        return self.video_export_dialog

    def _ensure_video_export_progress_dialog(self):
        if self.video_export_progress_dialog is None:
            self.video_export_progress_dialog = ProtectedVideoExportProgressDialog()
            self.video_export_progress_dialog.setWindowFlag(_qt_window_flag(), True)
            self._sync_auxiliary_window_stay_on_top()
        return self.video_export_progress_dialog

    def _stored_protected_video_export_state(self):
        global imgList
        return imgList.getProtectedVideoExportState()

    def persist_protected_video_export_state(self, state):
        global imgList
        imgList.setProtectedVideoExportState(state)

    def _show_protected_video_export_window(self):
        dialog = self._ensure_video_export_dialog()
        dialog.apply_state(self._stored_protected_video_export_state())
        dialog.set_export_busy(self.video_export_busy)
        dialog.show()
        dialog.raise_()
        dialog.activateWindow()

    @pyqtSlot(int, str, str)
    def _handle_video_export_progress(self, percent, stage, detail):
        progress_dialog = self._ensure_video_export_progress_dialog()
        progress_dialog.update_progress(percent, stage, detail)

    @pyqtSlot(bool)
    def _handle_video_export_busy_changed(self, enabled):
        if self.video_export_dialog is not None:
            self.video_export_dialog.set_export_busy(enabled)

    @pyqtSlot(bool, str, str)
    def _handle_video_export_finished(self, success, title, detail):
        progress_dialog = self._ensure_video_export_progress_dialog()
        if success:
            progress_dialog.show_success(title, detail)
        else:
            progress_dialog.show_error(title, detail)

    def _emit_video_export_progress(self, percent, stage, detail):
        self.videoexportprogress.emit(int(max(0, min(100, round(float(percent))))), str(stage), str(detail))

    def _emit_video_export_finished(self, success, title, detail):
        self.videoexportfinished.emit(bool(success), str(title), str(detail))

    def _resolve_file_dialog_start_path(self, remembered_path='', current_path='', fallback_path=''):
        candidates = [remembered_path, current_path, fallback_path, os.path.expanduser('~')]
        for candidate in candidates:
            raw_value = str(candidate or '').strip()
            if raw_value == '':
                continue
            expanded = os.path.expanduser(raw_value)
            if os.path.isfile(expanded) or os.path.isdir(expanded):
                return expanded
            parent_dir = os.path.dirname(expanded)
            if parent_dir and os.path.isdir(parent_dir):
                return parent_dir
        return os.path.expanduser('~')

    def _run_with_window_not_topmost(self, callback):
        root = engine.rootObjects()[0] if len(engine.rootObjects()) > 0 else None
        was_stay_on_top = False
        toggled_windows = []
        if root is not None:
            try:
                was_stay_on_top = bool(root.property('stayOnTop'))
            except Exception:
                was_stay_on_top = False

        if root is not None and was_stay_on_top:
            root.setProperty('stayOnTop', False)
            app.processEvents()

        for window in self._iter_auxiliary_video_windows():
            if window.is_stay_on_top():
                window.set_stay_on_top(False)
                toggled_windows.append(window)

        try:
            return callback()
        finally:
            for window in toggled_windows:
                window.set_stay_on_top(True)
            if root is not None and was_stay_on_top:
                root.setProperty('stayOnTop', True)

    def _build_protected_video_export_options(
        self,
        input_paths,
        duration_seconds,
        output_format,
        overlay_mode,
        watermark_text,
        watermark_path,
        delete_source_after_export=False,
    ):
        normalized_paths = []
        seen = set()
        raw_paths = input_paths if isinstance(input_paths, (list, tuple)) else [input_paths]
        for value in raw_paths:
            selected_path = str(value or '').strip()
            if selected_path == '' or selected_path in seen:
                continue
            if not os.path.isfile(selected_path):
                raise ValueError('Input video does not exist: {0}'.format(selected_path))
            seen.add(selected_path)
            normalized_paths.append(selected_path)
        if len(normalized_paths) == 0:
            raise ValueError('At least one input video is required')

        try:
            target_duration = int(str(duration_seconds).strip())
        except (TypeError, ValueError):
            raise ValueError('Target duration must be a whole number of seconds')
        if target_duration <= 0:
            raise ValueError('Target duration must be greater than 0 seconds')

        output_format_value = video_tools.normalize_output_format(output_format)

        overlay_value = str(overlay_mode or 'noise').strip().lower()
        if overlay_value not in ('noise', 'off'):
            overlay_value = 'noise'

        watermark_image_path = str(watermark_path or '').strip()
        watermark_text_value = str(watermark_text or '').strip()
        if watermark_image_path != '' and not os.path.isfile(watermark_image_path):
            raise ValueError('Watermark image does not exist')
        if watermark_image_path == '' and watermark_text_value == '':
            raise ValueError('Watermark text is required when no watermark image is selected')

        jobs = []
        for selected_path in normalized_paths:
            jobs.append({
                'input_path': selected_path,
                'output_path': video_tools.build_output_path(selected_path, output_format=output_format_value),
            })

        return {
            'input_path': normalized_paths[0],
            'input_paths': normalized_paths,
            'target_duration': target_duration,
            'output_format': output_format_value,
            'overlay': overlay_value,
            'watermark_path': watermark_image_path,
            'watermark_text': watermark_text_value,
            'delete_source_after_export': bool(delete_source_after_export),
            'jobs': jobs,
            'cleanup_paths': [],
        }

    def _video_export_log(self, message):
        logger.info('Video export %s', str(message))

    def _set_video_export_busy(self, enabled):
        self.video_export_busy = bool(enabled)
        self.protected_video_export_busy_state()
        self.videoexportbusychanged.emit(self.video_export_busy)

    def _build_batch_video_export_progress_callback(self, index, total_jobs):
        base_progress = float(index) * 100.0 / float(max(1, total_jobs))
        progress_span = 100.0 / float(max(1, total_jobs))

        def callback(percent, stage, detail):
            try:
                local_percent = float(percent)
            except (TypeError, ValueError):
                local_percent = 0.0
            local_percent = max(0.0, min(100.0, local_percent))
            batch_percent = base_progress + ((local_percent / 100.0) * progress_span)
            stage_text = str(stage)
            if total_jobs > 1:
                stage_text = 'Video {0}/{1} - {2}'.format(index + 1, total_jobs, stage_text)
            self._emit_video_export_progress(batch_percent, stage_text, str(detail))

        return callback

    def _delete_export_source(self, input_path, output_path):
        try:
            source_path = os.path.normcase(os.path.abspath(str(input_path or '').strip()))
            exported_path = os.path.normcase(os.path.abspath(str(output_path or '').strip()))
        except Exception:
            source_path = str(input_path or '').strip()
            exported_path = str(output_path or '').strip()

        if source_path == '' or source_path == exported_path:
            return False

        os.remove(str(input_path))
        return True

    def _run_protected_video_export_worker(self, options):
        try:
            jobs = list(options.get('jobs', []))
            total_jobs = len(jobs)
            if total_jobs == 0:
                raise RuntimeError('No videos are queued for export')

            exported_outputs = []
            deleted_sources = []
            for index, job in enumerate(jobs):
                input_path = job['input_path']
                try:
                    result = video_tools.export_protected_short_video(
                        ffmpeg_path=self.video_tools.get('ffmpeg', ''),
                        ffprobe_path=self.video_tools.get('ffprobe', ''),
                        input_path=input_path,
                        output_path=job.get('output_path', ''),
                        target_total_duration=options['target_duration'],
                        output_format=options.get('output_format', 'mp4'),
                        watermark_path=options.get('watermark_path', ''),
                        watermark_text=options.get('watermark_text', ''),
                        overlay=options.get('overlay', 'noise'),
                        logger=self._video_export_log,
                        progress_callback=self._build_batch_video_export_progress_callback(index, total_jobs),
                    )
                except Exception as exc:
                    raise RuntimeError(
                        'Video {0}/{1} failed ({2}): {3}'.format(
                            index + 1,
                            total_jobs,
                            os.path.basename(input_path),
                            exc,
                        )
                    ) from exc

                exported_output = result.get('output_path', job.get('output_path', ''))
                exported_outputs.append(exported_output)
                logger.info(
                    'Protected video export complete: input=%s output=%s final_duration=%.3f pts_factor=%.4f overlay=%s watermark_mode=%s',
                    input_path,
                    exported_output,
                    float(result.get('final_duration', 0.0)),
                    float(result.get('pts_factor', 1.0)),
                    result.get('overlay', options.get('overlay', 'noise')),
                    result.get('watermark_mode', 'text')
                )

                if options.get('delete_source_after_export', False):
                    try:
                        if self._delete_export_source(input_path, exported_output):
                            deleted_sources.append(input_path)
                    except OSError as exc:
                        raise RuntimeError(
                            'Video {0}/{1} exported but source deletion failed ({2}): {3}'.format(
                                index + 1,
                                total_jobs,
                                os.path.basename(input_path),
                                exc,
                            )
                        ) from exc

            if total_jobs == 1:
                detail = os.path.basename(exported_outputs[0])
                toast_message = 'Protected video exported: {0}'.format(detail)
            else:
                detail = '{0} videos exported successfully.'.format(total_jobs)
                toast_message = 'Protected video export complete: {0} videos'.format(total_jobs)
            if deleted_sources:
                detail = '{0}\nDeleted {1} source video(s).'.format(detail, len(deleted_sources))

            self._emit_video_export_finished(
                True,
                'Protected video export complete',
                detail
            )
            self.toast(toast_message)
        except Exception as exc:
            logger.exception('Protected video export failed')
            self._emit_video_export_finished(
                False,
                'Protected video export failed',
                str(exc)
            )
            self.toast('Protected video export failed: {0}'.format(exc))
        finally:
            for path in options.get('cleanup_paths', []):
                try:
                    os.remove(path)
                except OSError:
                    pass
            self._set_video_export_busy(False)
            self.video_export_thread = None

    def pick_protected_video_input_paths(self, current_paths=None):
        video_filter = (
            'Video Files (*.mp4 *.mov *.mkv *.avi *.webm *.m4v *.wmv *.flv *.ts *.mts *.m2ts);;'
            'All Files (*)'
        )
        saved_state = self._stored_protected_video_export_state()
        remembered_paths = saved_state.get('input_paths', [])
        remembered_path = remembered_paths[0] if isinstance(remembered_paths, list) and remembered_paths else ''
        current_list = current_paths if isinstance(current_paths, (list, tuple)) else [current_paths]
        current_path = ''
        for value in current_list:
            path_value = str(value or '').strip()
            if path_value != '':
                current_path = path_value
                break
        start_path = self._resolve_file_dialog_start_path(
            remembered_path=remembered_path or saved_state.get('input_path', ''),
            current_path=current_path,
        )
        dialog_parent = self.video_export_dialog if self.video_export_dialog is not None and self.video_export_dialog.isVisible() else None

        def pick_inputs():
            return QFileDialog.getOpenFileNames(
                dialog_parent,
                'Select Source Videos',
                start_path,
                video_filter
            )

        selected_paths, _ = self._run_with_window_not_topmost(pick_inputs)
        normalized_paths = []
        seen = set()
        for path in selected_paths or []:
            path_value = str(path or '').strip()
            if path_value == '' or path_value in seen:
                continue
            seen.add(path_value)
            normalized_paths.append(path_value)
        if normalized_paths:
            self.persist_protected_video_export_state({
                'input_path': normalized_paths[0],
                'input_paths': normalized_paths,
            })
        return normalized_paths

    @pyqtSlot(str, result=str)
    def pick_protected_video_input_path(self, current_path=''):
        selected_paths = self.pick_protected_video_input_paths([current_path] if current_path else [])
        return selected_paths[0] if selected_paths else ''

    @pyqtSlot(str, str, result=str)
    def pick_protected_video_watermark_path(self, input_path, current_path=''):
        image_filter = 'Image Files (*.png *.jpg *.jpeg *.bmp *.gif *.webp);;All Files (*)'
        saved_state = self._stored_protected_video_export_state()
        start_dir = self._resolve_file_dialog_start_path(
            remembered_path=saved_state.get('watermark_path', ''),
            current_path=current_path,
            fallback_path=os.path.dirname(str(input_path).strip())
        )
        dialog_parent = self.video_export_dialog if self.video_export_dialog is not None and self.video_export_dialog.isVisible() else None

        def pick_watermark():
            return QFileDialog.getOpenFileName(
                dialog_parent,
                'Select Watermark Image',
                start_dir,
                image_filter
            )

        selected_path, _ = self._run_with_window_not_topmost(pick_watermark)
        if selected_path:
            self.persist_protected_video_export_state({'watermark_path': selected_path})
        return str(selected_path or '')

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
            reason = self.video_tools.get('missing_reason', '') or 'required tools are unavailable'
            self.toast('Protected video export is unavailable: {0}'.format(reason))
            return False
        self._show_protected_video_export_window()
        return True

    def export_protected_short_video_with_options(
        self,
        input_paths,
        duration_seconds,
        output_format,
        overlay_mode,
        watermark_text,
        watermark_path,
        delete_source_after_export=False,
    ):
        if not self.video_tools.get('available'):
            reason = self.video_tools.get('missing_reason', '') or 'required tools are unavailable'
            self.toast('Protected video export is unavailable: {0}'.format(reason))
            return False
        if self.video_export_busy:
            self.toast('Protected video export is already running')
            return False

        try:
            options = self._build_protected_video_export_options(
                input_paths,
                duration_seconds,
                output_format,
                overlay_mode,
                watermark_text,
                watermark_path,
                delete_source_after_export,
            )
        except Exception as exc:
            logger.exception('Failed to prepare protected video export options')
            self.toast('Protected video export failed: {0}'.format(exc))
            return False

        self.persist_protected_video_export_state({
            'input_path': options.get('input_path', ''),
            'input_paths': options.get('input_paths', []),
            'duration_seconds': options.get('target_duration', 15),
            'output_format': options.get('output_format', 'mp4'),
            'overlay_mode': options.get('overlay', 'noise'),
            'watermark_mode': 'image' if options.get('watermark_path', '') else 'text',
            'watermark_text': options.get('watermark_text', ''),
            'watermark_path': options.get('watermark_path', ''),
            'delete_source_after_export': bool(options.get('delete_source_after_export', False)),
        })
        self._set_video_export_busy(True)
        job_count = len(options.get('jobs', []))
        self._emit_video_export_progress(
            0,
            'Preparing export',
            'Protected video export is starting for {0} video(s)...'.format(job_count)
        )
        self._ensure_video_export_progress_dialog()
        self.toast('Protected video export started ({0} video(s))'.format(job_count))
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
        self._sync_auxiliary_window_stay_on_top()

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
