import json
import os
import random
import sys
import tempfile
import time

from os import walk
from os.path import join, exists, basename, splitext, isdir, isfile, dirname
from zipfile import ZipFile
from pathlib import Path

# supported file extensions
image_extensions = ['.jpg', '.png', '.bmp', '.gif']
zip_extensions = ['.zip']
default_window_width = 840
default_window_height = 1120
default_timer_seconds = 90
default_stay_on_top = True
app_mode_photo_switching = 'photo_switching'
app_mode_color_blocks = 'color_blocks'
app_mode_color_photo = 'color_photo'
app_modes = (app_mode_photo_switching, app_mode_color_blocks, app_mode_color_photo)
playback_profile_photo_switching = app_mode_photo_switching
playback_profile_color_photo = app_mode_color_photo
playback_profiles = (playback_profile_photo_switching, playback_profile_color_photo)
default_playback_profile = playback_profile_photo_switching
default_color_practice_enabled = False
default_color_practice_sub_mode = 'palette'
color_practice_sub_modes = ('palette', 'photo')
default_color_practice_min_luma = 0.22
default_color_practice_max_luma = 0.82
default_color_practice_min_saturation = 0.35
default_color_blocks_shape_mode_enabled = False
default_protected_video_export_duration_seconds = 15
playback_state_file_name = 'justdraw_playback_state.json'

timer_end_mode_auto_next = 'auto_next'
timer_end_mode_hold = 'hold'
timer_end_mode_overtime = 'overtime'
timer_end_modes = (timer_end_mode_auto_next, timer_end_mode_hold, timer_end_mode_overtime)
default_timer_end_mode = timer_end_mode_auto_next

# keep created TemporaryDirectory objects here to prevent it from deletion (will be deleted after program exit)
zip_extract_temp_paths = []


def get_app_data_dir():
    # Source run: keep config in project folder for local development.
    if not getattr(sys, 'frozen', False):
        return os.path.dirname(os.path.realpath(__file__))

    app_name = 'JustDraw'
    if sys.platform.startswith('win'):
        base_dir = os.environ.get('APPDATA') or os.environ.get('LOCALAPPDATA')
        if not base_dir:
            base_dir = str(Path.home())
        target_dir = join(base_dir, app_name)
    else:
        base_dir = os.environ.get('XDG_CONFIG_HOME')
        if not base_dir:
            base_dir = join(str(Path.home()), '.config')
        target_dir = join(base_dir, app_name)

    try:
        os.makedirs(target_dir, exist_ok=True)
        return target_dir
    except OSError:
        return os.path.dirname(sys.executable)


