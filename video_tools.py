import json
import os
import re
import shutil
import subprocess
from pathlib import Path


def clamp(value, low, high):
    return max(low, min(high, value))


def format_hhmmss(duration_seconds):
    total = max(0, int(round(float(duration_seconds))))
    hours = total // 3600
    minutes = (total % 3600) // 60
    seconds = total % 60
    return '{0:02d}{1:02d}{2:02d}'.format(hours, minutes, seconds)


def _find_binary_path(name, explicit=''):
    explicit_value = str(explicit or '').strip()
    if explicit_value:
        explicit_path = Path(explicit_value)
        if explicit_path.exists():
            return str(explicit_path)
        return ''

    candidates = []
    for variant in (name, '{0}.exe'.format(name)):
        resolved = shutil.which(variant)
        if resolved:
            candidates.append(resolved)

    local_app_data = os.environ.get('LOCALAPPDATA')
    if local_app_data:
        candidates.append(
            str(Path(local_app_data) / 'Programs' / 'ffmpeg' / 'bin' / '{0}.exe'.format(name))
        )

    candidates.extend([
        '/mnt/c/Users/Admin/AppData/Local/Programs/ffmpeg/bin/{0}.exe'.format(name),
        '/mnt/c/Program Files/ffmpeg/bin/{0}.exe'.format(name),
        '/mnt/c/ffmpeg/bin/{0}.exe'.format(name),
    ])

    for candidate in candidates:
        if candidate and Path(candidate).exists():
            return candidate

    return ''


def find_ffmpeg_tools():
    ffmpeg_path = _find_binary_path('ffmpeg')
    ffprobe_path = _find_binary_path('ffprobe')
    if ffmpeg_path and not ffprobe_path:
        candidate_dir = os.path.dirname(ffmpeg_path)
        candidate_name = 'ffprobe.exe' if os.name == 'nt' else 'ffprobe'
        candidate_path = os.path.join(candidate_dir, candidate_name)
        if os.path.isfile(candidate_path):
            ffprobe_path = candidate_path

    missing = []
    if not ffmpeg_path:
        missing.append('ffmpeg was not found')
    if not ffprobe_path:
        missing.append('ffprobe was not found')

    return {
        'ffmpeg': ffmpeg_path or '',
        'ffprobe': ffprobe_path or '',
        'available': bool(ffmpeg_path and ffprobe_path),
        'missing_reason': '; '.join(missing),
    }


def _path_for_tool(path_value, tool_path):
    value = str(path_value)
    tool_text = str(tool_path or '').lower()
    if not tool_text.endswith('.exe'):
        return value
    if not value.startswith('/mnt/') or len(value) < 7 or value[6] != '/':
        return value
    drive_letter = value[5].upper()
    remainder = value[7:].replace('/', '\\')
    if remainder:
        return '{0}:\\{1}'.format(drive_letter, remainder)
    return '{0}:\\'.format(drive_letter)


def _command_to_log_string(command):
    if os.name == 'nt':
        return subprocess.list2cmdline(command)

    quoted = []
    for part in command:
        part = str(part)
        if part == '':
            quoted.append("''")
        elif re.search(r'[^A-Za-z0-9_@%+=:,./-]', part):
            quoted.append("'" + part.replace("'", "'\"'\"'") + "'")
        else:
            quoted.append(part)
    return ' '.join(quoted)


def _run_command(command, logger=None, check=True):
    if logger is not None:
        logger('Running command: {0}'.format(_command_to_log_string(command)))

    completed = subprocess.run(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding='utf-8',
        errors='replace'
    )

    if logger is not None:
        if completed.stdout.strip():
            logger('stdout:\n{0}'.format(completed.stdout.strip()))
        if completed.stderr.strip():
            logger('stderr:\n{0}'.format(completed.stderr.strip()))

    if check and completed.returncode != 0:
        raise RuntimeError(
            'Command failed with exit code {0}: {1}\nstderr:\n{2}'.format(
                completed.returncode,
                _command_to_log_string(command),
                (completed.stderr or '').strip()
            )
        )

    return completed


