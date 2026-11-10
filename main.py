"""File Organizer entry point (command line).

Examples:
    python main.py "C:/Users/Name/Downloads" --dry-run
    python main.py "C:/Users/Name/Downloads"
    python main.py --history
    python main.py --undo
    python main.py --gui
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import List, Optional

from core.categorizer import Categorizer, CategoryConfigError, load_category_config
from core.history import HistoryError, add_operation, find_operation, get_statistics, load_history
from core.organizer import create_plan, execute_plan
from core.scanner import InvalidDirectoryError
from core.undo import UndoResult, undo_last, undo_operation
from utils.logger import setup_logging


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Organize files into category folders by extension.")
    parser.add_argument("directory", nargs="?", help="Folder to organize")
    parser.add_argument("-r", "--recursive", action="store_true", help="Include sub-folders")
    parser.add_argument("--dry-run", action="store_true", help="Preview only; move nothing")
    parser.add_argument("-y", "--yes", action="store_true", help="Do not ask for confirmation")
    parser.add_argument("--history", action="store_true", help="List previous operations")
    parser.add_argument("--show", type=int, metavar="ID", help="Show the files moved in operation ID")
    parser.add_argument("--stats", action="store_true", help="Show history statistics")
    parser.add_argument("--undo", action="store_true", help="Undo the most recent operation")
    parser.add_argument("--undo-operation", type=int, metavar="ID", help="Undo operation ID")
    parser.add_argument("--gui", action="store_true", help="Open the graphical interface")
    return parser


def print_history() -> None:
    operations = load_history()
    if not operations:
        print("No operations recorded yet.")
        return
    print(f"{'ID':>3}  {'Date':19}  {'Moved':>5}  {'Failed':>6}  {'Status':8}  Folder")
    for op in operations:
        status = "undone" if op.get("undone") else "active"
        print(f"{op['id']:>3}  {op['timestamp']:19}  {op['successful']:>5}  {op['failed']:>6}  {status:8}  {op['source_dir']}")


def print_operation(operation_id: int) -> None:
    op = find_operation(load_history(), operation_id)
    print(f"Operation {op['id']} - {op['timestamp']} - {op['source_dir']}")
    for move in op["moves"]:
        print(f"  {move['source']} -> {move['destination']}")
    print(f"{len(op['moves'])} file(s) moved, {op['failed']} failed, undone: {op.get('undone', False)}")


def print_stats() -> None:
    stats = get_statistics(load_history())
    print(f"Operations: {stats['operations']} ({stats['undone']} undone)")
    print(f"Files moved: {stats['files_moved']}   Files failed: {stats['files_failed']}")
    for category, count in sorted(stats["by_category"].items()):
        print(f"  {category}: {count}")


def print_undo(result: UndoResult) -> None:
    print(f"Undo of operation {result.operation_id}: {len(result.restored)} restored, {len(result.failed)} failed")
    for line in result.restored:
        print(f"  restored: {line}")
    for line in result.failed:
        print(f"  COULD NOT RESTORE: {line}")


def run_organize(args: argparse.Namespace) -> int:
    categorizer = Categorizer(load_category_config())
    plan = create_plan(Path(args.directory), categorizer, args.recursive)

    print(f"Folder: {plan.source_dir}")
    print(f"Files found: {plan.files_scanned}")
    for error in plan.scan_errors:
        print(f"  WARNING: {error}")
    for move in plan.moves:
        print(f"  {move.source.relative_to(plan.source_dir)} -> {move.category}/{move.destination.name}")

    if args.dry_run:
        print("Dry run: no files were moved.")
        return 0
    if not plan.moves:
        print("Nothing to organize.")
        return 0
    if not args.yes and input(f"Move {len(plan.moves)} file(s)? [y/N] ").strip().lower() != "y":
        print("Cancelled. No files were moved.")
        return 0

    result = execute_plan(plan)
    if result.moved:
        operation = add_operation(result)
        print(f"Moved {result.moved_count} file(s). Operation ID: {operation['id']} (undo with --undo)")
    for record in result.failed:
        print(f"  FAILED: {record.source} - {record.error}")
    print(f"Done: {result.moved_count} moved, {result.failed_count} failed.")
    return 1 if result.failed else 0


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    setup_logging()
    try:
        if args.gui:
            from gui.app import run_gui  # imported lazily so the CLI works without Tkinter
            run_gui()
        elif args.history:
            print_history()
        elif args.show is not None:
            print_operation(args.show)
        elif args.stats:
            print_stats()
        elif args.undo:
            print_undo(undo_last())
        elif args.undo_operation is not None:
            print_undo(undo_operation(args.undo_operation))
        elif args.directory:
            return run_organize(args)
        else:
            parser.print_help()
        return 0
    except (InvalidDirectoryError, CategoryConfigError, HistoryError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("\nInterrupted.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    sys.exit(main())
