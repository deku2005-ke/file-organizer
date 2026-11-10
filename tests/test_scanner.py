"""Tests for scanning. All work happens inside pytest's temporary folders."""

from pathlib import Path

import pytest

from core.scanner import InvalidDirectoryError, scan_directory
from utils.paths import PROJECT_ROOT


def names(result):
    return sorted(p.name for p in result.files)


def test_non_recursive_scan(tmp_path):
    (tmp_path / "a.txt").write_text("a")
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "b.txt").write_text("b")
    assert names(scan_directory(tmp_path)) == ["a.txt"]


def test_recursive_scan(tmp_path):
    (tmp_path / "a.txt").write_text("a")
    (tmp_path / "sub" / "deep").mkdir(parents=True)
    (tmp_path / "sub" / "deep" / "b.txt").write_text("b")
    assert names(scan_directory(tmp_path, recursive=True)) == ["a.txt", "b.txt"]


def test_skips_category_and_hidden_folders(tmp_path):
    (tmp_path / "Images").mkdir()
    (tmp_path / "Images" / "done.jpg").write_text("x")
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "config").write_text("x")
    (tmp_path / "new.jpg").write_text("x")
    result = scan_directory(tmp_path, recursive=True, skip_folder_names={"Images"})
    assert names(result) == ["new.jpg"]


def test_empty_directory(tmp_path):
    assert scan_directory(tmp_path).file_count == 0


def test_ignores_system_files(tmp_path):
    (tmp_path / "desktop.ini").write_text("x")
    (tmp_path / "keep.txt").write_text("x")
    assert names(scan_directory(tmp_path)) == ["keep.txt"]


def test_missing_directory(tmp_path):
    with pytest.raises(InvalidDirectoryError):
        scan_directory(tmp_path / "does_not_exist")


def test_path_is_a_file(tmp_path):
    file_path = tmp_path / "f.txt"
    file_path.write_text("x")
    with pytest.raises(InvalidDirectoryError):
        scan_directory(file_path)


def test_protected_directories_refused():
    with pytest.raises(InvalidDirectoryError):
        scan_directory(Path.home())
    with pytest.raises(InvalidDirectoryError):
        scan_directory(PROJECT_ROOT)
    with pytest.raises(InvalidDirectoryError):
        scan_directory(Path(Path.home().anchor))


def test_symlinks_not_followed(tmp_path):
    real = tmp_path / "real"
    real.mkdir()
    (real / "inside.txt").write_text("x")
    link = tmp_path / "link"
    try:
        link.symlink_to(real, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("Symlinks not available on this system")
    assert names(scan_directory(tmp_path, recursive=True)) == ["inside.txt"]  # found once, via 'real'