def ffprobe_json(ffprobe_path, input_path):
    command = [
        ffprobe_path,
        '-v', 'error',
        '-show_entries', 'format=duration:stream=codec_type,width,height,avg_frame_rate',
        '-of', 'json',
        _path_for_tool(input_path, ffprobe_path),
    ]
    completed = _run_command(command, logger=None, check=True)
    return json.loads(completed.stdout or '{}')


def parse_fps(raw_value):
    if not raw_value or raw_value == '0/0':
        return 30.0
    if '/' in raw_value:
        left, right = raw_value.split('/', 1)
        denominator = float(right or 1)
        if denominator == 0:
            return 30.0
        return float(left) / denominator
    return float(raw_value)


def probe_video(ffprobe_path, input_path):
    data = ffprobe_json(ffprobe_path, input_path)
    streams = data.get('streams') or []
    stream = next((item for item in streams if item.get('codec_type') == 'video' and item.get('width')), None)
    if not stream:
        raise RuntimeError('No video stream found in {0}'.format(input_path))

    duration = float((data.get('format') or {}).get('duration') or 0.0)
    if duration <= 0:
        raise RuntimeError('Could not read duration from {0}'.format(input_path))

    return {
        'duration': duration,
        'width': int(stream['width']),
        'height': int(stream['height']),
        'fps': parse_fps(stream.get('avg_frame_rate')),
    }


def even_size(width, height):
    out_width = width if width % 2 == 0 else width - 1
    out_height = height if height % 2 == 0 else height - 1
    return max(out_width, 2), max(out_height, 2)


def find_font_path():
    candidates = [
        'C:/Windows/Fonts/arial.ttf',
        'C:/Windows/Fonts/segoeui.ttf',
        'C:/Windows/Fonts/msyh.ttc',
        'C:/Windows/Fonts/simhei.ttf',
        '/mnt/c/Windows/Fonts/arial.ttf',
        '/mnt/c/Windows/Fonts/segoeui.ttf',
        '/mnt/c/Windows/Fonts/msyh.ttc',
        '/mnt/c/Windows/Fonts/simhei.ttf',
        '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
    ]
    for candidate in candidates:
        if Path(candidate).exists():
            return candidate
    return ''


def _escape_drawtext_value(value):
    escaped = str(value or '')
    escaped = escaped.replace('\\', '\\\\')
    escaped = escaped.replace(':', '\\:')
    escaped = escaped.replace("'", "\\'")
    escaped = escaped.replace('%', '\\%')
    escaped = escaped.replace('[', '\\[')
    escaped = escaped.replace(']', '\\]')
    return escaped


def generate_text_watermark(path, text, width, height, ffmpeg_path, logger=None):
    canvas_width = max(320, int(width * 0.72))
    canvas_height = max(140, int(height * 0.24))
    font_size = max(28, int(min(width, height) * 0.09))
    stroke_width = max(1, int(min(width, height) * 0.004))
    filter_parts = [
        'format=rgba',
        'drawtext=text=\'{text}\':fontsize={font_size}:fontcolor=white:borderw={stroke_width}:bordercolor=black@0.70:x=(w-text_w)/2:y=(h-text_h)/2'.format(
            text=_escape_drawtext_value(text),
            font_size=font_size,
            stroke_width=stroke_width,
        ),
    ]

    font_path = find_font_path()
    if font_path:
        filter_parts[1] = 'drawtext=fontfile=\'{fontfile}\':text=\'{text}\':fontsize={font_size}:fontcolor=white:borderw={stroke_width}:bordercolor=black@0.70:x=(w-text_w)/2:y=(h-text_h)/2'.format(
            fontfile=_escape_drawtext_value(font_path),
            text=_escape_drawtext_value(text),
            font_size=font_size,
            stroke_width=stroke_width,
        )

    command = [
        ffmpeg_path,
        '-y',
        '-f', 'lavfi',
        '-i', 'color=c=black@0.0:s={0}x{1}:r=1'.format(canvas_width, canvas_height),
        '-frames:v', '1',
        '-vf', ','.join(filter_parts),
        '-pix_fmt', 'rgba',
        _path_for_tool(path, ffmpeg_path),
    ]
    _run_command(command, logger=logger, check=True)


