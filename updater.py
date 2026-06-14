import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from urllib.parse import urlparse

try:
    from version import __version__ as APP_VERSION
except ImportError:
    APP_VERSION = '0.0.0-dev'

GITHUB_OWNER = 'CasseShimada'
GITHUB_REPO = 'justdraw'
GITHUB_API_LATEST_RELEASE = 'https://api.github.com/repos/{0}/{1}/releases/latest'.format(GITHUB_OWNER, GITHUB_REPO)
GITHUB_RELEASES_URL = 'https://github.com/{0}/{1}/releases/latest'.format(GITHUB_OWNER, GITHUB_REPO)
WINDOWS_EXE_ASSET_NAME = 'JustDraw.exe'
WINDOWS_SHA256_ASSET_NAME = 'JustDraw.exe.sha256'


def is_packaged_windows():
    return sys.platform.startswith('win') and bool(getattr(sys, 'frozen', False))


def normalize_version(value):
    text = str(value or '').strip()
    if text.lower().startswith('v'):
        text = text[1:]
    return text


def version_key(value):
    normalized = normalize_version(value)
    key = []
    for part in re.split(r'([0-9]+|[A-Za-z]+)', normalized):
        if part == '' or part in ('.', '-', '_', '+'):
            continue
        if part.isdigit():
            key.append((1, int(part)))
        elif part.isalpha():
            key.append((0, part.lower()))
        else:
            key.append((0, part.lower()))
    return key


def is_newer_version(remote_version, current_version):
    remote = normalize_version(remote_version)
    current = normalize_version(current_version)
    if remote == '' or current == '':
        return False
    return version_key(remote) > version_key(current)


def _quote_ps_string(value):
    return "'" + str(value).replace("'", "''") + "'"


class UpdateError(Exception):
    pass


class ReleaseInfo:
    def __init__(self, tag_name='', name='', html_url='', exe_url='', sha256_url='', body=''):
        self.tag_name = tag_name
        self.name = name
        self.html_url = html_url
        self.exe_url = exe_url
        self.sha256_url = sha256_url
        self.body = body

    @property
    def version(self):
        return normalize_version(self.tag_name)

    def to_dict(self):
        return {
            'tag_name': self.tag_name,
            'name': self.name,
            'html_url': self.html_url,
            'exe_url': self.exe_url,
            'sha256_url': self.sha256_url,
            'body': self.body,
        }


def find_curl_exe():
    if not sys.platform.startswith('win'):
        return shutil.which('curl') or ''

    candidates = [
        os.path.join(os.environ.get('SystemRoot', r'C:\Windows'), 'System32', 'curl.exe'),
        os.path.join(os.environ.get('SystemRoot', r'C:\Windows'), 'Sysnative', 'curl.exe'),
    ]
    for candidate in candidates:
        if os.path.isfile(candidate):
            return candidate
    return shutil.which('curl.exe') or shutil.which('curl') or ''


def validate_proxy_url(proxy_url):
    value = str(proxy_url or '').strip()
    if value == '':
        return ''
    parsed = urlparse(value)
    if parsed.scheme.lower() not in ('http', 'https', 'socks4', 'socks4a', 'socks5', 'socks5h'):
        raise ValueError('Proxy must start with http://, https://, socks4://, or socks5://')
    if not parsed.hostname:
        raise ValueError('Proxy host is required')
    return value


def _run_curl(url, output_path=None, proxy_url='', timeout_seconds=30):
    curl_path = find_curl_exe()
    if curl_path == '':
        raise UpdateError('curl.exe was not found on this Windows installation')

    cmd = [
        curl_path,
        '--fail',
        '--location',
        '--silent',
        '--show-error',
        '--connect-timeout',
        '15',
        '--max-time',
        str(max(1, int(timeout_seconds))),
        '--user-agent',
        'JustDraw/{0}'.format(APP_VERSION),
        '--header',
        'Accept: application/vnd.github+json',
    ]
    if proxy_url:
        cmd.extend(['--proxy', proxy_url])
    if output_path:
        cmd.extend(['--output', output_path])
    cmd.append(url)

    completed = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or '').strip()
        raise UpdateError(detail or 'curl.exe failed with exit code {0}'.format(completed.returncode))
    return completed.stdout


