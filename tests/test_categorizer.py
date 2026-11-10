"""Tests for extension -> category mapping and config loading."""

import json
from pathlib import Path

import pytest

from core.categorizer import Categorizer, CategoryConfigError, load_category_config


def test_known_extensions():
    c = Categorizer()
    assert c.categorize(Path("photo.jpg")) == "Images"
    assert c.categorize(Path("report.pdf")) == "Documents"
    assert c.categorize(Path("song.mp3")) == "Audio"
    assert c.categorize(Path("setup.exe")) == "Executables"


def test_case_insensitive_and_unknown():
    c = Categorizer()
    assert c.categorize(Path("PHOTO.JPG")) == "Images"
    assert c.categorize(Path("file.xyz")) == "Others"
    assert c.categorize(Path("Makefile")) == "Others"


def test_custom_config_file(tmp_path):
    config_file = tmp_path / "categories.json"
    config_file.write_text(json.dumps({"categories": {"Notes": ["txt", ".LOG"]}}), encoding="utf-8")
    c = Categorizer(load_category_config(config_file))
    assert c.categorize(Path("a.txt")) == "Notes"
    assert c.categorize(Path("b.log")) == "Notes"
    assert c.categorize(Path("c.jpg")) == "Others"


def test_missing_config_uses_defaults(tmp_path):
    c = Categorizer(load_category_config(tmp_path / "nope.json"))
    assert c.categorize(Path("a.png")) == "Images"


def test_corrupted_json_raises(tmp_path):
    config_file = tmp_path / "categories.json"
    config_file.write_text("{ not json", encoding="utf-8")
    with pytest.raises(CategoryConfigError):
        load_category_config(config_file)


def test_invalid_folder_name_rejected(tmp_path):
    config_file = tmp_path / "categories.json"
    config_file.write_text(json.dumps({"categories": {"Bad/Name": [".x"]}}), encoding="utf-8")
    with pytest.raises(CategoryConfigError):
        load_category_config(config_file)
