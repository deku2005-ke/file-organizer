"""Reverses recorded operations without overwriting anything."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List

from core.history import (HistoryError, find_operation, latest_undoable, load_history,
                          now_text, save_history)
from utils.file_utils import safe_move, unique_destination
from utils.logger import get_logger
from utils.paths import HISTORY_FILE

log = get_logger("undo")


@dataclass
class UndoResult:
    operation_id: int
    restored: List[str] = field(default_factory=list)
    failed: List[str] = field(default_factory=list)


def _undo(operations: List[Dict[str, Any]], operation: Dict[str, Any], history_path: Path) -> UndoResult:
    if operation.get("undone", False):
        raise HistoryError(f"Operation {operation['id']} was already undone.")

    result = UndoResult(operation_id=operation["id"])
    for move in reversed(operation["moves"]):
        original = Path(move["source"])
        current = Path(move["destination"])
        if not current.exists():
            result.failed.append(f"{current} - file not found (moved or deleted manually)")
            continue
        try:
            target = unique_destination(original)  # never overwrite a file now at the old path
            safe_move(current, target)
        except PermissionError:
            result.failed.append(f"{current} - permission denied")
            continue
        except OSError as exc:
            result.failed.append(f"{current} - {exc}")
            continue
        note = "" if target == original else f" (original name was taken; restored as {target.name})"
        result.restored.append(f"{current} -> {target}{note}")

    operation["undone"] = True
    operation["undone_at"] = now_text()
    save_history(operations, history_path)
    log.info("Undid operation %d: %d restored, %d failed",
             operation["id"], len(result.restored), len(result.failed))
    for problem in result.failed:
        log.warning("Undo problem in operation %d: %s", operation["id"], problem)
    return result


def undo_operation(operation_id: int, history_path: Path = HISTORY_FILE) -> UndoResult:
    """Undo a specific operation by ID."""
    operations = load_history(history_path)
    return _undo(operations, find_operation(operations, operation_id), history_path)


def undo_last(history_path: Path = HISTORY_FILE) -> UndoResult:
    """Undo the most recent operation that has not been undone yet."""
    operations = load_history(history_path)
    return _undo(operations, latest_undoable(operations), history_path)
