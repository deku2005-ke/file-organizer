# File Organizer

A small Python app that sorts the files in a folder into category folders (Images, Documents, Audio, ...) by extension.
It has a command line and a Tkinter window, previews before moving, and can undo any previous run.
No database and no third-party runtime dependencies: settings and history are plain JSON files.

## Features
- Dry-run preview, and a confirmation before anything is moved
- Never overwrites (`photo.jpg` -> `photo_1.jpg`) and never deletes files
- Optional recursive scan; symlinks, hidden folders and already-organized category folders are skipped
- Refuses to organize a drive root, your whole home folder, Windows system folders, or this app's own folder
- Undo the latest run or any earlier run; history survives restarts (`data/history.json`, written safely via a temp file)
- Categories editable in `config/categories.json` (or in the GUI's Categories tab)
- Log file in `logs/file_organizer.log`

## Requirements
Python 3.9+ (Tkinter is included with the standard Windows installer). Only `pytest` is needed, for the tests:

    python -m pip install pytest

## Usage (Windows PowerShell)

    python main.py "C:/Users/YourName/Downloads" --dry-run     # preview only
    python main.py "C:/Users/YourName/Downloads"               # organize (asks to confirm)
    python main.py "C:/Users/YourName/Downloads" -r            # include sub-folders
    python main.py --history                                   # list operations
    python main.py --show 1                                    # files moved in operation 1
    python main.py --stats                                     # totals
    python main.py --undo                                      # undo the latest operation
    python main.py --undo-operation 1                          # undo a specific one
    python main.py --gui                                       # open the window
