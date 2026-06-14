import os
import subprocess
import sys


def main():
    project_dir = os.path.dirname(os.path.realpath(__file__))

    try:
        import PyQt6  # noqa: F401
    except ImportError:
        print('PyQt6 is required. Install it first:')
        print('  py -3 -m pip install PyQt6')
        return 1

    # Use the current interpreter so CI and local builds resolve PyInstaller
    # from the same environment that launched this script.
    pyinstaller_cmd = [sys.executable, '-m', 'PyInstaller']

    pyinstaller_cmd.extend([
        '--noconfirm',
        '--clean',
        '--windowed',
        '--onefile',
        '--name',
        'JustDraw',
        '--add-data',
        'main.qml;.',
        '--add-data',
        'images;images',
        '--add-data',
        'version.py;.',
        '--collect-all',
        'PyQt6',
        'justdraw.py',
    ])

    print('Building with PyQt6...')
    print('Command: {0}'.format(' '.join(pyinstaller_cmd)))
    return subprocess.call(pyinstaller_cmd, cwd=project_dir)


if __name__ == '__main__':
    raise SystemExit(main())