class ImageList:
    def __init__(self):
        self.img_list = []
        self.cur_img_index = 0
        self.cur_image_path = ''
        self.image_root_paths = []
        self.app_data_dir = get_app_data_dir()
        self.config_path = join(self.app_data_dir, 'justdraw_config.json')
        self.playback_state_path = join(self.app_data_dir, playback_state_file_name)
        self.playback_states = {}
        self.app_mode = app_mode_photo_switching
        self.mode_states = self._default_mode_states()
        self.protected_video_export_state = self._default_protected_video_export_state()
        self.playback_profile = default_playback_profile
        self.random_play_mode = False
        self.stay_on_top = default_stay_on_top
        self.timer_end_mode = default_timer_end_mode
        self.prestart_countdown_enabled = False
        self.color_practice_enabled = default_color_practice_enabled
        self.color_practice_sub_mode = default_color_practice_sub_mode
        self.color_practice_min_luma = default_color_practice_min_luma
        self.color_practice_max_luma = default_color_practice_max_luma
        self.color_practice_min_saturation = default_color_practice_min_saturation
        self.last_image_path = ''
        self.global_flip_horizontal = False
        self.global_flip_vertical = False

        self.timer_paused = False
        self.max_timer_value = default_timer_seconds
        self.cur_timer = 0
        self.timer_expired_hold = False
        self.timer_overtime_seconds = 0
        self.total_time_spent = 0

        self.window_width = default_window_width
        self.window_height = default_window_height

        self.loadConfig()
        self.loadPlaybackState()

    @staticmethod
    def _to_bool(value, default):
        if isinstance(value, bool):
            return value

        if isinstance(value, (int, float)):
            return value != 0

        if isinstance(value, str):
            lower = value.strip().lower()
            if lower in ('1', 'true', 'yes', 'on'):
                return True
            if lower in ('0', 'false', 'no', 'off'):
                return False

        return default

    @staticmethod
    def _path_key(path):
        # Normalize separators/case so resume matching works across slash styles.
        raw = str(path).strip()
        if raw == '':
            return ''
        normalized = raw.replace('\\', os.sep).replace('/', os.sep)
        return os.path.normcase(os.path.normpath(normalized))

    @staticmethod
    def _normalize_timer_end_mode(raw_value):
        value = str(raw_value).strip().lower()
        if value in timer_end_modes:
            return value
        return ''

    @staticmethod
    def _normalize_rotation(raw_value):
        try:
            value = int(raw_value)
        except (TypeError, ValueError):
            return 0

        value = value % 360
        if value < 0:
            value += 360

        if value % 90 != 0:
            return 0

        return value

    @staticmethod
    def _to_float(value, default):
        try:
            return float(value)
        except (TypeError, ValueError):
            return float(default)

    @staticmethod
    def _clamp_unit_interval(value):
        return max(0.0, min(1.0, float(value)))

    @staticmethod
    def _normalize_app_mode(value):
        mode = str(value).strip().lower()
        if mode in app_modes:
            return mode
        return ''

    def _default_mode_states(self):
        return {
            app_mode_photo_switching: {
                'image_root_path': '',
                'last_image_path': '',
                'random_play_mode': False,
                'timer_seconds': default_timer_seconds,
                'timer_end_mode': default_timer_end_mode,
                'prestart_countdown_enabled': False,
            },
            app_mode_color_blocks: {
                'stripe_count': 1,
                'min_luma': default_color_practice_min_luma,
                'max_luma': default_color_practice_max_luma,
                'min_saturation': default_color_practice_min_saturation,
                'shape_mode_enabled': default_color_blocks_shape_mode_enabled,
            },
            app_mode_color_photo: {
                'image_root_path': '',
                'last_image_path': '',
                'random_play_mode': False,
                'crystallize_enabled': False,
            },
        }

    def _default_protected_video_export_state(self):
        return {
            'input_path': '',
            'input_paths': [],
            'duration_seconds': default_protected_video_export_duration_seconds,
            'output_format': 'mp4',
            'overlay_mode': 'noise',
            'watermark_mode': 'text',
            'watermark_text': '',
            'watermark_path': '',
            'delete_source_after_export': False,
        }

    def _normalize_protected_video_export_state(self, state=None):
        normalized = self._default_protected_video_export_state()
        if isinstance(state, dict):
            normalized.update(state)

        try:
            duration_seconds = int(normalized.get('duration_seconds', default_protected_video_export_duration_seconds))
        except (TypeError, ValueError):
            duration_seconds = default_protected_video_export_duration_seconds
        normalized['duration_seconds'] = max(1, duration_seconds)

        raw_input_path = str(normalized.get('input_path', '')).strip()
        raw_input_paths = normalized.get('input_paths', [])
        input_paths = []
        seen = set()
        if isinstance(raw_input_paths, list):
            for path in raw_input_paths:
                path_value = str(path or '').strip()
                if path_value == '' or path_value in seen:
                    continue
                seen.add(path_value)
                input_paths.append(path_value)
        if not input_paths and raw_input_path:
            input_paths = [raw_input_path]

        normalized['input_paths'] = input_paths
        normalized['input_path'] = input_paths[0] if input_paths else ''
        normalized['output_format'] = 'gif' if str(normalized.get('output_format', 'mp4')).strip().lower() == 'gif' else 'mp4'

        overlay_mode = str(normalized.get('overlay_mode', 'noise')).strip().lower()
        normalized['overlay_mode'] = 'off' if overlay_mode == 'off' else 'noise'

        watermark_mode = str(normalized.get('watermark_mode', 'text')).strip().lower()
        normalized['watermark_mode'] = 'image' if watermark_mode == 'image' else 'text'
        normalized['watermark_text'] = str(normalized.get('watermark_text', '')).strip()
        normalized['watermark_path'] = str(normalized.get('watermark_path', '')).strip()
        normalized['delete_source_after_export'] = self._to_bool(
            normalized.get('delete_source_after_export', False),
            False
        )
        return normalized

    def _active_playback_profile(self):
        if self.app_mode == app_mode_color_photo:
            return playback_profile_color_photo
        return playback_profile_photo_switching

    def _sync_runtime_into_mode_states(self):
        mode_state = self.mode_states.get(self.app_mode, {})
        if self.app_mode == app_mode_photo_switching:
            mode_state['image_root_path'] = self.getImageRootPath()
            mode_state['last_image_path'] = self.last_image_path
            mode_state['random_play_mode'] = self.random_play_mode
            mode_state['timer_seconds'] = self.max_timer_value
            mode_state['timer_end_mode'] = self.timer_end_mode
            mode_state['prestart_countdown_enabled'] = self.prestart_countdown_enabled
        elif self.app_mode == app_mode_color_photo:
            mode_state['image_root_path'] = self.getImageRootPath()
            mode_state['last_image_path'] = self.last_image_path
            mode_state['random_play_mode'] = self.random_play_mode
        elif self.app_mode == app_mode_color_blocks:
            mode_state['stripe_count'] = int(max(1, self.mode_states[app_mode_color_blocks].get('stripe_count', 1)))
            mode_state['min_luma'] = self.color_practice_min_luma
            mode_state['max_luma'] = self.color_practice_max_luma
            mode_state['min_saturation'] = self.color_practice_min_saturation
            mode_state['shape_mode_enabled'] = self.getColorBlocksShapeModeEnabled()

    def _apply_mode_state_to_runtime(self):
        self.playback_profile = self._active_playback_profile()
        self.color_practice_enabled = self.app_mode != app_mode_photo_switching
        self.color_practice_sub_mode = 'palette' if self.app_mode == app_mode_color_blocks else 'photo'

        if self.app_mode == app_mode_color_blocks:
            blocks = self.mode_states.get(app_mode_color_blocks, {})
            min_luma = self._clamp_unit_interval(self._to_float(blocks.get('min_luma', default_color_practice_min_luma), default_color_practice_min_luma))
            max_luma = self._clamp_unit_interval(self._to_float(blocks.get('max_luma', default_color_practice_max_luma), default_color_practice_max_luma))
            if min_luma > max_luma:
                min_luma, max_luma = max_luma, min_luma
            self.color_practice_min_luma = min_luma
            self.color_practice_max_luma = max_luma
            self.color_practice_min_saturation = self._clamp_unit_interval(
                self._to_float(blocks.get('min_saturation', default_color_practice_min_saturation), default_color_practice_min_saturation)
            )
            self.image_root_paths = []
            self.last_image_path = ''
            self.random_play_mode = False
            return

        mode_state = self.mode_states.get(self.app_mode, {})
        root_path = str(mode_state.get('image_root_path', '')).strip()
        if root_path and exists(root_path) and (isdir(root_path) or (isfile(root_path) and is_file_valid(root_path, zip_extensions))):
            self.image_root_paths = [root_path]
        else:
            self.image_root_paths = []
        self.last_image_path = str(mode_state.get('last_image_path', '')).strip()
        self.random_play_mode = self._to_bool(mode_state.get('random_play_mode', False), False)

        if self.app_mode == app_mode_photo_switching:
            try:
                timer_seconds = int(mode_state.get('timer_seconds', default_timer_seconds))
            except (TypeError, ValueError):
                timer_seconds = default_timer_seconds
            self.max_timer_value = timer_seconds if timer_seconds > 0 else default_timer_seconds
            timer_mode = self._normalize_timer_end_mode(mode_state.get('timer_end_mode', default_timer_end_mode))
            self.timer_end_mode = timer_mode if timer_mode else default_timer_end_mode
            self.prestart_countdown_enabled = self._to_bool(
                mode_state.get('prestart_countdown_enabled', False),
                False
            )

    def getImagePath(self):
        return self.cur_image_path

    def getWindowWidth(self):
        return self.window_width

    def getWindowHeight(self):
        return self.window_height

    def getImageRootPath(self):
        if len(self.image_root_paths) == 0:
            return ''

        return self.image_root_paths[0]

    def hasImages(self):
        return len(self.img_list) > 0

    def loadConfig(self):
        if not exists(self.config_path):
            self._apply_mode_state_to_runtime()
            return

        try:
            with open(self.config_path, 'r', encoding='utf-8') as fp:
                raw = fp.read().strip()

            if raw == '':
                return

            data = json.loads(raw)
        except (OSError, ValueError):
            self._apply_mode_state_to_runtime()
            return

        try:
            width = int(data.get('window_width', default_window_width))
            height = int(data.get('window_height', default_window_height))
        except (TypeError, ValueError):
            width = default_window_width
            height = default_window_height

        if width > 0:
            self.window_width = width
        else:
            self.window_width = default_window_width

        if height > 0:
            self.window_height = height
        else:
            self.window_height = default_window_height

        # Keep startup behavior: first timer tick should trigger initial image load.
        self.cur_timer = 0
        self.stay_on_top = self._to_bool(data.get('stay_on_top', default_stay_on_top), default_stay_on_top)

        modes_data = data.get('modes')
        legacy_root_path = str(data.get('image_root_path', '')).strip()
        legacy_last_image_path = str(data.get('last_image_path', '')).strip()
        legacy_random_play_mode = self._to_bool(data.get('random_play_mode', False), False)
        try:
            legacy_timer_seconds = int(data.get('timer_seconds', default_timer_seconds))
        except (TypeError, ValueError):
            legacy_timer_seconds = default_timer_seconds
        if legacy_timer_seconds <= 0:
            legacy_timer_seconds = default_timer_seconds
        legacy_timer_end_mode = self._normalize_timer_end_mode(data.get('timer_end_mode', ''))
        if legacy_timer_end_mode == '':
            auto_next = self._to_bool(data.get('auto_next_on_timer_end', True), True)
            legacy_timer_end_mode = timer_end_mode_auto_next if auto_next else timer_end_mode_hold
        legacy_prestart = self._to_bool(data.get('prestart_countdown_enabled', False), False)
        legacy_color_enabled = self._to_bool(
            data.get('color_practice_enabled', default_color_practice_enabled),
            default_color_practice_enabled
        )
        legacy_sub_mode = str(data.get('color_practice_sub_mode', default_color_practice_sub_mode)).strip().lower()
        if legacy_sub_mode not in color_practice_sub_modes:
            legacy_sub_mode = default_color_practice_sub_mode
        legacy_min_luma = self._clamp_unit_interval(
            self._to_float(data.get('color_practice_min_luma', default_color_practice_min_luma), default_color_practice_min_luma)
        )
        legacy_max_luma = self._clamp_unit_interval(
            self._to_float(data.get('color_practice_max_luma', default_color_practice_max_luma), default_color_practice_max_luma)
        )
        if legacy_min_luma > legacy_max_luma:
            legacy_min_luma, legacy_max_luma = legacy_max_luma, legacy_min_luma
        legacy_min_saturation = self._clamp_unit_interval(
            self._to_float(data.get('color_practice_min_saturation', default_color_practice_min_saturation), default_color_practice_min_saturation)
        )

        # Migrate old flat config into mode-scoped structure.
        self.mode_states = self._default_mode_states()
        self.mode_states[app_mode_photo_switching]['image_root_path'] = legacy_root_path
        self.mode_states[app_mode_photo_switching]['last_image_path'] = legacy_last_image_path
        self.mode_states[app_mode_photo_switching]['random_play_mode'] = legacy_random_play_mode
        self.mode_states[app_mode_photo_switching]['timer_seconds'] = legacy_timer_seconds
        self.mode_states[app_mode_photo_switching]['timer_end_mode'] = legacy_timer_end_mode
        self.mode_states[app_mode_photo_switching]['prestart_countdown_enabled'] = legacy_prestart
        self.mode_states[app_mode_color_blocks]['min_luma'] = legacy_min_luma
        self.mode_states[app_mode_color_blocks]['max_luma'] = legacy_max_luma
        self.mode_states[app_mode_color_blocks]['min_saturation'] = legacy_min_saturation
        self.mode_states[app_mode_color_photo]['image_root_path'] = str(
            data.get('color_photo_image_root_path', legacy_root_path)
        ).strip()
        self.mode_states[app_mode_color_photo]['last_image_path'] = str(
            data.get('color_photo_last_image_path', '')
        ).strip()
        self.mode_states[app_mode_color_photo]['random_play_mode'] = self._to_bool(
            data.get('color_photo_random_play_mode', False),
            False
        )
        self.mode_states[app_mode_color_photo]['crystallize_enabled'] = self._to_bool(
            data.get('color_photo_crystallize_enabled', False),
            False
        )
        self.mode_states[app_mode_color_blocks]['stripe_count'] = max(
            1,
            int(self._to_float(data.get('color_blocks_stripe_count', 1), 1))
        )
        self.mode_states[app_mode_color_blocks]['shape_mode_enabled'] = self._to_bool(
            data.get('color_blocks_shape_mode_enabled', default_color_blocks_shape_mode_enabled),
            default_color_blocks_shape_mode_enabled
        )

        if isinstance(modes_data, dict):
            for mode_name in app_modes:
                incoming = modes_data.get(mode_name)
                if not isinstance(incoming, dict):
                    continue
                target = self.mode_states[mode_name]
                for key, value in incoming.items():
                    target[key] = value

        saved_mode = self._normalize_app_mode(data.get('app_mode', ''))
        if saved_mode == '':
            if legacy_color_enabled:
                saved_mode = app_mode_color_blocks if legacy_sub_mode == 'palette' else app_mode_color_photo
            else:
                saved_mode = app_mode_photo_switching
        self.app_mode = saved_mode

        self.global_flip_horizontal = self._to_bool(
            data.get('global_flip_horizontal', data.get('flip_horizontal', False)),
            False
        )
        self.global_flip_vertical = self._to_bool(
            data.get('global_flip_vertical', data.get('flip_vertical', False)),
            False
        )
        protected_video_state = data.get('protected_video_export')
        self.protected_video_export_state = self._normalize_protected_video_export_state(protected_video_state)
        self._apply_mode_state_to_runtime()

    def saveConfig(self):
        self._sync_runtime_into_mode_states()

        legacy_color_enabled = self.app_mode in (app_mode_color_blocks, app_mode_color_photo)
        legacy_sub_mode = 'palette' if self.app_mode == app_mode_color_blocks else 'photo'
        photo_mode = self.mode_states[app_mode_photo_switching]
        blocks_mode = self.mode_states[app_mode_color_blocks]
        color_photo_mode = self.mode_states[app_mode_color_photo]

        data = {
            'app_mode': self.app_mode,
            'modes': self.mode_states,
            'image_root_path': str(photo_mode.get('image_root_path', '')).strip(),
            'window_width': self.window_width,
            'window_height': self.window_height,
            'timer_seconds': int(photo_mode.get('timer_seconds', default_timer_seconds)),
            'random_play_mode': self._to_bool(photo_mode.get('random_play_mode', False), False),
            'stay_on_top': self.stay_on_top,
            'timer_end_mode': str(photo_mode.get('timer_end_mode', default_timer_end_mode)),
            'prestart_countdown_enabled': self._to_bool(photo_mode.get('prestart_countdown_enabled', False), False),
            'playback_profile': self.playback_profile,
            'color_practice_enabled': legacy_color_enabled,
            'color_practice_sub_mode': legacy_sub_mode,
            'color_practice_min_luma': self._to_float(blocks_mode.get('min_luma', default_color_practice_min_luma), default_color_practice_min_luma),
            'color_practice_max_luma': self._to_float(blocks_mode.get('max_luma', default_color_practice_max_luma), default_color_practice_max_luma),
            'color_practice_min_saturation': self._to_float(
                blocks_mode.get('min_saturation', default_color_practice_min_saturation),
                default_color_practice_min_saturation
            ),
            'color_blocks_stripe_count': int(max(1, self._to_float(blocks_mode.get('stripe_count', 1), 1))),
            'color_blocks_shape_mode_enabled': self._to_bool(
                blocks_mode.get('shape_mode_enabled', default_color_blocks_shape_mode_enabled),
                default_color_blocks_shape_mode_enabled
            ),
            'color_photo_image_root_path': str(color_photo_mode.get('image_root_path', '')).strip(),
            'color_photo_last_image_path': str(color_photo_mode.get('last_image_path', '')).strip(),
            'color_photo_random_play_mode': self._to_bool(color_photo_mode.get('random_play_mode', False), False),
            'color_photo_crystallize_enabled': self._to_bool(color_photo_mode.get('crystallize_enabled', False), False),
            # Keep legacy key for backward compatibility.
            'auto_next_on_timer_end': str(photo_mode.get('timer_end_mode', default_timer_end_mode)) == timer_end_mode_auto_next,
            'last_image_path': str(photo_mode.get('last_image_path', '')).strip(),
            'global_flip_horizontal': self.global_flip_horizontal,
            'global_flip_vertical': self.global_flip_vertical,
            'protected_video_export': self.getProtectedVideoExportState(),
        }

        try:
            with open(self.config_path, 'w', encoding='utf-8') as fp:
                json.dump(data, fp, ensure_ascii=True, indent=2)
        except OSError:
            print('Cannot write config file: {0}'.format(self.config_path))

    def loadPlaybackState(self):
        self.playback_states = {}
        if not exists(self.playback_state_path):
            return

        try:
            with open(self.playback_state_path, 'r', encoding='utf-8') as fp:
                raw = fp.read().strip()

            if raw == '':
                return

            data = json.loads(raw)
        except (OSError, ValueError):
            return

        paths = data.get('paths', {}) if isinstance(data, dict) else {}
        if isinstance(paths, dict):
            self.playback_states = paths
            if self._remove_legacy_flip_fields_from_view_states():
                self.savePlaybackState()

    def _remove_legacy_flip_fields_from_view_states(self):
        changed = False
        for state in self.playback_states.values():
            if not isinstance(state, dict):
                continue

            view_states = state.get('image_view_states')
            if not isinstance(view_states, dict):
                continue

            for view in view_states.values():
                if not isinstance(view, dict):
                    continue
                if 'mirror' in view:
                    del view['mirror']
                    changed = True
                if 'flip_vertical' in view:
                    del view['flip_vertical']
                    changed = True

        return changed

    def getProtectedVideoExportState(self):
        return self._normalize_protected_video_export_state(self.protected_video_export_state)

    def setProtectedVideoExportState(self, state):
        if not isinstance(state, dict):
            return False

        previous = self.getProtectedVideoExportState()
        updated = dict(previous)
        for key in state.keys():
            if key in updated:
                updated[key] = state[key]

        self.protected_video_export_state = self._normalize_protected_video_export_state(updated)
        changed = self.getProtectedVideoExportState() != previous
        if changed:
            self.saveConfig()
        return changed

    def savePlaybackState(self):
        data = {
            'paths': self.playback_states,
        }

        try:
            with open(self.playback_state_path, 'w', encoding='utf-8') as fp:
                json.dump(data, fp, ensure_ascii=True, indent=2)
        except OSError:
            print('Cannot write playback state file: {0}'.format(self.playback_state_path))

    def _get_path_playback_key(self, path=''):
        target_path = path if path else self.getImageRootPath()
        if not target_path:
            return ''
        return '{0}::{1}'.format(self.playback_profile, self._path_key(target_path))

    def _ensure_current_path_playback_state(self):
        key = self._get_path_playback_key()
        if key == '':
            return None

        state = self.playback_states.get(key)
        if not isinstance(state, dict):
            state = {}
            self.playback_states[key] = state

        state['path'] = self.getImageRootPath()
        state['profile'] = self.playback_profile
        if ('image_view_states' not in state) or (not isinstance(state.get('image_view_states'), dict)):
            state['image_view_states'] = {}

        return state

    def _get_item_resume_key(self, item):
        if item is None:
            return ''

        try:
            if hasattr(item, 'get_resume_key'):
                return str(item.get_resume_key()).strip()
            return self._path_key(item.get_path())
        except Exception:
            return ''

    def _serialize_current_image_order(self):
        ordered_keys = []
        seen = set()
        for item in self.img_list:
            key = self._get_item_resume_key(item)
            if key == '' or key in seen:
                continue
            seen.add(key)
            ordered_keys.append(key)
        return ordered_keys

    def _restore_saved_image_order_for_current_path(self):
        key = self._get_path_playback_key()
        if key == '' or len(self.img_list) == 0:
            return False

        state = self.playback_states.get(key)
        if not isinstance(state, dict):
            return False

        saved_order = state.get('image_order')
        if not isinstance(saved_order, list) or len(saved_order) == 0:
            return False

        items_by_key = {}
        for item in self.img_list:
            item_key = self._get_item_resume_key(item)
            if item_key != '' and item_key not in items_by_key:
                items_by_key[item_key] = item

        restored = []
        used_keys = set()
        for raw_key in saved_order:
            item_key = str(raw_key).strip()
            if item_key == '' or item_key in used_keys:
                continue
            item = items_by_key.get(item_key)
            if item is None:
                continue
            restored.append(item)
            used_keys.add(item_key)

        if len(restored) == 0:
            return False

        for item in self.img_list:
            item_key = self._get_item_resume_key(item)
            if item_key in used_keys:
                continue
            restored.append(item)
            if item_key != '':
                used_keys.add(item_key)

        if len(restored) != len(self.img_list):
            return False

        self.img_list = restored
        return True

    def _capture_current_path_playback_state(self, save_to_disk=False):
        state = self._ensure_current_path_playback_state()
        if state is None:
            return False

        state['last_image_path'] = self.cur_image_path if self.cur_image_path else self.last_image_path
        state['image_order'] = self._serialize_current_image_order()
        state['random_play_mode'] = self.random_play_mode
        state['timer_seconds'] = self.max_timer_value
        state['timer_end_mode'] = self.timer_end_mode
        state['auto_next_on_timer_end'] = self.timer_end_mode == timer_end_mode_auto_next
        state['last_used_at'] = int(time.time())

        if save_to_disk:
            self.savePlaybackState()

        return True

    def _reset_profile_runtime_defaults(self):
        self.last_image_path = ''
        self.random_play_mode = False
        self.timer_end_mode = default_timer_end_mode
        self.max_timer_value = default_timer_seconds

    def applyPlaybackStateForCurrentPath(self):
        key = self._get_path_playback_key()
        if key == '':
            self._reset_profile_runtime_defaults()
            return False

        state = self.playback_states.get(key)
        if not isinstance(state, dict):
            self._reset_profile_runtime_defaults()
            return False

        self.last_image_path = str(state.get('last_image_path', self.last_image_path)).strip()
        self.random_play_mode = self._to_bool(state.get('random_play_mode', self.random_play_mode), self.random_play_mode)
        mode = self._normalize_timer_end_mode(state.get('timer_end_mode', ''))
        if mode == '':
            auto_next = self._to_bool(
                state.get('auto_next_on_timer_end', self.timer_end_mode == timer_end_mode_auto_next),
                self.timer_end_mode == timer_end_mode_auto_next
            )
            mode = timer_end_mode_auto_next if auto_next else timer_end_mode_hold
        self.timer_end_mode = mode

        try:
            timer_seconds = int(state.get('timer_seconds', self.max_timer_value))
            if timer_seconds > 0:
                self.max_timer_value = timer_seconds
        except (TypeError, ValueError):
            pass

        return True

    def getSavedPlaybackPaths(self):
        result = []
        for state in self.playback_states.values():
            if not isinstance(state, dict):
                continue
            state_profile = str(state.get('profile', default_playback_profile)).strip().lower()
            if state_profile != self.playback_profile:
                continue

            path = str(state.get('path', '')).strip()
            if path:
                result.append(path)

        # Keep ordering stable for UI chooser.
        return sorted(set(result))

    def getRecentPlaybackPaths(self, limit_count=10):
        ranked = []
        for state in self.playback_states.values():
            if not isinstance(state, dict):
                continue
            state_profile = str(state.get('profile', default_playback_profile)).strip().lower()
            if state_profile != self.playback_profile:
                continue

            path = str(state.get('path', '')).strip()
            if not path:
                continue

            try:
                last_used_at = int(state.get('last_used_at', 0))
            except (TypeError, ValueError):
                last_used_at = 0

            ranked.append((last_used_at, path))

        ranked.sort(key=lambda item: item[0], reverse=True)

        unique_paths = []
        seen = set()
        for _, path in ranked:
            if path in seen:
                continue
            seen.add(path)
            unique_paths.append(path)
            if len(unique_paths) >= limit_count:
                break

        return unique_paths

    def deletePlaybackState(self, path):
        key = self._get_path_playback_key(path)
        if key == '' or key not in self.playback_states:
            return False

        del self.playback_states[key]
        self.savePlaybackState()
        return True

    def saveCurrentImageViewState(self, scale, offset_x, offset_y, rotation=0):
        if not self.getImageRootPath() or not self.cur_image_path:
            return False

        try:
            scale_value = float(scale)
            offset_x_value = float(offset_x)
            offset_y_value = float(offset_y)
        except (TypeError, ValueError):
            return False

        rotation_value = self._normalize_rotation(rotation)

        state = self._ensure_current_path_playback_state()
        if state is None:
            return False

        view_states = state['image_view_states']
        view_states[self._path_key(self.cur_image_path)] = {
            'image_path': self.cur_image_path,
            'scale': scale_value,
            'offset_x': offset_x_value,
            'offset_y': offset_y_value,
            'rotation': rotation_value,
        }

        self._capture_current_path_playback_state(save_to_disk=False)
        self.savePlaybackState()
        return True

    def getCurrentImageViewState(self):
        if not self.getImageRootPath() or not self.cur_image_path:
            return None

        key = self._get_path_playback_key()
        state = self.playback_states.get(key)
        if not isinstance(state, dict):
            return None

        view_states = state.get('image_view_states', {})
        if not isinstance(view_states, dict):
            return None

        view = view_states.get(self._path_key(self.cur_image_path))
        if not isinstance(view, dict):
            return None

        try:
            scale_value = float(view.get('scale', 1.0))
            offset_x_value = float(view.get('offset_x', 0.0))
            offset_y_value = float(view.get('offset_y', 0.0))
        except (TypeError, ValueError):
            return None

        rotation_value = self._normalize_rotation(view.get('rotation', 0))

        return {
            'scale': scale_value,
            'offset_x': offset_x_value,
            'offset_y': offset_y_value,
            'rotation': rotation_value,
        }

    def getGlobalFlipHorizontal(self):
        return self.global_flip_horizontal

    def getGlobalFlipVertical(self):
        return self.global_flip_vertical

    def setGlobalFlipState(self, flip_horizontal, flip_vertical):
        new_horizontal = self._to_bool(flip_horizontal, False)
        new_vertical = self._to_bool(flip_vertical, False)

        if self.global_flip_horizontal == new_horizontal and self.global_flip_vertical == new_vertical:
            return False

        self.global_flip_horizontal = new_horizontal
        self.global_flip_vertical = new_vertical
        self.saveConfig()
        return True

    def isCurrentImageFromZip(self):
        if not self.hasImages() or not self.cur_image_path:
            return False

        if self.cur_img_index >= 0 and self.cur_img_index < len(self.img_list):
            if isinstance(self.img_list[self.cur_img_index], ImagePathInZip):
                return True

        # Images extracted from zip-file mode are regular paths inside temporary zip extract folders.
        cur_path = os.path.normcase(os.path.normpath(self.cur_image_path))
        for temp_dir in zip_extract_temp_paths:
            try:
                base_dir = os.path.normcase(os.path.normpath(temp_dir.name))
            except Exception:
                continue

            if cur_path == base_dir or cur_path.startswith(base_dir + os.sep):
                return True

        return False

    def canRevealCurrentImageInExplorer(self):
        return self.hasImages() and bool(self.cur_image_path) and (not self.isCurrentImageFromZip())

    def clearCurrentImageViewState(self):
        if not self.getImageRootPath() or not self.cur_image_path:
            return False

        key = self._get_path_playback_key()
        state = self.playback_states.get(key)
        if not isinstance(state, dict):
            return False

        view_states = state.get('image_view_states', {})
        if not isinstance(view_states, dict):
            return False

        img_key = self._path_key(self.cur_image_path)
        if img_key not in view_states:
            return False

        del view_states[img_key]
        self._capture_current_path_playback_state(save_to_disk=False)
        self.savePlaybackState()
        return True

    def clearCurrentPathImageViewStates(self):
        if not self.getImageRootPath():
            return False

        state = self._ensure_current_path_playback_state()
        if state is None:
            return False

        view_states = state.get('image_view_states')
        if not isinstance(view_states, dict) or len(view_states) == 0:
            return False

        state['image_view_states'] = {}
        self._capture_current_path_playback_state(save_to_disk=False)
        self.savePlaybackState()
        return True

    def _buildImageListFromFolder(self, path):
        # Load regular images from the folder tree and include ZIP archives as image sources too.
        img_items = toImgList(self, findAllSupportedFiles([path], image_extensions))
        zip_files = findAllSupportedFiles([path], zip_extensions)
        if len(zip_files) > 0:
            img_items.extend(findAllSupportedZipFilesRandom(self, zip_files))
        return img_items

    def _buildImageListFromSourcePath(self, path):
        source_path = str(path).strip()
        if not source_path or not exists(source_path):
            return []

        if isdir(source_path):
            return self._buildImageListFromFolder(source_path)

        if isfile(source_path) and is_file_valid(source_path, zip_extensions):
            return findAllSupportedZipFilesRandom(self, [source_path])

        return []

    def _switchToImageList(self, new_img_list, source_path=''):
        if len(new_img_list) == 0:
            return False

        # Save current path progress before switching to a new source.
        self.saveResumeState()

        was_paused = self.timer_paused
        self.image_root_paths = [source_path] if source_path else []
        self.img_list = new_img_list
        self.last_image_path = ''
        self.applyPlaybackStateForCurrentPath()
        restored_saved_order = self._restore_saved_image_order_for_current_path()
        if self.random_play_mode and not restored_saved_order:
            self.shuffle_cycle()

        self.cur_img_index = -1
        self.cur_image_path = ''
        self.cur_timer = 0
        self.timer_expired_hold = False
        self.timer_overtime_seconds = 0
        restored_last_image = self.restoreLastImagePosition()
        if not restored_last_image:
            self.change(1)

        if was_paused and not self.timer_paused:
            self.pause()

        self.saveConfig()
        self._capture_current_path_playback_state(save_to_disk=True)
        return True

    def setImageRootPath(self, path):
        if self.app_mode == app_mode_color_blocks:
            return False

        path = str(path).strip()
        if not path:
            return False

        new_img_list = self._buildImageListFromSourcePath(path)
        if len(new_img_list) == 0:
            return False

        return self._switchToImageList(new_img_list, path)

    def setZipFiles(self, zip_file_paths):
        valid_zip_files = []
        for item in zip_file_paths:
            zip_file = str(item).strip()
            if zip_file and exists(zip_file) and isfile(zip_file) and is_file_valid(zip_file, zip_extensions):
                valid_zip_files.append(zip_file)

        if len(valid_zip_files) == 0:
            return False

        source_path = ''
        if len(valid_zip_files) == 1:
            source_path = valid_zip_files[0]
        else:
            parent_folders = sorted(set(dirname(path) for path in valid_zip_files))
            if len(parent_folders) == 1:
                source_path = parent_folders[0]

        return self._switchToImageList(findAllSupportedZipFiles(self, valid_zip_files), source_path)

    def setRandomZipFromFolder(self, folder_path):
        path = str(folder_path).strip()
        if not path or not exists(path) or not isdir(path):
            return False

        zip_files_list = findAllSupportedFiles([path], zip_extensions)
        if len(zip_files_list) == 0:
            return False

        selected_zip = random.choice(zip_files_list)
        return self._switchToImageList(findAllSupportedZipFiles(self, [selected_zip]), path)

    def setAllZipsFromFolder(self, folder_path):
        path = str(folder_path).strip()
        if not path or not exists(path) or not isdir(path):
            return False

        zip_files_list = findAllSupportedFiles([path], zip_extensions)
        if len(zip_files_list) == 0:
            return False

        return self._switchToImageList(findAllSupportedZipFilesRandom(self, zip_files_list), path)

    def setDefaultWindowSize(self, width, height):
        if width <= 0 or height <= 0:
            return False

        self.window_width = width
        self.window_height = height
        self.saveConfig()
        return True

    def restoreLastImagePosition(self):
        if len(self.img_list) == 0:
            return False

        if not self.getImageRootPath():
            return False

        if not self.last_image_path:
            return False

        target_key = self._path_key(self.last_image_path)
        for index, item in enumerate(self.img_list):
            if self._path_key(item.get_path()) == target_key:
                self.cur_img_index = -1
                self.cur_image_path = ''
                self.cur_timer = self.max_timer_value
                return self._setCurrentImageByIndex(index)

        # Image was removed or moved since last run.
        self.last_image_path = ''
        self.saveConfig()
        self._capture_current_path_playback_state(save_to_disk=True)
        return False

    def saveResumeState(self):
        if self.getImageRootPath() and self.cur_image_path:
            self.last_image_path = self.cur_image_path
        self._capture_current_path_playback_state(save_to_disk=True)
        self.saveConfig()

    def getIndexOfPrevImageInSameFolder(self):

        # search from current index till the beginning of list
        for i in reversed(range(0, self.cur_img_index - 1)):
            if self.img_list[self.cur_img_index].same_folder(self.img_list[i]):
                return i

        # search from the end of the list till current index
        for i in reversed(range(self.cur_img_index + 1, len(self.img_list))):
            if self.img_list[self.cur_img_index].same_folder(self.img_list[i]):
                return i

        return self.cur_img_index + 1

    def getIndexOfNextImageInSameFolder(self):

        # search from current index till the end of list
        for i in range(self.cur_img_index + 1, len(self.img_list)):
            if self.img_list[self.cur_img_index].same_folder(self.img_list[i]):
                return i

        # search from begin of list till current index
        for i in range(0, self.cur_img_index - 1):
            if self.img_list[self.cur_img_index].same_folder(self.img_list[i]):
                return i

        return self.cur_img_index + 1

    def load(self):
        source_path = self.getImageRootPath()
        self.img_list = self._buildImageListFromSourcePath(source_path) if source_path else []

        if len(self.img_list) == 0:
            if source_path:
                print('No supported images found in source: {0}'.format(source_path))
            print('No image source selected. Use File -> Set Image Source...')
            self.cur_timer = self.max_timer_value
            return

        # Restore per-path playback settings (if any).
        self.applyPlaybackStateForCurrentPath()

        # randomize first cycle order in random mode
        restored_saved_order = self._restore_saved_image_order_for_current_path()
        if self.random_play_mode and not restored_saved_order:
            self.shuffle_cycle()

        self.restoreLastImagePosition()

        print('{} images found'.format(len(self.img_list)))

    def append_img(self, img):
        self.img_list.append(img)

    def update_list(self, force=False):
        if not force and not self.random_play_mode:
            return

        if (self.cur_img_index + 1) >= len(self.img_list):
            return

        # make copy
        img_list_copy = self.img_list[(self.cur_img_index + 1):]

        # shuffle it
        random.shuffle(img_list_copy)

        # return temporary list to the back of the list
        self.img_list[(self.cur_img_index + 1):] = img_list_copy

    def shuffle_cycle(self, prev_img=None):
        random.shuffle(self.img_list)

        # avoid showing the same image twice when switching to next cycle
        if prev_img is not None and len(self.img_list) > 1 and self.img_list[0] is prev_img:
            swap_index = random.randrange(1, len(self.img_list))
            self.img_list[0], self.img_list[swap_index] = self.img_list[swap_index], self.img_list[0]

    def isRandomPlayMode(self):
        return self.random_play_mode

    def togglePlayMode(self):
        self.random_play_mode = not self.random_play_mode

        if self.random_play_mode:
            self.update_list(force=True)

        self._capture_current_path_playback_state(save_to_disk=True)
        self.saveConfig()

        mode = 'random' if self.random_play_mode else 'sequential'
        print('Playback mode: {0}'.format(mode))

        return self.random_play_mode

    def getCurTimer(self, decrement=True):
        if not self.hasImages():
            return '--:--'

        if self.timer_paused:
            if self.timer_expired_hold and self.timer_end_mode == timer_end_mode_overtime:
                return '+{:02d}:{:02d}'.format(
                    int(self.timer_overtime_seconds / 60),
                    int(self.timer_overtime_seconds % 60)
                )
            if self.timer_expired_hold:
                return '00:00'
            return '{:02d}:{:02d}'.format(int(self.cur_timer / 60), int(self.cur_timer % 60))

        if self.timer_expired_hold:
            if self.timer_end_mode == timer_end_mode_overtime:
                if decrement:
                    self.timer_overtime_seconds += 1
                return '+{:02d}:{:02d}'.format(
                    int(self.timer_overtime_seconds / 60),
                    int(self.timer_overtime_seconds % 60)
                )
            return '00:00'

        if decrement:
            self.cur_timer -= 1

        if self.cur_timer <= 0:
            if self.timer_end_mode == timer_end_mode_auto_next:
                self.change(1)

                # we must return expired to actually change image
                # when we go back in this function to change timer value
                return 'expired'

            self.cur_timer = 0
            self.timer_expired_hold = True
            self.timer_overtime_seconds = 0
            return '00:00'

        return '{:02d}:{:02d}'.format(int(self.cur_timer / 60), int(self.cur_timer % 60))

    def getCurTimerColor(self):
        if not self.hasImages():
            return 'gray'

        if self.timer_paused:
            return 'yellow'

        if self.timer_expired_hold:
            return 'red'

        if self.cur_timer <= 5:
            return 'red'

        return 'white'

    def getTimerSeconds(self):
        return self.max_timer_value

    def getTimerEndMode(self):
        return self.timer_end_mode

    def isPrestartCountdownEnabled(self):
        return self.prestart_countdown_enabled

    def togglePrestartCountdownEnabled(self):
        self.prestart_countdown_enabled = not self.prestart_countdown_enabled
        self.saveConfig()
        return self.prestart_countdown_enabled

    def isColorPracticeEnabled(self):
        return self.app_mode in (app_mode_color_blocks, app_mode_color_photo)

    def setColorPracticeEnabled(self, enabled):
        new_value = self._to_bool(enabled, default_color_practice_enabled)
        target_mode = app_mode_color_blocks if new_value else app_mode_photo_switching
        return self.setAppMode(target_mode)

    def getAppMode(self):
        return self.app_mode

    def setAppMode(self, mode):
        normalized = self._normalize_app_mode(mode)
        if normalized == '':
            return False
        if self.app_mode == normalized:
            return False

        # Persist outgoing mode state first.
        self.saveResumeState()
        self._sync_runtime_into_mode_states()

        self.app_mode = normalized
        self._apply_mode_state_to_runtime()

        if self.app_mode in (app_mode_photo_switching, app_mode_color_photo):
            self.load()
            if self.hasImages():
                self.change(1)
        else:
            self.img_list = []
            self.cur_img_index = 0
            self.cur_image_path = ''

        self.saveConfig()
        return True

    def getPlaybackProfile(self):
        return self.playback_profile

    def setPlaybackProfile(self, profile):
        normalized = str(profile).strip().lower()
        if normalized not in playback_profiles:
            return False
        target_mode = app_mode_color_photo if normalized == playback_profile_color_photo else app_mode_photo_switching
        return self.setAppMode(target_mode)

    def getColorPracticeSubMode(self):
        return self.color_practice_sub_mode

    def setColorPracticeSubMode(self, mode):
        normalized = str(mode).strip().lower()
        if normalized not in color_practice_sub_modes:
            return False
        target_mode = app_mode_color_blocks if normalized == 'palette' else app_mode_color_photo
        return self.setAppMode(target_mode)

    def getColorPracticeThresholds(self):
        blocks_mode = self.mode_states.get(app_mode_color_blocks, {})
        return {
            'min_luma': self._to_float(blocks_mode.get('min_luma', default_color_practice_min_luma), default_color_practice_min_luma),
            'max_luma': self._to_float(blocks_mode.get('max_luma', default_color_practice_max_luma), default_color_practice_max_luma),
            'min_saturation': self._to_float(
                blocks_mode.get('min_saturation', default_color_practice_min_saturation),
                default_color_practice_min_saturation
            ),
        }

    def setColorPracticeThresholds(self, min_luma, max_luma, min_saturation):
        blocks_mode = self.mode_states.get(app_mode_color_blocks, {})
        cur_min_luma = self._clamp_unit_interval(
            self._to_float(blocks_mode.get('min_luma', default_color_practice_min_luma), default_color_practice_min_luma)
        )
        cur_max_luma = self._clamp_unit_interval(
            self._to_float(blocks_mode.get('max_luma', default_color_practice_max_luma), default_color_practice_max_luma)
        )
        cur_min_saturation = self._clamp_unit_interval(
            self._to_float(blocks_mode.get('min_saturation', default_color_practice_min_saturation), default_color_practice_min_saturation)
        )

        next_min_luma = self._clamp_unit_interval(self._to_float(min_luma, cur_min_luma))
        next_max_luma = self._clamp_unit_interval(self._to_float(max_luma, cur_max_luma))
        next_min_saturation = self._clamp_unit_interval(
            self._to_float(min_saturation, cur_min_saturation)
        )

        if next_min_luma > next_max_luma:
            return False

        if (
            cur_min_luma == next_min_luma
            and cur_max_luma == next_max_luma
            and cur_min_saturation == next_min_saturation
        ):
            return False

        blocks_mode['min_luma'] = next_min_luma
        blocks_mode['max_luma'] = next_max_luma
        blocks_mode['min_saturation'] = next_min_saturation
        if self.app_mode == app_mode_color_blocks:
            self.color_practice_min_luma = next_min_luma
            self.color_practice_max_luma = next_max_luma
            self.color_practice_min_saturation = next_min_saturation
        self.saveConfig()
        return True

    def getColorBlocksSettings(self):
        blocks_mode = self.mode_states.get(app_mode_color_blocks, {})
        return {
            'stripe_count': int(max(1, self._to_float(blocks_mode.get('stripe_count', 1), 1))),
            'min_luma': self._to_float(blocks_mode.get('min_luma', default_color_practice_min_luma), default_color_practice_min_luma),
            'max_luma': self._to_float(blocks_mode.get('max_luma', default_color_practice_max_luma), default_color_practice_max_luma),
            'min_saturation': self._to_float(
                blocks_mode.get('min_saturation', default_color_practice_min_saturation),
                default_color_practice_min_saturation
            ),
            'shape_mode_enabled': self._to_bool(
                blocks_mode.get('shape_mode_enabled', default_color_blocks_shape_mode_enabled),
                default_color_blocks_shape_mode_enabled
            ),
        }

    def setColorBlocksSettings(self, stripe_count, min_luma, max_luma, min_saturation):
        blocks_mode = self.mode_states.get(app_mode_color_blocks, {})
        try:
            next_stripe_count = int(stripe_count)
        except (TypeError, ValueError):
            next_stripe_count = int(max(1, self._to_float(blocks_mode.get('stripe_count', 1), 1)))
        next_stripe_count = max(1, min(20, next_stripe_count))

        next_min_luma = self._clamp_unit_interval(self._to_float(min_luma, blocks_mode.get('min_luma', default_color_practice_min_luma)))
        next_max_luma = self._clamp_unit_interval(self._to_float(max_luma, blocks_mode.get('max_luma', default_color_practice_max_luma)))
        next_min_saturation = self._clamp_unit_interval(self._to_float(min_saturation, blocks_mode.get('min_saturation', default_color_practice_min_saturation)))
        if next_min_luma > next_max_luma:
            return False

        if (
            int(max(1, self._to_float(blocks_mode.get('stripe_count', 1), 1))) == next_stripe_count
            and self._to_float(blocks_mode.get('min_luma', default_color_practice_min_luma), default_color_practice_min_luma) == next_min_luma
            and self._to_float(blocks_mode.get('max_luma', default_color_practice_max_luma), default_color_practice_max_luma) == next_max_luma
            and self._to_float(blocks_mode.get('min_saturation', default_color_practice_min_saturation), default_color_practice_min_saturation) == next_min_saturation
        ):
            return False

        blocks_mode['stripe_count'] = next_stripe_count
        blocks_mode['min_luma'] = next_min_luma
        blocks_mode['max_luma'] = next_max_luma
        blocks_mode['min_saturation'] = next_min_saturation
        if self.app_mode == app_mode_color_blocks:
            self.color_practice_min_luma = next_min_luma
            self.color_practice_max_luma = next_max_luma
            self.color_practice_min_saturation = next_min_saturation
        self.saveConfig()
        return True

    def getColorBlocksShapeModeEnabled(self):
        blocks_mode = self.mode_states.get(app_mode_color_blocks, {})
        return self._to_bool(
            blocks_mode.get('shape_mode_enabled', default_color_blocks_shape_mode_enabled),
            default_color_blocks_shape_mode_enabled
        )

    def setColorBlocksShapeModeEnabled(self, enabled):
        blocks_mode = self.mode_states.get(app_mode_color_blocks, {})
        new_value = self._to_bool(enabled, default_color_blocks_shape_mode_enabled)
        if self._to_bool(
            blocks_mode.get('shape_mode_enabled', default_color_blocks_shape_mode_enabled),
            default_color_blocks_shape_mode_enabled
        ) == new_value:
            return False
        blocks_mode['shape_mode_enabled'] = new_value
        self.saveConfig()
        return True

    def getColorPhotoCrystallizeEnabled(self):
        color_photo_mode = self.mode_states.get(app_mode_color_photo, {})
        return self._to_bool(color_photo_mode.get('crystallize_enabled', False), False)

    def setColorPhotoCrystallizeEnabled(self, enabled):
        color_photo_mode = self.mode_states.get(app_mode_color_photo, {})
        new_value = self._to_bool(enabled, False)
        if self._to_bool(color_photo_mode.get('crystallize_enabled', False), False) == new_value:
            return False
        color_photo_mode['crystallize_enabled'] = new_value
        self.saveConfig()
        return True

    def setTimerSeconds(self, seconds):
        if seconds <= 0:
            return False

        self.max_timer_value = seconds
        self.cur_timer = self.max_timer_value
        self.timer_expired_hold = False
        self.timer_overtime_seconds = 0
        self._capture_current_path_playback_state(save_to_disk=True)
        self.saveConfig()
        print('Timer value set to {0} second(s).'.format(self.max_timer_value))
        return True

    def isStayOnTop(self):
        return self.stay_on_top

    def toggleStayOnTop(self):
        self.stay_on_top = not self.stay_on_top
        self.saveConfig()
        return self.stay_on_top

    def isAutoNextOnTimerEnd(self):
        return self.timer_end_mode == timer_end_mode_auto_next

    def isTimerExpiredHold(self):
        return self.timer_expired_hold

    def isTimerPaused(self):
        return self.timer_paused

    def setTimerEndMode(self, mode):
        normalized = self._normalize_timer_end_mode(mode)
        if normalized == '':
            return False

        if self.timer_end_mode == normalized:
            return False

        self.timer_end_mode = normalized
        advanced = False

        # If the timer had already expired in hold mode, continue immediately when auto-next is enabled.
        if self.timer_end_mode == timer_end_mode_auto_next and self.timer_expired_hold and self.hasImages() and not self.timer_paused:
            self.change(1)
            advanced = True
        elif self.timer_end_mode != timer_end_mode_overtime:
            self.timer_overtime_seconds = 0

        self._capture_current_path_playback_state(save_to_disk=True)
        self.saveConfig()
        return advanced

    def cycleTimerEndMode(self):
        idx = timer_end_modes.index(self.timer_end_mode)
        next_mode = timer_end_modes[(idx + 1) % len(timer_end_modes)]
        self.setTimerEndMode(next_mode)
        return self.timer_end_mode

    # Backward compatibility for older caller.
    def setAutoNextOnTimerEnd(self, enabled):
        return self.setTimerEndMode(timer_end_mode_auto_next if bool(enabled) else timer_end_mode_hold)

    def toggleAutoNextOnTimerEnd(self):
        if self.timer_end_mode == timer_end_mode_auto_next:
            return self.setTimerEndMode(timer_end_mode_hold)
        return self.setTimerEndMode(timer_end_mode_auto_next)

    def pause(self):
        if self.timer_paused:
            self.timer_paused = False
            print('Unpaused ... ')
        else:
            self.timer_paused = True
            print('Paused ... ')

    def resetTimer(self):
        self.cur_timer = self.max_timer_value
        self.timer_expired_hold = False
        self.timer_overtime_seconds = 0
        print('Timer reset to {0} second(s).'.format(self.max_timer_value))

    def _setCurrentImageByIndex(self, index):
        if not self.hasImages():
            self.cur_image_path = ''
            self.cur_timer = self.max_timer_value
            self.timer_expired_hold = False
            self.timer_overtime_seconds = 0
            return False

        index_int = int(index)
        if index_int < 0 or index_int >= len(self.img_list):
            return False

        if self.cur_image_path != '':
            self.total_time_spent += (self.max_timer_value - max(self.cur_timer, 0))
            print('Image {0} took {1} second(s).'.format(self.cur_img_index, self.max_timer_value - self.cur_timer))

        self.cur_timer = self.max_timer_value
        self.timer_expired_hold = False
        self.timer_overtime_seconds = 0

        if self.timer_paused:
            self.pause()

        self.cur_img_index = index_int
        self.cur_image_path = self.img_list[self.cur_img_index].get_path()
        self.last_image_path = self.cur_image_path
        self._capture_current_path_playback_state(save_to_disk=True)
        return True

    def resetImageOrderAndPickRandom(self):
        if not self.hasImages():
            return False

        if self.random_play_mode:
            self.shuffle_cycle()

        target_index = random.randrange(0, len(self.img_list))
        if len(self.img_list) > 1 and target_index == self.cur_img_index:
            target_index = (target_index + 1) % len(self.img_list)

        return self._setCurrentImageByIndex(target_index)

    def change(self, direction):
        if not self.hasImages():
            self.cur_image_path = ''
            self.cur_timer = self.max_timer_value
            self.timer_expired_hold = False
            self.timer_overtime_seconds = 0
            return

        # if it's not the first run - save and print some stats
        if self.cur_image_path != '':
            self.total_time_spent += (self.max_timer_value - max(self.cur_timer, 0))
            print('Image {0} took {1} second(s).'.format(self.cur_img_index, self.max_timer_value - self.cur_timer))

        self.cur_timer = self.max_timer_value
        self.timer_expired_hold = False
        self.timer_overtime_seconds = 0

        # unpause if was paused
        if self.timer_paused:
            self.pause()

        # set label default color
        # timeImgLabel.config(foreground=timer_foreground_color)

        # next image index
        if direction == 2:
            # next image in same folder as current image
            self.cur_img_index = self.getIndexOfNextImageInSameFolder()
        elif direction == -2:
            # prev image in same folder as current image
            self.cur_img_index = self.getIndexOfPrevImageInSameFolder()
        else:
            self.cur_img_index += direction

        if self.cur_img_index == len(self.img_list):
            if direction == 1 and self.random_play_mode:
                prev_img = self.img_list[-1]
                self.shuffle_cycle(prev_img)
            self.cur_img_index = 0
        elif self.cur_img_index < 0:
            self.cur_img_index = len(self.img_list) - 1

        self.cur_image_path = self.img_list[self.cur_img_index].get_path()
        self.last_image_path = self.cur_image_path
        self._capture_current_path_playback_state(save_to_disk=True)

        # timeImgLabel.config(image=cur_photo)

        # imgFileNameLabel.config(text=img_list[cur_img_index].get_path(), wraplength=cur_window_width)