def generate_noise_overlay(path, width, height, ffmpeg_path, logger=None):
    tile_width = max(640, width)
    tile_height = max(640, height)
    command = [
        ffmpeg_path,
        '-y',
        '-f', 'lavfi',
        '-i', 'color=c=gray:s={0}x{1}:r=1'.format(tile_width, tile_height),
        '-frames:v', '1',
        '-vf', 'noise=alls=100:allf=u,boxblur=1:1,format=rgb24',
        _path_for_tool(path, ffmpeg_path),
    ]
    _run_command(command, logger=logger, check=True)


def generated_paths(input_path):
    path_obj = Path(input_path)
    stem = path_obj.stem
    parent = path_obj.parent
    return {
        'temp_video': parent / '{0}_tmp.mp4'.format(stem),
        'noise': parent / '{0}_tmp_noise.png'.format(stem),
        'watermark': parent / '{0}_tmp_watermark.png'.format(stem),
    }


def build_output_path(input_path, seconds=None, processed_duration=None):
    path_obj = Path(input_path)
    if seconds is not None and processed_duration is not None:
        return str(path_obj.parent / '{0}_{1}_{2}s.mp4'.format(
            path_obj.stem,
            format_hhmmss(processed_duration),
            int(seconds)
        ))
    return str(path_obj.parent / '{0}_out.mp4'.format(path_obj.stem))


def _build_timeline(seconds, processed_duration, fps):
    still_duration = 1.0
    if seconds < 2:
        still_duration = max(0.0, float(seconds) / 2.0)
    main_duration = max(0.0, float(seconds) - (2.0 * still_duration))
    still_frames = max(1, int(round(still_duration * fps))) if still_duration > 0 else 1
    still_loops = max(0, still_frames - 1)
    pts_factor = 1.0
    if main_duration > 0:
        pts_factor = main_duration / max(float(processed_duration), 0.001)
    return {
        'still_duration': still_duration,
        'main_duration': main_duration,
        'still_loops': still_loops,
        'pts_factor': pts_factor,
    }


def build_filter_complex(
    seconds,
    processed_duration,
    fps,
    width,
    height,
    overlay_mode,
    noise_opacity,
    watermark_opacity,
    include_watermark,
):
    filters = []
    timeline = _build_timeline(seconds, processed_duration, fps)
    input_index = 2

    filters.append(
        '[1:v]'
        'reverse,'
        'trim=end_frame=1,'
        'loop=loop={0}:size=1:start=0,'.format(timeline['still_loops']) +
        'setpts=N/({0}*TB),'.format(fps) +
        'fps={0},'.format(fps) +
        'scale=trunc(iw/2)*2:trunc(ih/2)*2:flags=lanczos,'
        'setsar=1,'
        'format=rgba,'
        'trim=duration={0:.6f}[still]'.format(timeline['still_duration'])
    )
    filters.append('[still]split=2[intro][outro]')

    if timeline['main_duration'] > 0:
        filters.append(
            '[0:v]'
            'setpts={0:.10f}*(PTS-STARTPTS),'.format(timeline['pts_factor']) +
            'fps={0},'.format(fps) +
            'scale=trunc(iw/2)*2:trunc(ih/2)*2:flags=lanczos,'
            'setsar=1,'
            'format=rgba,'
            'trim=duration={0:.6f}[main]'.format(timeline['main_duration'])
        )
        filters.append('[intro][main][outro]concat=n=3:v=1:a=0[base0]')
    else:
        filters.append('[intro][outro]concat=n=2:v=1:a=0[base0]')

    current = 'base0'
    filters.append('[{0}]unsharp=5:5:0.25:5:5:0.0[base_sharp]'.format(current))
    current = 'base_sharp'

    if overlay_mode == 'noise':
        filters.append(
            '[{0}:v]'.format(input_index) +
            'scale={0}:{1}:flags=lanczos,'.format(width, height) +
            'format=rgba,'
            'colorchannelmixer=aa={0:.3f}[noise]'.format(clamp(noise_opacity, 0.0, 1.0))
        )
        filters.append('[{0}][noise]overlay=0:0:format=auto[base_noise]'.format(current))
        current = 'base_noise'
        input_index += 1

    if include_watermark:
        filters.append(
            '[{0}:v]'.format(input_index) +
            'scale={0}:{1}:flags=lanczos,'.format(width, height) +
            'format=rgba,'
            'colorchannelmixer=aa={0:.3f}[wm]'.format(clamp(watermark_opacity, 0.0, 1.0))
        )
        filters.append('[{0}][wm]overlay=0:0:format=auto[v]'.format(current))
    else:
        filters.append('[{0}]null[v]'.format(current))

    return ';'.join(filters), timeline


