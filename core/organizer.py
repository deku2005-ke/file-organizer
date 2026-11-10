"""Plans and performs file moves. Never overwrites and never deletes anything."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, List, Optional, Set

from core.categorizer import Categorizer
from core.scanner import scan_directory
from utils.file_utils import safe_move, unique_destination
from utils.logger import get_logger

log = get_logger("organizer")


@dataclass(frozen=True)
class PlannedMove:
    """One move that is intended but not yet done."""

    source: Path
    destination: Path
    category: str


@dataclass
class MoveRecord:
    """The outcome of one attempted move."""

    source: Path
    destination: Path
    category: str
    success: bool
    error: str = ""


@dataclass
class OrganizationPlan:
    """Everything a preview needs to show."""

    source_dir: Path
    recursive: bool
    files_scanned: int
    moves: List[PlannedMove] = field(default_factory=list)
    scan_errors: List[str] = field(default_factory=list)


@dataclass
class OrganizeResult:
    """Final report of an organize run (or a dry run)."""

    source_dir: Path
    recursive: bool
    dry_run: bool
    files_scanned: int
    plan: List[PlannedMove] = field(default_factory=list)
    moved: List[MoveRecord] = field(default_factory=list)
    failed: List[MoveRecord] = field(default_factory=list)
    scan_errors: List[str] = field(default_factory=list)

    @property
    def moved_count(self) -> int:
        return len(self.moved)

    @property
    def failed_count(self) -> int:
        return len(self.failed)


# Called after each file with (files_done, files_total, record).
ProgressCallback = Callable[[int, int, MoveRecord], None]


def create_plan(directory: Path, categorizer: Categorizer, recursive: bool = False) -> OrganizationPlan:
    """Scan a folder and decide where every file would go. Touches nothing."""
    scan = scan_directory(directory, recursive=recursive, skip_folder_names=categorizer.category_names)
    plan = OrganizationPlan(
        source_dir=scan.root,
        recursive=recursive,
        files_scanned=scan.file_count,
        scan_errors=list(scan.errors),
    )
    reserved: Set[Path] = set()
    for file_path in scan.files:
        category = categorizer.categorize(file_path)
        destination = unique_destination(scan.root / category / file_path.name, reserved)
        reserved.add(destination)
        plan.moves.append(PlannedMove(source=file_path, destination=destination, category=category))
    return plan


def execute_plan(plan: OrganizationPlan, progress: Optional[ProgressCallback] = None) -> OrganizeResult:
    """Carry out a plan. A failed move is reported as failed and the run continues."""
    result = OrganizeResult(
        source_dir=plan.source_dir,
        recursive=plan.recursive,
        dry_run=False,
        files_scanned=plan.files_scanned,
        plan=list(plan.moves),
        scan_errors=list(plan.scan_errors),
    )
    total = len(plan.moves)

    for index, move in enumerate(plan.moves, start=1):
        try:
            # Re-check the name now: something may have appeared since the preview.
            final = safe_move(move.source, unique_destination(move.destination))
            record = MoveRecord(move.source, final, move.category, True)
            log.info("Moved %s -> %s", move.source, final)
        except PermissionError:
            record = MoveRecord(move.source, move.destination, move.category, False,
                                "Permission denied (file may be open in another program)")
        except FileNotFoundError:
            record = MoveRecord(move.source, move.destination, move.category, False,
                                "File no longer exists")
        except OSError as exc:
            record = MoveRecord(move.source, move.destination, move.category, False,
                                f"File system error: {exc}")

        if record.success:
            result.moved.append(record)
        else:
            result.failed.append(record)
            log.error("Failed to move %s: %s", move.source, record.error)
        if progress:
            progress(index, total, record)

    log.info("Organized %s: %d moved, %d failed", plan.source_dir, result.moved_count, result.failed_count)
    return result


def organize_directory(
    directory: Path,
    categorizer: Categorizer,
    recursive: bool = False,
    dry_run: bool = False,
    progress: Optional[ProgressCallback] = None,
) -> OrganizeResult:
    """Plan and (unless dry_run) execute in one call."""
    plan = create_plan(directory, categorizer, recursive)
    if dry_run:
        return OrganizeResult(
            source_dir=plan.source_dir,
            recursive=recursive,
            dry_run=True,
            files_scanned=plan.files_scanned,
            plan=list(plan.moves),
            scan_errors=list(plan.scan_errors),
        )
    return execute_plan(plan, progress)
