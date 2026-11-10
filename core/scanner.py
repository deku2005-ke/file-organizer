"""Finds files to organize. Never follows symlinks by default and skips internal folders."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, List

from utils.logger import get_logger
from utils.paths import PROJECT_ROOT, get_protected_reason, is_relative_to

log = get_logger("scanner")

IGNORED_FILENAMES = {"desktop.ini",".crdownload", "thumbs.db", ".ds_store"}


class InvalidDirectoryError(Exception):
    """Raised when the chosen directory is missing, unreadable, or not safe to organize."""


@dataclass
class ScanResult:
    """Files found plus any problems met along the way."""

    root: Path
    files: List[Path] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)

    @property
    def file_count(self) -> int:
        return len(self.files)


def validate_directory(path: Path) -> Path:
    """Return the resolved directory or raise InvalidDirectoryError with a clear reason."""
    try:
        resolved = Path(path).expanduser().resolve()
    except (OSError, RuntimeError) as exc:
        raise InvalidDirectoryError(f"Invalid path '{path}': {exc}") from exc

    if not resolved.exists():
        raise InvalidDirectoryError(f"The folder does not exist: {resolved}")
    if not resolved.is_dir():
        raise InvalidDirectoryError(f"That path is a file, not a folder: {resolved}")
    if not os.access(resolved, os.R_OK):
        raise InvalidDirectoryError(f"Permission denied: cannot read {resolved}")

    reason = get_protected_reason(resolved)
    if reason:
        raise InvalidDirectoryError(f"Refusing to organize {resolved} because {reason}.")
    return resolved


def _may_enter(folder: Path, name: str, skip_names: set, follow_symlinks: bool) -> bool:
    """Decide whether to descend into a sub-folder."""
    if name.lower() in skip_names or name.startswith("."):
        return False  # category folders and hidden folders such as .git
    if folder.is_symlink() and not follow_symlinks:
        return False
    return not is_relative_to(folder, PROJECT_ROOT)


def scan_directory(
    root: Path,
    recursive: bool = False,
    skip_folder_names: Iterable[str] = (),
    follow_symlinks: bool = False,
) -> ScanResult:
    """List the files under ``root``.

    ``skip_folder_names`` should be the category folder names, so files that are
    already organized are not picked up again.
    """
    resolved = validate_directory(root)
    result = ScanResult(root=resolved)
    skip_names = {name.lower() for name in skip_folder_names}

    def on_error(error: OSError) -> None:
        message = f"Cannot access '{error.filename}': {error.strerror or error}"
        log.warning(message)
        result.errors.append(message)

    for current, dirs, files in os.walk(resolved, topdown=True, onerror=on_error, followlinks=follow_symlinks):
        current_path = Path(current)
        if recursive:
            dirs[:] = sorted(d for d in dirs if _may_enter(current_path / d, d, skip_names, follow_symlinks))
        else:
            dirs[:] = []

        for name in sorted(files):
            file_path = current_path / name
            if name.lower() in IGNORED_FILENAMES:
                continue
            if file_path.is_symlink() and not follow_symlinks:
                continue
            if is_relative_to(file_path, PROJECT_ROOT):
                continue
            result.files.append(file_path)

    log.info("Scanned %s: %d files (recursive=%s)", resolved, result.file_count, recursive)
    return result
