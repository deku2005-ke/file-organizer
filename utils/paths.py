"""Central place for every filesystem location the application uses."""

from __future__ import annotations

import os
from pathlib import Path

PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent
CONFIG_DIR: Path = PROJECT_ROOT / "config"
DATA_DIR: Path = PROJECT_ROOT / "data"
LOGS_DIR: Path = PROJECT_ROOT / "logs"

CATEGORIES_FILE: Path = CONFIG_DIR / "categories.json"
HISTORY_FILE: Path = DATA_DIR / "history.json"
LOG_FILE: Path = LOGS_DIR / "file_organizer.log"

_SYSTEM_ENV_VARS = ("SystemRoot", "ProgramFiles", "ProgramFiles(x86)", "ProgramData")


def ensure_app_dirs() -> None:
    """Create the config, data and logs folders if they do not exist."""
    for folder in (CONFIG_DIR, DATA_DIR, LOGS_DIR):
        folder.mkdir(parents=True, exist_ok=True)


def is_relative_to(path: Path, parent: Path) -> bool:
    """Return True if ``path`` is ``parent`` or lives somewhere inside it."""
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def get_protected_reason(directory: Path) -> str | None:
    """Explain why a directory must never be organized, or return None if it is safe."""
    resolved = directory.resolve()

    if resolved == Path(resolved.anchor):
        return "it is a drive root"
    if resolved == Path.home().resolve():
        return "it is your entire user home folder"
    if is_relative_to(resolved, PROJECT_ROOT):
        return "it is part of this application's own folder"

    for variable in _SYSTEM_ENV_VARS:
        value = os.environ.get(variable)
        if value and is_relative_to(resolved, Path(value).resolve()):
            return "it is a Windows system folder"
    return None
