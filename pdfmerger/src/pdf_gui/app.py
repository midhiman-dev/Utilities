from __future__ import annotations

import os
import sys
import threading
import tkinter as tk
import tkinter.font as tkfont
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk
from typing import Any

from .diagnostics import create_diagnostics_bundle
from .inprocess_dispatch import run_tool, values_to_argv
from .observability import configure_app_logger
from .paths import resolve_app_paths
from .runner import ProcessRunner
from .settings_store import SettingsStore
from .tool_specs import TOOL_BY_ID, TOOLS, FieldSpec


class ToolForm(ttk.Frame):
    def __init__(self, parent: ttk.Notebook, tool_id: str, values: dict[str, Any]) -> None:
        super().__init__(parent)
        self.tool_id = tool_id
        self.spec = TOOL_BY_ID[tool_id]
        self.variables: dict[str, tk.Variable] = {}
        self._build(values)

    def _build(self, values: dict[str, Any]) -> None:
        container = ttk.Frame(self)
        container.grid(row=0, column=0, sticky="nsew", padx=12, pady=12)
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        row = 0
        for field in self.spec.fields:
            ttk.Label(container, text=field.label).grid(row=row, column=0, sticky="w", padx=(0, 10), pady=6)

            if field.kind == "bool":
                var = tk.BooleanVar(value=bool(values.get(field.key, False)))
                widget = ttk.Checkbutton(container, variable=var, style="Form.TCheckbutton")
                widget.grid(row=row, column=1, sticky="w", pady=6)
                self.variables[field.key] = var
                row += 1
                continue

            if field.kind == "choice":
                default = values.get(field.key, field.choices[0] if field.choices else "")
                var = tk.StringVar(value=str(default))
                widget = ttk.Combobox(container, textvariable=var, values=field.choices, state="readonly")
                widget.grid(row=row, column=1, sticky="ew", pady=6)
                self.variables[field.key] = var
                row += 1
                continue

            var = tk.StringVar(value=str(values.get(field.key, "")))
            entry = ttk.Entry(container, textvariable=var)
            entry.grid(row=row, column=1, sticky="ew", pady=6)
            self.variables[field.key] = var

            if field.kind == "path":
                ttk.Button(
                    container,
                    text="Browse",
                    style="Secondary.TButton",
                    command=lambda f=field: self._browse_for_field(f),
                ).grid(row=row, column=2, sticky="w", padx=(8, 0), pady=6)

            row += 1

        container.columnconfigure(1, weight=1)

    def _browse_for_field(self, field: FieldSpec) -> None:
        current = self.variables[field.key].get().strip() if field.key in self.variables else ""
        lower_label = field.label.lower()

        chosen = ""
        if "folder" in lower_label or "directory" in lower_label:
            chosen = filedialog.askdirectory(initialdir=current or None)
        elif "input" in lower_label and ("xlsx" in lower_label or "docx" in lower_label):
            filetypes = [("All files", "*.*")]
            if "xlsx" in lower_label:
                filetypes.insert(0, ("Excel files", "*.xlsx"))
            if "docx" in lower_label:
                filetypes.insert(0, ("Word files", "*.docx"))
            chosen = filedialog.askopenfilename(initialdir=str(Path(current).parent) if current else None, filetypes=filetypes)
        elif "output" in lower_label and "html" in lower_label:
            chosen = filedialog.asksaveasfilename(defaultextension=".html", filetypes=[("HTML files", "*.html")])
        elif "output" in lower_label and "xlsx" in lower_label:
            chosen = filedialog.asksaveasfilename(defaultextension=".xlsx", filetypes=[("Excel files", "*.xlsx")])
        else:
            chosen = filedialog.askopenfilename(initialdir=str(Path(current).parent) if current else None)

        if chosen:
            self.variables[field.key].set(chosen)

    def get_values(self) -> dict[str, Any]:
        values: dict[str, Any] = {}
        for field in self.spec.fields:
            var = self.variables[field.key]
            value: Any
            if isinstance(var, tk.BooleanVar):
                value = bool(var.get())
            else:
                value = str(var.get()).strip()
            values[field.key] = value
        return values

    def set_values(self, values: dict[str, Any]) -> None:
        for field in self.spec.fields:
            if field.key not in self.variables:
                continue
            var = self.variables[field.key]
            raw = values.get(field.key, "")
            if isinstance(var, tk.BooleanVar):
                var.set(bool(raw))
            else:
                var.set(str(raw))

    def validate(self) -> list[str]:
        errors: list[str] = []
        values = self.get_values()
        for field in self.spec.fields:
            raw = values.get(field.key)
            if field.required and (raw is None or str(raw).strip() == ""):
                errors.append(f"{field.label} is required")
                continue

            if raw in (None, ""):
                continue

            try:
                if field.kind == "int":
                    int(str(raw))
                elif field.kind == "float":
                    float(str(raw))
            except ValueError:
                errors.append(f"{field.label} must be a valid {field.kind}")

        return errors


