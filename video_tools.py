import json
import os
import re
import shutil
import subprocess
import tempfile


def find_ffmpeg_tools():
    ffmpeg_path = shutil.which('ffmpeg')
    ffprobe_path = shutil.which('ffprobe')
    if ffmpeg_path and not ffprobe_path:
        candidate_dir = os.path.dirname(ffmpeg_path)
        candidate_name = 'ffprobe.exe' if os.name == 'nt' else 'ffprobe'
        candidate_path = os.path.join(candidate_dir, candidate_name)
        if os.path.isfile(candidate_path):
            ffprobe_path = candidate_path
    return {
        'ffmpeg': ffmpeg_path or '',
        'ffprobe': ffprobe_path or '',
        'available': bool(ffmpeg_path),
    }


def _run_command(command, logger=None, check=True):
    if logger is not None:
        logger('Running command: {0}'.format(' '.join(command)))
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
        raise RuntimeError(completed.stderr.strip() or 'Command failed with exit code {0}'.format(completed.returncode))
    return completed


def _parse_duration_from_ffmpeg_stderr(stderr_text):
    match = re.search(r'Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)', stderr_text or '')
    if not match:
        return 0.0
    hours = int(match.group(1))
    minutes = int(match.group(2))
    seconds = float(match.group(3))
    return hours * 3600.0 + minutes * 60.0 + seconds


def probe_media(path, ffmpeg_path, ffprobe_path='', logger=None):
    if ffprobe_path:
        command = [
            ffprobe_path,
            '-v', 'error',
            '-print_format', 'json',
            '-show_streams',
            '-show_format',
            path,
        ]
        completed = _run_command(command, logger=logger, check=True)
        data = json.loads(completed.stdout or '{}')
        duration = 0.0
        try:
            duration = float((data.get('format') or {}).get('duration') or 0.0)
        except (TypeError, ValueError):
            duration = 0.0
        has_audio = False
        for stream in data.get('streams') or []:
            if str(stream.get('codec_type', '')).strip().lower() == 'audio':
                has_audio = True
                break
        return {
            'duration': max(0.0, duration),
            'has_audio': has_audio,
        }

    command = [ffmpeg_path, '-hide_banner', '-i', path]
    completed = _run_command(command, logger=logger, check=False)
    stderr_text = completed.stderr or ''
    duration = _parse_duration_from_ffmpeg_stderr(stderr_text)
    has_audio = 'Audio:' in stderr_text
    return {
        'duration': max(0.0, duration),
        'has_audio': has_audio,
    }


def build_atempo_chain(speed_factor):
    factor = max(1.0, float(speed_factor))
    parts = []
    while factor > 2.0:
        parts.append('atempo=2.0')
        factor /= 2.0
    parts.append('atempo={0:.8f}'.format(factor))
    return ','.join(parts)


def build_output_path(input_path):
    base, _ = os.path.splitext(input_path)
    return base + '_out.mp4'


