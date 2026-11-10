"""Tkinter interface. It only calls the core modules; it contains no file logic.

Long work runs in a background thread and talks to the window through a Queue,
because Tkinter widgets must only be touched from the main thread.
"""

from __future__ import annotations

import json
import queue
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Any, Callable, Optional

from core.categorizer import Categorizer, CategoryConfigError, load_category_config, parse_category_config
from core.history import HistoryError, add_operation, get_statistics, load_history
from core.organizer import OrganizationPlan, create_plan, execute_plan
from core.scanner import InvalidDirectoryError
from core.undo import undo_operation
from utils.file_utils import write_json_atomic
from utils.logger import get_logger
from utils.paths import CATEGORIES_FILE

log = get_logger("gui")
EXPECTED_ERRORS = (InvalidDirectoryError, CategoryConfigError, HistoryError)


class App(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("File Organizer")
        self.geometry("920x620")
        self.minsize(760, 480)
        self.messages: "queue.Queue[tuple]" = queue.Queue()
        self.plan: Optional[OrganizationPlan] = None
        self.busy = False
        self.action_buttons: list = []

        self.folder_var = tk.StringVar()
        self.recursive_var = tk.BooleanVar(value=False)
        self.status_var = tk.StringVar(value="Choose a folder to begin.")

        notebook = ttk.Notebook(self)
        notebook.pack(fill="both", expand=True, padx=10, pady=(10, 0))
        self._build_organize_tab(notebook)
        self._build_history_tab(notebook)
        self._build_settings_tab(notebook)

        bottom = ttk.Frame(self, padding=10)
        bottom.pack(fill="x")
        self.progress = ttk.Progressbar(bottom, mode="determinate")
        self.progress.pack(fill="x")
        ttk.Label(bottom, textvariable=self.status_var).pack(anchor="w", pady=(6, 0))

        self.refresh_history()
        self.load_settings_text()
        self.after(100, self._poll)

    # ---------- layout ----------
    def _scrolled_tree(self, parent: tk.Widget, columns: tuple, widths: tuple) -> ttk.Treeview:
        frame = ttk.Frame(parent)
        frame.pack(fill="both", expand=True, pady=10)
        tree = ttk.Treeview(frame, columns=columns, show="headings", selectmode="browse")
        for name, width in zip(columns, widths):
            tree.heading(name, text=name.title())
            tree.column(name, width=width, anchor="w")
        scroll = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scroll.set)
        tree.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        return tree

    def _build_organize_tab(self, notebook: ttk.Notebook) -> None:
        tab = ttk.Frame(notebook, padding=12)
        notebook.add(tab, text="Organize")
        row = ttk.Frame(tab)
        row.pack(fill="x")
        ttk.Entry(row, textvariable=self.folder_var).pack(side="left", fill="x", expand=True)
        browse = ttk.Button(row, text="Browse...", command=self.browse)
        browse.pack(side="left", padx=(8, 0))
        options = ttk.Frame(tab)
        options.pack(fill="x", pady=(8, 0))
        ttk.Checkbutton(options, text="Include sub-folders", variable=self.recursive_var).pack(side="left")
        self.organize_button = ttk.Button(options, text="Organize", command=self.organize, state="disabled")
        self.organize_button.pack(side="right")
        scan = ttk.Button(options, text="Scan / Preview", command=self.scan)
        scan.pack(side="right", padx=8)
        self.action_buttons += [browse, scan]
        self.files_tree = self._scrolled_tree(tab, ("file", "category", "destination", "status"), (260, 100, 340, 160))

    def _build_history_tab(self, notebook: ttk.Notebook) -> None:
        tab = ttk.Frame(notebook, padding=12)
        notebook.add(tab, text="History")
        buttons = ttk.Frame(tab)
        buttons.pack(fill="x")
        for text, command in (("Refresh", self.refresh_history), ("View files", self.view_operation),
                              ("Undo selected", self.undo_selected)):
            button = ttk.Button(buttons, text=text, command=command)
            button.pack(side="left", padx=(0, 8))
            self.action_buttons.append(button)
        self.stats_var = tk.StringVar()
        ttk.Label(buttons, textvariable=self.stats_var).pack(side="right")
        self.history_tree = self._scrolled_tree(
            tab, ("id", "date", "moved", "failed", "status", "folder"), (40, 140, 60, 60, 70, 380))

    def _build_settings_tab(self, notebook: ttk.Notebook) -> None:
        tab = ttk.Frame(notebook, padding=12)
        notebook.add(tab, text="Categories")
        ttk.Label(tab, text="Edit which extensions belong to each category (JSON).").pack(anchor="w")
        buttons = ttk.Frame(tab)
        buttons.pack(fill="x", pady=8)
        ttk.Button(buttons, text="Save", command=self.save_settings).pack(side="left", padx=(0, 8))
        ttk.Button(buttons, text="Reload", command=self.load_settings_text).pack(side="left")
        self.settings_text = tk.Text(tab, wrap="none", font=("Consolas", 10), undo=True)
        self.settings_text.pack(fill="both", expand=True)

    # ---------- background work ----------
    def run_in_background(self, work: Callable[[], Any], done: Callable[[Any], None],
                          indeterminate: bool = False) -> None:
        if self.busy:
            return
        self.set_busy(True, indeterminate)

        def target() -> None:
            try:
                self.messages.put(("done", done, work()))
            except Exception as exc:  # reported on the main thread
                self.messages.put(("error", None, exc))

        threading.Thread(target=target, daemon=True).start()

    def set_busy(self, busy: bool, indeterminate: bool = False) -> None:
        self.busy = busy
        state = "disabled" if busy else "normal"
        for button in self.action_buttons:
            button.configure(state=state)
        self.organize_button.configure(state="disabled" if busy or not (self.plan and self.plan.moves) else "normal")
        self.progress.configure(mode="indeterminate" if indeterminate else "determinate", value=0)
        if busy and indeterminate:
            self.progress.start(12)
        else:
            self.progress.stop()

    def _poll(self) -> None:
        try:
            while True:
                kind, callback, payload = self.messages.get_nowait()
                if kind == "progress":
                    done_count, total = payload
                    self.progress.configure(maximum=max(total, 1), value=done_count)
                    self.status_var.set(f"Moving files... {done_count}/{total}")
                elif kind == "done":
                    self.set_busy(False)
                    callback(payload)
                else:
                    self.set_busy(False)
                    self.show_error(payload)
        except queue.Empty:
            pass
        self.after(100, self._poll)

    def show_error(self, exc: Exception) -> None:
        if isinstance(exc, EXPECTED_ERRORS):
            log.warning("GUI error: %s", exc)
        else:
            log.exception("Unexpected error", exc_info=exc)
        self.status_var.set("Something went wrong.")
        messagebox.showerror("Error", str(exc))

    # ---------- organize tab ----------
    def browse(self) -> None:
        chosen = filedialog.askdirectory(title="Choose a folder to organize")
        if chosen:
            self.folder_var.set(chosen)
            self.plan = None
            self.organize_button.configure(state="disabled")

    def fill_files(self, rows: list) -> None:
        self.files_tree.delete(*self.files_tree.get_children())
        for row in rows:
            self.files_tree.insert("", "end", values=row)

    def scan(self) -> None:
        folder = self.folder_var.get().strip()
        if not folder:
            messagebox.showinfo("Choose a folder", "Please choose a folder first.")
            return
        recursive = self.recursive_var.get()
        self.status_var.set("Scanning...")
        self.run_in_background(
            lambda: create_plan(Path(folder), Categorizer(load_category_config()), recursive),
            self.on_scanned, indeterminate=True)

    def on_scanned(self, plan: OrganizationPlan) -> None:
        self.plan = plan
        self.fill_files([(str(m.source.relative_to(plan.source_dir)), m.category,
                          str(m.destination.relative_to(plan.source_dir)), "planned") for m in plan.moves])
        note = f" ({len(plan.scan_errors)} folder(s) could not be read)" if plan.scan_errors else ""
        self.status_var.set(f"{len(plan.moves)} file(s) would be moved.{note}")
        self.organize_button.configure(state="normal" if plan.moves else "disabled")

    def organize(self) -> None:
        plan = self.plan
        if not plan or not plan.moves:
            return
        if not messagebox.askyesno("Confirm", f"Move {len(plan.moves)} file(s) inside\n{plan.source_dir}\n\n"
                                              "You can undo this from the History tab."):
            return
        self.run_in_background(
            lambda: execute_plan(plan, lambda i, n, rec: self.messages.put(("progress", None, (i, n)))),
            self.on_organized)

    def on_organized(self, result: Any) -> None:
        rows = [(m.source.name, m.category, str(m.destination), "moved") for m in result.moved]
        rows += [(m.source.name, m.category, "", "FAILED: " + m.error) for m in result.failed]
        self.fill_files(rows)
        self.plan = None
        self.organize_button.configure(state="disabled")
        try:
            if result.moved:
                add_operation(result)
        except HistoryError as exc:
            self.show_error(exc)
        self.status_var.set(f"Done: {result.moved_count} moved, {result.failed_count} failed.")
        self.refresh_history()

    # ---------- history tab ----------
    def refresh_history(self) -> None:
        try:
            operations = load_history()
        except HistoryError as exc:
            self.show_error(exc)
            return
        self.history_tree.delete(*self.history_tree.get_children())
        for op in reversed(operations):
            status = "undone" if op.get("undone") else "active"
            self.history_tree.insert("", "end", values=(op["id"], op["timestamp"], op["successful"],
                                                        op["failed"], status, op["source_dir"]))
        stats = get_statistics(operations)
        self.stats_var.set(f"{stats['operations']} operations, {stats['files_moved']} files moved")

    def selected_operation_id(self) -> Optional[int]:
        selection = self.history_tree.selection()
        if not selection:
            messagebox.showinfo("Select an operation", "Please select an operation in the list.")
            return None
        return int(self.history_tree.item(selection[0])["values"][0])

    def view_operation(self) -> None:
        operation_id = self.selected_operation_id()
        if operation_id is None:
            return
        operation = next((op for op in load_history() if op["id"] == operation_id), None)
        if operation is None:
            return
        window = tk.Toplevel(self)
        window.title(f"Operation {operation_id}")
        window.geometry("760x420")
        text = tk.Text(window, wrap="none")
        text.pack(fill="both", expand=True)
        for move in operation["moves"]:
            text.insert("end", f"{move['source']}\n    -> {move['destination']}\n")
        text.configure(state="disabled")

    def undo_selected(self) -> None:
        operation_id = self.selected_operation_id()
        if operation_id is None:
            return
        if not messagebox.askyesno("Confirm undo", f"Move the files of operation {operation_id} back?"):
            return
        self.status_var.set("Undoing...")
        self.run_in_background(lambda: undo_operation(operation_id), self.on_undone, indeterminate=True)

    def on_undone(self, result: Any) -> None:
        self.refresh_history()
        self.status_var.set(f"Undo finished: {len(result.restored)} restored, {len(result.failed)} failed.")
        if result.failed:
            messagebox.showwarning("Some files could not be restored", "\n".join(result.failed[:15]))

    # ---------- categories tab ----------
    def load_settings_text(self) -> None:
        try:
            content = CATEGORIES_FILE.read_text(encoding="utf-8") if CATEGORIES_FILE.exists() else ""
        except OSError as exc:
            self.show_error(exc)
            return
        self.settings_text.delete("1.0", "end")
        self.settings_text.insert("1.0", content)

    def save_settings(self) -> None:
        try:
            data = json.loads(self.settings_text.get("1.0", "end"))
            parse_category_config(data)  # validates names and extensions
            write_json_atomic(CATEGORIES_FILE, data)
        except ValueError as exc:
            messagebox.showerror("Invalid JSON", str(exc))
            return
        except (CategoryConfigError, OSError) as exc:
            messagebox.showerror("Cannot save", str(exc))
            return
        self.status_var.set("Categories saved.")


def run_gui() -> None:
    App().mainloop()