class PdfGuiApp(tk.Tk):
    def __init__(self, workspace_root: Path) -> None:
        super().__init__()
        self.workspace_root = workspace_root
        self.title("PDF Tools GUI")
        self.geometry("980x760")
        self.minsize(900, 650)
        self.option_add("*tearOff", False)
        self._configure_styles()

        self.paths = resolve_app_paths()
        self.log_ctx = configure_app_logger(self.paths.logs_root)
        self.logger = self.log_ctx.logger

        self.settings_store = SettingsStore(paths=self.paths)
        self.config_values = self.settings_store.load_config()
        self.runner = ProcessRunner()

        self.status_var = tk.StringVar(value="Ready")
        self.current_tool_var = tk.StringVar(value=TOOLS[0].title)

        self.forms: dict[str, ToolForm] = {}
        self._build_menu()
        self._build_layout()
        self._poll_runner_events()
        self._install_exception_handlers()

        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.logger.info("GUI started")

    def _configure_styles(self) -> None:
        style = ttk.Style(self)
        if "vista" in style.theme_names():
            style.theme_use("vista")
        elif "clam" in style.theme_names():
            style.theme_use("clam")

        default_font = tkfont.nametofont("TkDefaultFont")
        default_font.configure(size=10)
        text_font = tkfont.nametofont("TkTextFont")
        text_font.configure(size=10)
        heading_font = tkfont.nametofont("TkHeadingFont")
        heading_font.configure(size=10, weight="bold")

        style.configure("TButton", padding=(12, 6))
        style.configure("Toolbar.TButton", padding=(10, 5))
        style.configure("Primary.TButton", padding=(14, 6))
        style.configure("Secondary.TButton", padding=(10, 6))
        style.configure("Form.TCheckbutton", padding=(0, 2))
        style.configure("TLabelFrame", padding=(10, 8))
        style.configure("TNotebook.Tab", padding=(14, 8))
        style.configure("Muted.TLabel")

    def _build_menu(self) -> None:
        menu = tk.Menu(self)

        file_menu = tk.Menu(menu, tearoff=0)
        file_menu.add_command(label="Import Profile...", command=self._import_profile)
        file_menu.add_command(label="Export Profile...", command=self._export_profile)
        file_menu.add_separator()
        file_menu.add_command(label="Reset Defaults", command=self._reset_defaults)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self._on_close)
        menu.add_cascade(label="File", menu=file_menu)

        help_menu = tk.Menu(menu, tearoff=0)
        help_menu.add_command(label="Open Logs Folder", command=self._open_logs_folder)
        help_menu.add_command(label="Export Diagnostics...", command=self._export_diagnostics)
        help_menu.add_separator()
        help_menu.add_command(label="About", command=self._show_about)
        menu.add_cascade(label="Help", menu=help_menu)

        self.config(menu=menu)

    def _build_layout(self) -> None:
        top = ttk.LabelFrame(self, text="Quick Actions")
        top.pack(fill="x", padx=10, pady=(10, 6))

        for idx, tool in enumerate(TOOLS):
            ttk.Button(
                top,
                text=tool.title,
                style="Toolbar.TButton",
                command=lambda i=idx: self.notebook.select(i),
            ).pack(side="left", padx=4, pady=2)

        ttk.Label(top, text="Current Tool:", style="Muted.TLabel").pack(side="right", padx=(12, 4))
        ttk.Label(top, textvariable=self.current_tool_var).pack(side="right")

        center = ttk.Frame(self)
        center.pack(fill="both", expand=True, padx=10, pady=6)
        center.columnconfigure(0, weight=1)
        center.rowconfigure(0, weight=3)
        center.rowconfigure(2, weight=2)

        self.notebook = ttk.Notebook(center)
        self.notebook.grid(row=0, column=0, sticky="nsew")
        self.notebook.bind("<<NotebookTabChanged>>", self._on_tab_changed)

        for tool in TOOLS:
            values = self.config_values.get(tool.id, {})
            form = ToolForm(self.notebook, tool.id, values)
            self.forms[tool.id] = form
            self.notebook.add(form, text=tool.title)

        actions = ttk.LabelFrame(center, text="Actions")
        actions.grid(row=1, column=0, sticky="ew", pady=(10, 8))

        ttk.Button(actions, text="Run", style="Primary.TButton", command=self._run_active_tool).pack(side="left")
        self.cancel_button = ttk.Button(
            actions,
            text="Cancel",
            style="Secondary.TButton",
            command=self._cancel_active_run,
            state="disabled",
        )
        self.cancel_button.pack(side="left", padx=(6, 14))

        ttk.Button(actions, text="Save Profile", style="Secondary.TButton", command=self._save_profile).pack(side="left")
        ttk.Button(actions, text="Load Profile", style="Secondary.TButton", command=self._load_profile).pack(side="left", padx=(6, 0))
        ttk.Button(
            actions,
            text="Open Output Folder",
            style="Secondary.TButton",
            command=self._open_output_folder,
        ).pack(side="left", padx=(16, 0))

        self.progress = ttk.Progressbar(actions, mode="indeterminate", length=180)
        self.progress.pack(side="right")

        logs_frame = ttk.LabelFrame(center, text="Live Logs")
        logs_frame.grid(row=2, column=0, sticky="nsew")

        mono_family = "Consolas" if "Consolas" in tkfont.families() else "Courier New"
        self.logs_text = tk.Text(
            logs_frame,
            height=20,
            wrap="word",
            relief="flat",
            borderwidth=0,
            padx=8,
            pady=8,
            font=(mono_family, 10),
        )
        self.logs_text.pack(side="left", fill="both", expand=True)
        self.logs_text.configure(state="disabled")

        scrollbar = ttk.Scrollbar(logs_frame, orient="vertical", command=self.logs_text.yview)
        scrollbar.pack(side="right", fill="y")
        self.logs_text.configure(yscrollcommand=scrollbar.set)

        ttk.Separator(self, orient="horizontal").pack(fill="x", padx=10)

        status = ttk.Frame(self)
        status.pack(fill="x", padx=10, pady=(0, 10))
        ttk.Label(status, textvariable=self.status_var).pack(side="left")

    def _on_tab_changed(self, _event: tk.Event) -> None:
        tool = TOOLS[self.notebook.index(self.notebook.select())]
        self.current_tool_var.set(tool.title)

    def _active_tool_id(self) -> str:
        idx = self.notebook.index(self.notebook.select())
        return TOOLS[idx].id

    def _append_log(self, message: str, channel: str = "info") -> None:
        self.logs_text.configure(state="normal")
        prefix = ""
        if channel == "stderr":
            prefix = "[ERR] "
        elif channel == "start":
            prefix = "[CMD] "
        self.logs_text.insert("end", f"{prefix}{message}\n")
        self.logs_text.see("end")
        self.logs_text.configure(state="disabled")

        if channel == "stderr":
            self.logger.error(message)
        elif channel == "start":
            self.logger.info("RUN %s", message)
        else:
            self.logger.info(message)

    def _run_active_tool(self) -> None:
        if self.runner.is_running:
            messagebox.showwarning("Run in progress", "A task is already running.")
            return

        tool_id = self._active_tool_id()
        form = self.forms[tool_id]
        errors = form.validate()
        if errors:
            messagebox.showerror("Validation error", "\n".join(errors))
            return

        values = form.get_values()
        self.config_values[tool_id] = values

        argv = values_to_argv(tool_id, values)
        display = f"{TOOL_BY_ID[tool_id].title}: {' '.join(argv)}"
        self.logger.info("Starting tool=%s argv=%s", tool_id, argv)

        self.logs_text.configure(state="normal")
        self.logs_text.delete("1.0", "end")
        self.logs_text.configure(state="disabled")

        self.status_var.set(f"Running: {TOOL_BY_ID[tool_id].title}")
        self.cancel_button.configure(state="normal")
        self.progress.start(10)

        self.runner.start(
            task_name=display,
            task_fn=lambda: run_tool(tool_id=tool_id, values=values),
        )

    def _cancel_active_run(self) -> None:
        self.runner.cancel()
        self._append_log("Termination requested.", "stderr")
        self.status_var.set("Cancelling...")
        self.logger.warning("Cancellation requested by user")

    def _poll_runner_events(self) -> None:
        for event in self.runner.drain_events():
            if event.kind == "start":
                self._append_log(event.payload, "start")
            elif event.kind == "stdout":
                self._append_log(event.payload, "stdout")
            elif event.kind == "stderr":
                self._append_log(event.payload, "stderr")
            elif event.kind == "error":
                self._append_log(event.payload, "stderr")
                self._finish_run(-1)
            elif event.kind == "exit":
                self._finish_run(int(event.payload))
        self.after(120, self._poll_runner_events)

    def _finish_run(self, exit_code: int) -> None:
        self.progress.stop()
        self.cancel_button.configure(state="disabled")
        if exit_code == 0:
            self.status_var.set("Completed successfully")
            self._append_log("Completed successfully.")
            self.logger.info("Run completed successfully")
        else:
            self.status_var.set(f"Completed with exit code {exit_code}")
            self._append_log(f"Completed with exit code {exit_code}", "stderr")
            self.logger.error("Run completed with exit code %s", exit_code)

    def _save_profile(self) -> None:
        tool_id = self._active_tool_id()
        form = self.forms[tool_id]
        profile_name = simpledialog.askstring("Save Profile", "Profile name:", parent=self)
        if not profile_name:
            return
        path = self.settings_store.save_profile(tool_id, profile_name, form.get_values())
        self.status_var.set(f"Saved profile: {path.stem}")

    def _load_profile(self) -> None:
        tool_id = self._active_tool_id()
        profiles = self.settings_store.list_profiles(tool_id)
        if not profiles:
            messagebox.showinfo("Load Profile", "No profiles found for this tool.")
            return

        selected = simpledialog.askstring(
            "Load Profile",
            "Available profiles:\n" + "\n".join(profiles) + "\n\nType profile name:",
            parent=self,
        )
        if not selected:
            return

        try:
            payload = self.settings_store.load_profile(tool_id, selected)
        except Exception as exc:  # pylint: disable=broad-except
            messagebox.showerror("Load Profile", str(exc))
            return

        self.forms[tool_id].set_values(payload)
        self.status_var.set(f"Loaded profile: {selected}")

    def _import_profile(self) -> None:
        tool_id = self._active_tool_id()
        file_path = filedialog.askopenfilename(filetypes=[("JSON", "*.json"), ("All", "*.*")])
        if not file_path:
            return

        try:
            name = self.settings_store.import_profile(tool_id, Path(file_path))
        except Exception as exc:  # pylint: disable=broad-except
            messagebox.showerror("Import Profile", str(exc))
            self.logger.exception("Failed to import profile")
            return

        self.status_var.set(f"Imported profile: {name}")
        self.logger.info("Imported profile=%s tool=%s", name, tool_id)

    def _export_profile(self) -> None:
        tool_id = self._active_tool_id()
        profiles = self.settings_store.list_profiles(tool_id)
        if not profiles:
            messagebox.showinfo("Export Profile", "No profiles found for this tool.")
            return

        selected = simpledialog.askstring(
            "Export Profile",
            "Available profiles:\n" + "\n".join(profiles) + "\n\nType profile name:",
            parent=self,
        )
        if not selected:
            return

        target = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("JSON", "*.json")])
        if not target:
            return

        try:
            self.settings_store.export_profile(tool_id, selected, Path(target))
        except Exception as exc:  # pylint: disable=broad-except
            messagebox.showerror("Export Profile", str(exc))
            self.logger.exception("Failed to export profile")
            return

        self.status_var.set(f"Exported profile: {selected}")
        self.logger.info("Exported profile=%s tool=%s", selected, tool_id)

    def _open_output_folder(self) -> None:
        tool_id = self._active_tool_id()
        values = self.forms[tool_id].get_values()
        output = str(values.get("output", "")).strip()

        if not output and tool_id == "compress":
            input_path = str(values.get("input", "")).strip()
            if input_path:
                output = str(Path(input_path) / "compressedfiles")

        if not output:
            messagebox.showinfo("Open Output Folder", "No output folder is set for this tool.")
            return

        path = Path(output)
        folder = path if path.is_dir() else path.parent
        if not folder.exists():
            messagebox.showerror("Open Output Folder", f"Path does not exist: {folder}")
            return

        os.startfile(folder)  # type: ignore[attr-defined]

    def _reset_defaults(self) -> None:
        self.config_values = self.settings_store.reset_defaults()
        for tool in TOOLS:
            self.forms[tool.id].set_values(self.config_values.get(tool.id, {}))
        self.status_var.set("Defaults restored")
        self.logger.info("Defaults restored")

    def _open_logs_folder(self) -> None:
        if not self.paths.logs_root.exists():
            messagebox.showerror("Logs", f"Logs folder not found: {self.paths.logs_root}")
            return
        os.startfile(self.paths.logs_root)  # type: ignore[attr-defined]

    def _export_diagnostics(self) -> None:
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        default_name = f"pdf_tools_gui_diagnostics_{stamp}.zip"
        destination = filedialog.asksaveasfilename(
            defaultextension=".zip",
            initialfile=default_name,
            filetypes=[("ZIP archive", "*.zip")],
        )
        if not destination:
            return

        try:
            bundle = create_diagnostics_bundle(
                workspace_root=self.workspace_root,
                paths=self.paths,
                destination_zip=Path(destination),
            )
        except Exception as exc:  # pylint: disable=broad-except
            self.logger.exception("Diagnostics export failed")
            messagebox.showerror("Diagnostics", f"Failed to export diagnostics:\n{exc}")
            return

        self.logger.info("Diagnostics bundle created: %s", bundle)
        messagebox.showinfo("Diagnostics", f"Diagnostics bundle created:\n{bundle}")

    def _install_exception_handlers(self) -> None:
        def _sys_hook(exc_type, exc_value, exc_traceback) -> None:
            self._handle_unhandled_exception(exc_type, exc_value, exc_traceback)

        def _thread_hook(args) -> None:
            self._handle_unhandled_exception(args.exc_type, args.exc_value, args.exc_traceback)

        self.report_callback_exception = self._handle_unhandled_exception
        sys.excepthook = _sys_hook
        if hasattr(threading, "excepthook"):
            threading.excepthook = _thread_hook

    def _handle_unhandled_exception(self, exc_type, exc_value, exc_traceback) -> None:
        self.logger.exception(
            "Unhandled exception",
            exc_info=(exc_type, exc_value, exc_traceback),
        )
        messagebox.showerror(
            "Unexpected Error",
            "An unexpected error occurred.\n"
            f"Details were written to:\n{self.paths.app_log_file}\n\n"
            "Use Help > Export Diagnostics to create a support bundle.",
        )

    def _show_about(self) -> None:
        messagebox.showinfo(
            "About",
            "PDF Tools GUI\n\n"
            "Wraps existing Python CLI tools in this workspace.\n"
            "Execution mode: in-process (shared core)\n"
            f"Log file: {self.paths.app_log_file}",
        )

    def _on_close(self) -> None:
        for tool in TOOLS:
            self.config_values[tool.id] = self.forms[tool.id].get_values()
        self.settings_store.save_config(self.config_values)
        self.logger.info("GUI closed")
        self.destroy()


def run_gui() -> None:
    workspace_root = Path(__file__).resolve().parent.parent.parent
    app = PdfGuiApp(workspace_root=workspace_root)
    app.mainloop()