def fetch_latest_release(proxy_url=''):
    proxy = validate_proxy_url(proxy_url)
    raw_json = _run_curl(GITHUB_API_LATEST_RELEASE, proxy_url=proxy, timeout_seconds=30)
    try:
        data = json.loads(raw_json)
    except ValueError as exc:
        raise UpdateError('GitHub release response was not valid JSON') from exc

    assets = data.get('assets', [])
    exe_url = ''
    sha256_url = ''
    if isinstance(assets, list):
        for asset in assets:
            if not isinstance(asset, dict):
                continue
            name = str(asset.get('name', ''))
            download_url = str(asset.get('browser_download_url', ''))
            if name.lower() == WINDOWS_EXE_ASSET_NAME.lower():
                exe_url = download_url
            elif name.lower() == WINDOWS_SHA256_ASSET_NAME.lower():
                sha256_url = download_url

    return ReleaseInfo(
        tag_name=str(data.get('tag_name', '')),
        name=str(data.get('name', '')),
        html_url=str(data.get('html_url', GITHUB_RELEASES_URL)),
        exe_url=exe_url,
        sha256_url=sha256_url,
        body=str(data.get('body', '')),
    )


def download_release_exe(release_info, proxy_url=''):
    if not release_info.exe_url:
        raise UpdateError('The latest release does not include {0}'.format(WINDOWS_EXE_ASSET_NAME))

    temp_dir = tempfile.mkdtemp(prefix='justdraw-update-')
    exe_path = os.path.join(temp_dir, WINDOWS_EXE_ASSET_NAME)
    _run_curl(release_info.exe_url, output_path=exe_path, proxy_url=proxy_url, timeout_seconds=300)
    if not os.path.isfile(exe_path) or os.path.getsize(exe_path) <= 0:
        raise UpdateError('Downloaded update file is empty')

    if release_info.sha256_url:
        sha_path = os.path.join(temp_dir, WINDOWS_SHA256_ASSET_NAME)
        _run_curl(release_info.sha256_url, output_path=sha_path, proxy_url=proxy_url, timeout_seconds=60)
        _verify_sha256(exe_path, sha_path)

    return exe_path


def _verify_sha256(exe_path, sha_path):
    import hashlib
    try:
        with open(sha_path, 'r', encoding='utf-8') as fp:
            expected = fp.read().strip().split()[0].lower()
    except (OSError, IndexError):
        raise UpdateError('Could not read release checksum')

    if not re.fullmatch(r'[0-9a-fA-F]{64}', expected):
        raise UpdateError('Release checksum is invalid')

    digest = hashlib.sha256()
    with open(exe_path, 'rb') as fp:
        for chunk in iter(lambda: fp.read(1024 * 1024), b''):
            digest.update(chunk)
    actual = digest.hexdigest().lower()
    if actual != expected:
        raise UpdateError('Downloaded update checksum did not match the release checksum')


def create_update_script(downloaded_exe_path, target_exe_path=None, restart=True):
    if not sys.platform.startswith('win'):
        raise UpdateError('Automatic replacement is only supported on Windows')

    source_path = os.path.abspath(downloaded_exe_path)
    if target_exe_path is None:
        target_exe_path = sys.executable
    target_path = os.path.abspath(target_exe_path)
    backup_path = target_path + '.old'
    script_path = os.path.join(tempfile.gettempdir(), 'justdraw_apply_update_{0}.ps1'.format(int(time.time())))

    lines = [
        '$ErrorActionPreference = "Stop"',
        '$source = {0}'.format(_quote_ps_string(source_path)),
        '$target = {0}'.format(_quote_ps_string(target_path)),
        '$backup = {0}'.format(_quote_ps_string(backup_path)),
        'Start-Sleep -Milliseconds 800',
        'for ($i = 0; $i -lt 60; $i++) {',
        '    try {',
        '        if (Test-Path -LiteralPath $backup) { Remove-Item -LiteralPath $backup -Force -ErrorAction SilentlyContinue }',
        '        if (Test-Path -LiteralPath $target) { Rename-Item -LiteralPath $target -NewName ([System.IO.Path]::GetFileName($backup)) -Force }',
        '        Move-Item -LiteralPath $source -Destination $target -Force',
        '        if (Test-Path -LiteralPath $backup) { Remove-Item -LiteralPath $backup -Force -ErrorAction SilentlyContinue }',
        '        break',
        '    } catch {',
        '        Start-Sleep -Milliseconds 500',
        '        if ($i -eq 59) { throw }',
        '    }',
        '}',
    ]
    if restart:
        lines.append('Start-Process -FilePath $target')

    with open(script_path, 'w', encoding='utf-8') as fp:
        fp.write('\n'.join(lines) + '\n')
    return script_path


def launch_update_script(script_path):
    if not sys.platform.startswith('win'):
        raise UpdateError('Automatic replacement is only supported on Windows')
    powershell = shutil.which('powershell.exe') or shutil.which('pwsh.exe') or 'powershell.exe'
    subprocess.Popen([
        powershell,
        '-NoProfile',
        '-ExecutionPolicy',
        'Bypass',
        '-File',
        script_path,
    ], close_fds=True)