class ImagePath:
    """Path to image"""

    def __init__(self, par, img_path):
        # ptr to ImageList
        self.parent = par

        self.img_path = img_path

    def get_path(self):
        return self.img_path

    def get_resume_key(self):
        return 'file::{0}'.format(self.parent._path_key(self.img_path))

    def get_folder(self):
        return Path(self.img_path).parent

    def same_folder(self, other):
        return self.get_folder() == other.get_folder()


class ImagePathInZip(ImagePath):
    """Path to the zip with image in it + image file stored in this zip file
    If img_path empty - read image list from zip"""

    def __init__(self, par, zip_path, img_path, temp_path):
        super().__init__(par, img_path)

        # path to archive
        self.zip_path = zip_path

        # one temporary directory for all zip archive
        self.temp_path = temp_path

        # if image was opened from archive - keep path to it here
        self.real_path_to_img = ''

    def get_folder(self):
        return self.zip_path

    def get_path(self):
        global cur_img_index

        if len(self.real_path_to_img) != 0:
            return self.real_path_to_img

        with ZipFile(self.zip_path, 'r') as zipObj:

            # if img_path empty - read all images from zip
            if not self.img_path or self.img_path == '':
                # create temp directory
                temp_path = tempfile.TemporaryDirectory(prefix=splitext(basename(self.zip_path))[0] + '_')

                # save temp path object in global list
                zip_extract_temp_paths.append(temp_path)

                for img_file in zipObj.namelist():
                    if is_file_valid(img_file, image_extensions):
                        if not self.img_path or self.img_path == '':
                            # set image in current element
                            self.img_path = img_file
                            self.temp_path = temp_path.name
                        else:
                            # add other images in list
                            self.parent.append_img(ImagePathInZip(self.parent, self.zip_path, img_file, temp_path.name))

                # shuffle images which go next in list to keep Next/Prev button working (more or less)
                self.parent.update_list()

            if not self.img_path or self.img_path == '':
                # zip without images - don't know what to do
                return ''

            # extract files into temp directory
            zipObj.extract(self.img_path, self.temp_path)

            # save path to temp directory in list
            self.real_path_to_img = join(self.temp_path, self.img_path)

        return self.real_path_to_img

    def get_resume_key(self):
        return 'zip::{0}::{1}'.format(
            self.parent._path_key(self.zip_path),
            str(self.img_path or '').strip()
        )


