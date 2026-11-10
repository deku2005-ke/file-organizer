"""Maps file extensions to category names using a JSON configuration."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Set

from utils.paths import CATEGORIES_FILE

DEFAULT_CATEGORY = "Others"

DEFAULT_CATEGORIES: Dict[str, List[str]] = {
    "Images": [".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".svg", ".tiff", ".ico", ".heic"],
    "Documents": [".pdf", ".doc", ".docx", ".txt", ".rtf", ".odt", ".md"],
    "Spreadsheets": [".xls", ".xlsx", ".csv", ".ods"],
    "Presentations": [".ppt", ".pptx", ".odp"],
    "Audio": [".mp3", ".wav", ".flac", ".aac", ".ogg", ".m4a", ".wma"],
    "Videos": [".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv", ".webm"],
    "Archives": [".zip", ".rar", ".7z", ".tar", ".gz", ".bz2"],
    "Code": [".py", ".js", ".ts", ".java", ".c", ".cpp", ".h", ".cs", ".html", ".css",
             ".json", ".xml", ".sh", ".bat", ".go", ".rs", ".php"],
    "Executables": [".exe", ".msi", ".apk", ".dmg"],
}

_INVALID_FOLDER_CHARS = set('<>:"/\\|?*')


class CategoryConfigError(Exception):
    """Raised when the categories configuration is unreadable or invalid."""


@dataclass(frozen=True)
class CategoryConfig:
    """Validated category settings."""

    categories: Dict[str, List[str]]
    default_category: str = DEFAULT_CATEGORY


def _validate_folder_name(name: object) -> str:
    """Category names become folder names, so they must be valid Windows folder names."""
    if not isinstance(name, str) or not name.strip():
        raise CategoryConfigError("Category names must be non-empty text.")
    if name != name.strip() or name.endswith("."):
        raise CategoryConfigError(f"Category name '{name}' cannot start/end with spaces or end with a dot.")
    if any(ch in _INVALID_FOLDER_CHARS for ch in name):
        raise CategoryConfigError(f"Category name '{name}' contains characters not allowed in folder names.")
    return name


def _normalise_extension(extension: object) -> str:
    """Lower-case an extension and make sure it starts with a dot."""
    if not isinstance(extension, str) or extension.strip() in ("", "."):
        raise CategoryConfigError(f"Invalid extension: {extension!r}")
    cleaned = extension.strip().lower()
    return cleaned if cleaned.startswith(".") else "." + cleaned


def parse_category_config(data: object) -> CategoryConfig:
    """Validate raw JSON data and turn it into a CategoryConfig."""
    if not isinstance(data, dict):
        raise CategoryConfigError("The top level of the configuration must be a JSON object.")

    raw_categories = data.get("categories")
    if not isinstance(raw_categories, dict) or not raw_categories:
        raise CategoryConfigError("The configuration needs a non-empty 'categories' object.")

    default = _validate_folder_name(data.get("default_category", DEFAULT_CATEGORY))

    categories: Dict[str, List[str]] = {}
    for name, extensions in raw_categories.items():
        _validate_folder_name(name)
        if not isinstance(extensions, list):
            raise CategoryConfigError(f"Category '{name}' must contain a list of extensions.")
        categories[name] = [_normalise_extension(ext) for ext in extensions]
    return CategoryConfig(categories=categories, default_category=default)


def load_category_config(config_path: Path = CATEGORIES_FILE) -> CategoryConfig:
    """Load categories from JSON. A missing file falls back to built-in defaults;
    a corrupted or invalid file raises CategoryConfigError (never ignored silently)."""
    if not config_path.exists():
        return CategoryConfig(categories={k: list(v) for k, v in DEFAULT_CATEGORIES.items()})
    try:
        data = json.loads(config_path.read_text(encoding="utf-8"))
    except ValueError as exc:  # covers JSONDecodeError and UnicodeDecodeError
        raise CategoryConfigError(f"'{config_path}' is not valid JSON: {exc}") from exc
    except OSError as exc:
        raise CategoryConfigError(f"Cannot read '{config_path}': {exc}") from exc
    return parse_category_config(data)


class Categorizer:
    """Decides which category a file belongs to."""

    def __init__(self, config: Optional[CategoryConfig] = None) -> None:
        self._config = config or CategoryConfig(
            categories={k: list(v) for k, v in DEFAULT_CATEGORIES.items()}
        )
        self._extension_map: Dict[str, str] = {}
        for name, extensions in self._config.categories.items():
            for extension in extensions:
                self._extension_map.setdefault(extension, name)  # first listing wins

    @property
    def default_category(self) -> str:
        return self._config.default_category

    @property
    def category_names(self) -> Set[str]:
        """All category folder names, including the default one."""
        return set(self._config.categories) | {self._config.default_category}

    def categorize(self, file_path: Path) -> str:
        """Return the category name for a file based on its extension."""
        return self._extension_map.get(file_path.suffix.lower(), self._config.default_category)