def export_protected_short_video(
    ffmpeg_path,
    ffprobe_path,
    input_path,
    output_path,
    target_total_duration,
    watermark_path,
    logger=None,
):
    if not ffmpeg_path:
        raise RuntimeError('ffmpeg is not available')
    if not input_path or not os.path.isfile(input_path):
        raise RuntimeError('Input video does not exist')
    if not watermark_path or not os.path.isfile(watermark_path):
        raise RuntimeError('Watermark image does not exist')

    try:
        target_total = int(target_total_duration)
    except (TypeError, ValueError):
        raise RuntimeError('Target duration must be an integer')
    if target_total < 15 or target_total > 30:
        raise RuntimeError('Target duration must be between 15 and 30 seconds')

    source_probe = probe_media(input_path, ffmpeg_path, ffprobe_path, logger=logger)
    source_duration = float(source_probe.get('duration') or 0.0)
    if source_duration <= 0.0:
        raise RuntimeError('Could not determine input duration')

    body_target_duration = max(1.0, float(target_total - 1))

    temp_dir = tempfile.mkdtemp(prefix='justdraw_video_')
    try:
        decimated_path = os.path.join(temp_dir, 'decimated.mp4')

        decimate_command = [
            ffmpeg_path,
            '-y',
            '-hide_banner',
            '-i', input_path,
            '-an',
            '-vf', 'mpdecimate,setpts=N/FRAME_RATE/TB,fps=30',
            '-pix_fmt', 'yuv420p',
            '-c:v', 'libx264',
            '-preset', 'medium',
            '-crf', '18',
            '-movflags', '+faststart',
            decimated_path,
        ]

        source_video_path = input_path
        source_video_duration = source_duration
        try:
            _run_command(decimate_command, logger=logger, check=True)
            decimated_probe = probe_media(decimated_path, ffmpeg_path, ffprobe_path, logger=logger)
            decimated_duration = float(decimated_probe.get('duration') or 0.0)
            if decimated_duration >= 0.5:
                source_video_path = decimated_path
                source_video_duration = decimated_duration
            elif logger is not None:
                logger('Decimated video became too short; falling back to original source')
        except Exception as exc:
            if logger is not None:
                logger('Decimation step failed; falling back to original source: {0}'.format(exc))

        speed_factor = max(1.0, source_video_duration / body_target_duration)
        body_duration = source_video_duration / speed_factor
        if body_duration <= 0.05:
            raise RuntimeError('Processed body duration is too short')
        freeze_start = max(0.0, body_duration - (1.0 / 30.0))

        protection_chain = (
            'setpts=PTS/{speed:.10f},'
            'fps=30,'
            'noise=alls=5:allf=t+u,'
            'drawgrid=width=iw:height=4:thickness=1:color=black@0.05,'
            'eq=saturation=1.03:contrast=1.01'
        ).format(speed=speed_factor)

        has_audio = bool(source_probe.get('has_audio'))
        if has_audio:
            atempo_chain = build_atempo_chain(speed_factor)
            filter_complex = (
                '[0:v]{protection}[vbase];'
                '[2:v][vbase]scale2ref=w=\'min(iw,main_w*0.28)\':h=-1[wm][vscaled];'
                '[wm]format=rgba,colorchannelmixer=aa=0.30[wmrgba];'
                '[vscaled][wmrgba]overlay=x=main_w-overlay_w-24:y=main_h-overlay_h-24:format=auto,split=2[vbody][vfreeze];'
                '[vfreeze]trim=start={freeze_start:.6f},setpts=PTS-STARTPTS,select=\'eq(n,0)\',tpad=stop_mode=clone:stop_duration=1[vintr];'
                '[vintr][vbody]concat=n=2:v=1:a=0[vout];'
                '[1:a]aresample=48000,{atempo},atrim=duration={body_duration:.6f},asetpts=PTS-STARTPTS[abody];'
                '[3:a][abody]concat=n=2:v=0:a=1[aout]'
            ).format(
                protection=protection_chain,
                freeze_start=freeze_start,
                atempo=atempo_chain,
                body_duration=body_duration,
            )
            command = [
                ffmpeg_path,
                '-y',
                '-hide_banner',
                '-i', source_video_path,
                '-i', input_path,
                '-loop', '1',
                '-i', watermark_path,
                '-f', 'lavfi',
                '-t', '1',
                '-i', 'anullsrc=channel_layout=stereo:sample_rate=48000',
                '-filter_complex', filter_complex,
                '-map', '[vout]',
                '-map', '[aout]',
                '-c:v', 'libx264',
                '-preset', 'medium',
                '-crf', '18',
                '-pix_fmt', 'yuv420p',
                '-c:a', 'aac',
                '-b:a', '160k',
                '-movflags', '+faststart',
                output_path,
            ]
        else:
            filter_complex = (
                '[0:v]{protection}[vbase];'
                '[1:v][vbase]scale2ref=w=\'min(iw,main_w*0.28)\':h=-1[wm][vscaled];'
                '[wm]format=rgba,colorchannelmixer=aa=0.30[wmrgba];'
                '[vscaled][wmrgba]overlay=x=main_w-overlay_w-24:y=main_h-overlay_h-24:format=auto,split=2[vbody][vfreeze];'
                '[vfreeze]trim=start={freeze_start:.6f},setpts=PTS-STARTPTS,select=\'eq(n,0)\',tpad=stop_mode=clone:stop_duration=1[vintr];'
                '[vintr][vbody]concat=n=2:v=1:a=0[vout]'
            ).format(
                protection=protection_chain,
                freeze_start=freeze_start,
            )
            command = [
                ffmpeg_path,
                '-y',
                '-hide_banner',
                '-i', source_video_path,
                '-loop', '1',
                '-i', watermark_path,
                '-filter_complex', filter_complex,
                '-map', '[vout]',
                '-an',
                '-c:v', 'libx264',
                '-preset', 'medium',
                '-crf', '18',
                '-pix_fmt', 'yuv420p',
                '-movflags', '+faststart',
                output_path,
            ]

        _run_command(command, logger=logger, check=True)

        final_probe = probe_media(output_path, ffmpeg_path, ffprobe_path, logger=logger)
        return {
            'output_path': output_path,
            'input_duration': source_duration,
            'processed_source_duration': source_video_duration,
            'body_duration': body_duration,
            'final_duration': float(final_probe.get('duration') or 0.0),
            'speed_factor': speed_factor,
            'audio_preserved': has_audio,
        }
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
