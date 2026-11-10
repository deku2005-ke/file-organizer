"""Tests for planning, moving, duplicate names and dry runs."""

from pathlib import Path

import core.organizer as organizer_module
from core.categorizer import Categorizer
from core.organizer import create_plan, organize_directory


def make_files(folder: Path, *names: str) -> None:
    for name in names:
        (folder / name).write_text(name)


def test_organize_moves_files(tmp_path):
    make_files(tmp_path, "photo.jpg", "report.pdf", "song.mp3", "weird.xyz")
    result = organize_directory(tmp_path, Categorizer())
    assert result.moved_count == 4 and result.failed_count == 0
    assert (tmp_path / "Images" / "photo.jpg").read_text() == "photo.jpg"
    assert (tmp_path / "Documents" / "report.pdf").exists()
    assert (tmp_path / "Audio" / "song.mp3").exists()
    assert (tmp_path / "Others" / "weird.xyz").exists()
    assert not (tmp_path / "photo.jpg").exists()


def test_dry_run_moves_nothing(tmp_path):
    make_files(tmp_path, "photo.jpg")
    result = organize_directory(tmp_path, Categorizer(), dry_run=True)
    assert result.dry_run and len(result.plan) == 1 and result.moved_count == 0
    assert (tmp_path / "photo.jpg").exists()
    assert not (tmp_path / "Images").exists()


def test_never_overwrites_existing_file(tmp_path):
    (tmp_path / "Images").mkdir()
    (tmp_path / "Images" / "photo.jpg").write_text("OLD")
    (tmp_path / "photo.jpg").write_text("NEW")
    organize_directory(tmp_path, Categorizer())
    assert (tmp_path / "Images" / "photo.jpg").read_text() == "OLD"
    assert (tmp_path / "Images" / "photo_1.jpg").read_text() == "NEW"


def test_duplicate_names_in_one_batch(tmp_path):
    (tmp_path / "sub1").mkdir()
    (tmp_path / "sub2").mkdir()
    (tmp_path / "sub1" / "photo.jpg").write_text("1")
    (tmp_path / "sub2" / "photo.jpg").write_text("2")
    (tmp_path / "photo.jpg").write_text("0")
    organize_directory(tmp_path, Categorizer(), recursive=True)
    assert sorted(p.name for p in (tmp_path / "Images").iterdir()) == ["photo.jpg", "photo_1.jpg", "photo_2.jpg"]


def test_already_organized_files_not_picked_up_again(tmp_path):
    make_files(tmp_path, "photo.jpg")
    organize_directory(tmp_path, Categorizer(), recursive=True)
    second = create_plan(tmp_path, Categorizer(), recursive=True)
    assert second.moves == []


def test_failed_move_is_reported_and_run_continues(tmp_path, monkeypatch):
    make_files(tmp_path, "a.jpg", "b.pdf")
    real_move = organizer_module.safe_move

    def flaky(source, destination):
        if source.name == "a.jpg":
            raise PermissionError("locked")
        return real_move(source, destination)

    monkeypatch.setattr(organizer_module, "safe_move", flaky)
    result = organize_directory(tmp_path, Categorizer())
    assert result.failed_count == 1 and result.moved_count == 1
    assert "Permission denied" in result.failed[0].error
    assert (tmp_path / "a.jpg").exists()
    assert (tmp_path / "Documents" / "b.pdf").exists()


def test_file_vanishing_before_move_is_a_failure(tmp_path):
    make_files(tmp_path, "a.jpg")
    plan = create_plan(tmp_path, Categorizer())
    (tmp_path / "a.jpg").unlink()
    result = organizer_module.execute_plan(plan)
    assert result.failed_count == 1 and result.moved_count == 0


def test_progress_callback(tmp_path):
    make_files(tmp_path, "a.jpg", "b.pdf")
    calls = []
    organize_directory(tmp_path, Categorizer(), progress=lambda i, n, rec: calls.append((i, n)))
    assert calls == [(1, 2), (2, 2)]
