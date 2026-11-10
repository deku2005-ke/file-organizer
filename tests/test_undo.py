"""Tests for undoing operations."""

import pytest

from core.categorizer import Categorizer
from core.history import HistoryError, add_operation, load_history
from core.organizer import organize_directory
from core.undo import undo_last, undo_operation


def organize_and_record(folder, history, *names):
    for name in names:
        (folder / name).write_text(name)
    operation = add_operation(organize_directory(folder, Categorizer()), history)
    return operation["id"]


def test_undo_last_restores_files(tmp_path):
    history = tmp_path / "history.json"
    work = tmp_path / "work"
    work.mkdir()
    organize_and_record(work, history, "a.jpg", "b.pdf")
    result = undo_last(history)
    assert len(result.restored) == 2 and result.failed == []
    assert (work / "a.jpg").read_text() == "a.jpg" and (work / "b.pdf").exists()
    assert not (work / "Images" / "a.jpg").exists()
    assert load_history(history)[0]["undone"] is True  # history is preserved, just marked


def test_undo_specific_older_operation(tmp_path):
    history = tmp_path / "history.json"
    work = tmp_path / "work"
    work.mkdir()
    first = organize_and_record(work, history, "a.jpg")
    organize_and_record(work, history, "b.mp3")
    undo_operation(first, history)
    assert (work / "a.jpg").exists()
    assert (work / "Audio" / "b.mp3").exists()  # the newer operation is untouched
    assert undo_last(history).operation_id == 2  # newest not-yet-undone one


def test_undo_twice_is_refused(tmp_path):
    history = tmp_path / "history.json"
    work = tmp_path / "work"
    work.mkdir()
    op_id = organize_and_record(work, history, "a.jpg")
    undo_operation(op_id, history)
    with pytest.raises(HistoryError):
        undo_operation(op_id, history)


def test_manually_moved_file_is_reported(tmp_path):
    history = tmp_path / "history.json"
    work = tmp_path / "work"
    work.mkdir()
    op_id = organize_and_record(work, history, "a.jpg", "b.jpg")
    (work / "Images" / "a.jpg").unlink()
    result = undo_operation(op_id, history)
    assert len(result.restored) == 1 and len(result.failed) == 1
    assert "not found" in result.failed[0]


def test_undo_never_overwrites(tmp_path):
    history = tmp_path / "history.json"
    work = tmp_path / "work"
    work.mkdir()
    op_id = organize_and_record(work, history, "a.jpg")
    (work / "a.jpg").write_text("SOMETHING NEW")  # a new file took the old name
    result = undo_operation(op_id, history)
    assert (work / "a.jpg").read_text() == "SOMETHING NEW"
    assert (work / "a_1.jpg").read_text() == "a.jpg"
    assert "restored as a_1.jpg" in result.restored[0]


def test_unknown_operation_id(tmp_path):
    with pytest.raises(HistoryError):
        undo_operation(99, tmp_path / "history.json")