def is_file_valid(file_name, extensions):
    return any(x in str.lower(file_name) for x in extensions)


def findAllSupportedFiles(path_list, extensions):
    files_list = []

    for path in path_list:
        if not path or not exists(path):
            continue

        for dirpath, dirs, files in walk(path):
            for name in files:
                if is_file_valid(name, extensions):
                    files_list.append(join(dirpath, name))

    return files_list


def toImgList(par, path_list):
    temp_img_list = []

    for path in path_list:
        temp_img_list.append(ImagePath(par, path))

    return temp_img_list


def findAllSupportedZipFiles(par, zip_file_list):
    temp_path_names = []
    for zip_file in zip_file_list:
        if not zip_file or not exists(zip_file):
            print('File {} not found'.format(zip_file))

        with ZipFile(zip_file, 'r') as zipObj:
            # create temp directory
            temp_path = tempfile.TemporaryDirectory()

            # extract files into temp directory
            zipObj.extractall(temp_path.name)

            # save temp path object in global list
            zip_extract_temp_paths.append(temp_path)

            # save path to temp directory in list
            temp_path_names.append(temp_path.name)

    return toImgList(par, findAllSupportedFiles(temp_path_names, image_extensions))


def findAllSupportedZipFilesRandom(par, zip_file_list):
    temp_list = []

    for zip_file in zip_file_list:
        if not zip_file or not exists(zip_file):
            print('File {} not found'.format(zip_file))

        print('File {} found'.format(zip_file))

        temp_list.append(ImagePathInZip(par, zip_file, '', ''))

    return temp_list
