# JustDraw!
This tool helps artists to practice gesture drawings using images on their local hard drive.

1. Requirements

- Python 3.x: See https://www.python.org/getit/
- PyQt 6. Use: pip install PyQt6

2. Usage and arguments

```
usage: justdraw.py [-h] [-path path [path ...]] [-zip-path zip_path]
                    [-zip-path-random zip_path_random]
                    [-zip-file zip_file [zip_file ...]] [-timeout TIMEOUT]
                    [-width WIDTH] [-height HEIGHT]

Gesture drawing helper for artists.

options:
  -h, --help            show this help message and exit
  -path path [path ...]
                        Paths to the images directory (current directory by
                        default). You can specify many directories
  -zip-path zip_path    Path to the directory with zip files contains images.
                        The one random zip file selected, then all it images
                        will be shown in random order
  -zip-path-random zip_path_random
                        Path to the directory with zip files contains images.
                        All zip files selected, then all images from all these
                        files will be shown in random order
  -zip-file zip_file [zip_file ...]
                        Zip files with images. You can specify many files.
  -timeout TIMEOUT      Timeout in seconds (60 by default)
  -width WIDTH          Window width in pixels (600 by default)
  -height HEIGHT        Window height in pixels (800 by default)

```

Example: 
```
python justdraw.py -path "C:\Images" "D:\Path to reference images\Gestures" -timeout 120
```
