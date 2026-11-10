"""Tests for JSON history persistence."""

import json

import pytest

from core.categorizer import Categorizer
from core.history import (HistoryError, add_operation, find_operation, get_statistics,
                          latest_undoable, load_history)
from core.organizer import organize_directory


def make_result(folder, *names):
    for name in names:
        (folder / name).write_text("x")
    return organize_directory(folder, Categorizer())


def test_missing_history_is_empty(tmp_path):
    assert load_history(tmp_path / "history.json") == []


def test_add_and_reload_multiple_operations(tmp_path):
    history = tmp_path / "data" / "history.json"
    work = tmp_path / "work"
    work.mkdir()
    first = add_operation(make_result(work, "a.jpg", "b.pdf"), history)
    second = add_operation(make_result(work, "c.mp3"), history)
    assert (first["id"], second["id"]) == (1, 2)

    operations = load_history(history)  # simulates restarting the app
    assert [op["id"] for op in operations] == [1, 2]
    assert operations[0]["successful"] == 2 and len(operations[0]["moves"]) == 2
    assert operations[0]["moves"][0]["source"] and operations[0]["moves"][0]["destination"]
    assert find_operation(operations, 2)["successful"] == 1


def test_corrupted_history_is_set_aside(tmp_path):
    history = tmp_path / "history.json"
    history.write_text("{ broken", encoding="utf-8")
    assert load_history(history) == []
    assert (tmp_path / "history.json.corrupt").exists()
    assert not history.exists()


def test_invalid_structure_is_treated_as_corrupted(tmp_path):
    history = tmp_path / "history.json"
    history.write_text(json.dumps({"operations": [{"nope": 1}]}), encoding="utf-8")
    assert load_history(history) == []


def test_no_temp_file_left_behind(tmp_path):
    history = tmp_path / "history.json"
    work = tmp_path / "work"
    work.mkdir()
    add_operation(make_result(work, "a.jpg"), history)
    assert sorted(p.name for p in tmp_path.iterdir() if p.is_file()) == ["history.json"]


def test_unknown_operation_and_nothing_to_undo():
    with pytest.raises(HistoryError):
        find_operation([], 5)
    with pytest.raises(HistoryError):
        latest_undoable([])


def test_statistics(tmp_path):
    history = tmp_path / "history.json"
    work = tmp_path / "work"
    work.mkdir()
    add_operation(make_result(work, "a.jpg", "b.jpg", "c.pdf"), history)
    stats = get_statistics(load_history(history))
    assert stats["operations"] == 1 and stats["files_moved"] == 3
    assert stats["by_category"] == {"Images": 2, "Documents": 1}
