"""Small, safe filesystem helpers shared by the core modules."""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path
from typing import Any, Optional, Set


def unique_destination(destination: Path, reserved: Optional[Set[Path]] = None) -> Path:
    """Return a path that does not exist yet, adding _1, _2, ... before the extension.

    ``reserved`` holds paths already promised to other planned moves, so two
    files in the same batch never get the same name.
    """
    reserved = reserved if reserved is not None else set()
    candidate = destination
    counter = 1
    while candidate.exists() or candidate in reserved:
        candidate = destination.with_name(f"{destination.stem}_{counter}{destination.suffix}")
        counter += 1
    return candidate


def safe_move(source: Path, destination: Path) -> Path:
    """Move a file without ever overwriting anything. Returns the final path.

    Raises FileNotFoundError if the source is gone and FileExistsError if the
    destination already exists. Other OSErrors (permissions etc.) pass through.
    """
    if not source.exists():
        raise FileNotFoundError(f"Source file no longer exists: {source}")
    if destination.exists():
        raise FileExistsError(f"Destination already exists: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(source), str(destination))
    return destination


def write_json_atomic(path: Path, data: Any) -> None:
    """Write JSON to a temporary file first, then replace the real file.

    If anything fails, the previous file is left untouched.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(path.name + ".tmp")
    try:
        with open(temp_path, "w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=2, ensure_ascii=False)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, path)
    except Exception:
        temp_path.unlink(missing_ok=True)
        raise
