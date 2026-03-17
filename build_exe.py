import importlib.util
import os
import subprocess
import sys


def detect_qt_package():
    if importlib.util.find_spec('PyQt6') is not None:
        return 'PyQt6'
    if importlib.util.find_spec('PyQt5') is not None:
        return 'PyQt5'
    return ''


def main():
    project_dir = os.path.dirname(os.path.realpath(__file__))
    qt_package = detect_qt_package()

    if qt_package == '':
        print('PyQt6 or PyQt5 is required. Install one first:')
        print('  py -3 -m pip install PyQt6')
        print('or')
        print('  py -3 -m pip install PyQt5')
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
        '--collect-all',
        qt_package,
        'justdraw.py',
    ])

    print('Building with {0}...'.format(qt_package))
    print('Command: {0}'.format(' '.join(pyinstaller_cmd)))
    return subprocess.call(pyinstaller_cmd, cwd=project_dir)


if __name__ == '__main__':
    raise SystemExit(main())