def create_static_assets(width, height, paths, watermark_image, watermark_text, overlay_mode, ffmpeg_path, logger=None):
    created = []
    watermark_asset = watermark_image

    if overlay_mode == 'noise':
        generate_noise_overlay(paths['noise'], width, height, ffmpeg_path, logger=logger)
        created.append(paths['noise'])

    if watermark_text and not watermark_image:
        generate_text_watermark(paths['watermark'], watermark_text, width, height, ffmpeg_path, logger=logger)
        created.append(paths['watermark'])
        watermark_asset = paths['watermark']

    return created, watermark_asset


def iter_cleanup(paths):
    for path in paths:
        path_obj = Path(path)
        if path_obj.exists():
            if path_obj.is_dir():
                shutil.rmtree(str(path_obj), ignore_errors=True)
            else:
                path_obj.unlink()


def _resolve_export_output_path(input_path, seconds, processed_duration, requested_output_path):
    auto_output = Path(build_output_path(input_path, seconds=seconds, processed_duration=processed_duration))
    requested_value = str(requested_output_path or '').strip()
    if not requested_value:
        return auto_output

    requested_path = Path(requested_value)
    legacy_default = Path(build_output_path(input_path))
    if requested_path == legacy_default:
        return auto_output
    return requested_path


def export_protected_short_video(
    ffmpeg_path,
    ffprobe_path,
    input_path,
    output_path,
    target_total_duration,
    watermark_path='',
    watermark_text='',
    overlay='noise',
    noise_opacity=0.12,
    watermark_opacity=0.36,
    crf=22,
    preset='medium',
    keep_temp=False,
    logger=None,
):
    ffmpeg_value = str(ffmpeg_path or '').strip()
    ffprobe_value = str(ffprobe_path or '').strip()
    if not ffmpeg_value or not ffprobe_value:
        raise RuntimeError('ffmpeg and ffprobe are required')

    input_path_obj = Path(str(input_path or '')).expanduser().resolve()
    if not input_path_obj.is_file():
        raise RuntimeError('Input video does not exist')

    try:
        target_seconds = int(target_total_duration)
    except (TypeError, ValueError):
        raise RuntimeError('Target duration must be an integer')
    if target_seconds <= 0:
        raise RuntimeError('Target duration must be greater than 0 seconds')

    overlay_mode = str(overlay or 'noise').strip().lower()
    if overlay_mode not in ('off', 'noise'):
        raise RuntimeError('Overlay mode must be off or noise')

    watermark_image = None
    watermark_path_value = str(watermark_path or '').strip()
    if watermark_path_value:
        watermark_image = Path(watermark_path_value).expanduser().resolve()
        if not watermark_image.is_file():
            raise RuntimeError('Watermark image does not exist')

    watermark_text_value = str(watermark_text or '').strip()
    if watermark_image is None and watermark_text_value == '':
        raise RuntimeError('Provide a watermark image or watermark text')

    source_meta = probe_video(ffprobe_value, input_path_obj)
    width, height = even_size(source_meta['width'], source_meta['height'])
    output_fps = 30
    path_map = generated_paths(input_path_obj)
    temp_video = path_map['temp_video']
    cleanup_targets = []

    if logger is not None:
        logger('Input: {0}'.format(input_path_obj))
        logger('Temp video: {0}'.format(temp_video))

    try:
        dedupe_cmd = [
            ffmpeg_value,
            '-y',
            '-i', _path_for_tool(input_path_obj, ffmpeg_value),
            '-vf', (
                'mpdecimate=hi=64*8:lo=64*3:frac=0.10:keep=6,'
                'setpts=N/({0:.10f}*TB)'.format(max(source_meta['fps'], 1.0))
            ),
            '-an',
            '-c:v', 'libx264',
            '-crf', '18',
            '-preset', 'veryfast',
            _path_for_tool(temp_video, ffmpeg_value),
        ]
        _run_command(dedupe_cmd, logger=logger, check=True)
        cleanup_targets.append(temp_video)

        processed_meta = probe_video(ffprobe_value, temp_video)
        resolved_output_path = _resolve_export_output_path(
            input_path_obj,
            target_seconds,
            processed_meta['duration'],
            output_path,
        )
        if logger is not None:
            logger('Decimated duration: {0}'.format(format_hhmmss(processed_meta['duration'])))
            logger('Output: {0}'.format(resolved_output_path))
            if resolved_output_path.exists():
                logger('Output file already exists and will be overwritten: {0}'.format(resolved_output_path))

        created_assets, watermark_asset = create_static_assets(
            width=width,
            height=height,
            paths=path_map,
            watermark_image=watermark_image,
            watermark_text=watermark_text_value,
            overlay_mode=overlay_mode,
            ffmpeg_path=ffmpeg_value,
            logger=logger,
        )
        cleanup_targets.extend(created_assets)

        filter_complex, timeline = build_filter_complex(
            seconds=target_seconds,
            processed_duration=processed_meta['duration'],
            fps=output_fps,
            width=width,
            height=height,
            overlay_mode=overlay_mode,
            noise_opacity=noise_opacity,
            watermark_opacity=watermark_opacity,
            include_watermark=watermark_asset is not None,
        )

        render_cmd = [
            ffmpeg_value,
            '-y',
            '-i', _path_for_tool(temp_video, ffmpeg_value),
            '-sseof', '-1',
            '-i', _path_for_tool(input_path_obj, ffmpeg_value),
        ]
        if overlay_mode == 'noise':
            render_cmd.extend(['-loop', '1', '-i', _path_for_tool(path_map['noise'], ffmpeg_value)])
        if watermark_asset is not None:
            render_cmd.extend(['-loop', '1', '-i', _path_for_tool(watermark_asset, ffmpeg_value)])

        render_cmd.extend([
            '-filter_complex', filter_complex,
            '-map', '[v]',
            '-an',
            '-t', str(target_seconds),
            '-c:v', 'libx264',
            '-pix_fmt', 'yuv420p',
            '-crf', str(int(crf)),
            '-preset', str(preset),
            '-movflags', '+faststart',
            _path_for_tool(resolved_output_path, ffmpeg_value),
        ])
        _run_command(render_cmd, logger=logger, check=True)

        final_meta = probe_video(ffprobe_value, resolved_output_path)
        return {
            'output_path': str(resolved_output_path),
            'input_duration': float(source_meta['duration']),
            'processed_source_duration': float(processed_meta['duration']),
            'final_duration': float(final_meta['duration']),
            'pts_factor': float(timeline['pts_factor']),
            'overlay': overlay_mode,
            'audio_preserved': False,
            'watermark_mode': 'image' if watermark_image is not None else 'text',
        }
    finally:
        if not keep_temp:
            iter_cleanup(cleanup_targets)
