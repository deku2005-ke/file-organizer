"""Persistent operation history stored in data/history.json."""

from __future__ import annotations

import json
import os
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List

from utils.file_utils import write_json_atomic
from utils.logger import get_logger
from utils.paths import HISTORY_FILE

if TYPE_CHECKING:
    from core.organizer import OrganizeResult

log = get_logger("history")


class HistoryError(Exception):
    """Raised for history problems the user should be told about."""


def now_text() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _is_valid(data: Any) -> bool:
    if not isinstance(data, dict) or not isinstance(data.get("operations"), list):
        return False
    return all(
        isinstance(op, dict) and isinstance(op.get("id"), int) and isinstance(op.get("moves"), list)
        for op in data["operations"]
    )


def load_history(history_path: Path = HISTORY_FILE) -> List[Dict[str, Any]]:
    """Return all operations. A missing file means empty history; a corrupted file is
    renamed to ``*.corrupt`` (kept for inspection) and history starts fresh."""
    if not history_path.exists():
        return []
    try:
        data = json.loads(history_path.read_text(encoding="utf-8"))
        if not _is_valid(data):
            raise ValueError("unexpected structure")
        return data["operations"]
    except ValueError as exc:
        backup = history_path.with_name(history_path.name + ".corrupt")
        log.error("History file %s is corrupted (%s). Moving it to %s", history_path, exc, backup)
        try:
            os.replace(history_path, backup)
        except OSError as move_error:
            raise HistoryError(f"History file is corrupted and could not be set aside: {move_error}") from move_error
        return []
    except OSError as exc:
        raise HistoryError(f"Cannot read the history file: {exc}") from exc


def save_history(operations: List[Dict[str, Any]], history_path: Path = HISTORY_FILE) -> None:
    """Safely write history (temporary file, then replace)."""
    try:
        write_json_atomic(history_path, {"operations": operations})
    except OSError as exc:
        raise HistoryError(f"Cannot save the history file: {exc}") from exc


def add_operation(result: "OrganizeResult", history_path: Path = HISTORY_FILE) -> Dict[str, Any]:
    """Append one finished organize run. Only successful moves are stored as moves."""
    operations = load_history(history_path)
    operation = {
        "id": max((op["id"] for op in operations), default=0) + 1,
        "timestamp": now_text(),
        "source_dir": str(result.source_dir),
        "files_scanned": result.files_scanned,
        "successful": result.moved_count,
        "failed": result.failed_count,
        "undone": False,
        "moves": [
            {"source": str(r.source), "destination": str(r.destination), "category": r.category}
            for r in result.moved
        ],
    }
    operations.append(operation)
    save_history(operations, history_path)
    log.info("Recorded operation %d (%d moves)", operation["id"], result.moved_count)
    return operation


def find_operation(operations: List[Dict[str, Any]], operation_id: int) -> Dict[str, Any]:
    for operation in operations:
        if operation["id"] == operation_id:
            return operation
    raise HistoryError(f"No operation with ID {operation_id} exists.")


def latest_undoable(operations: List[Dict[str, Any]]) -> Dict[str, Any]:
    for operation in reversed(operations):
        if not operation.get("undone", False):
            return operation
    raise HistoryError("There is nothing to undo.")


def get_statistics(operations: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Totals across all operations."""
    categories: Counter = Counter()
    for operation in operations:
        for move in operation["moves"]:
            categories[move.get("category", "?")] += 1
    return {
        "operations": len(operations),
        "undone": sum(1 for op in operations if op.get("undone", False)),
        "files_moved": sum(op.get("successful", 0) for op in operations),
        "files_failed": sum(op.get("failed", 0) for op in operations),
        "by_category": dict(categories),
    }
