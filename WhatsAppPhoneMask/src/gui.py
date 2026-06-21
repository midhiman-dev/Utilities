#!/usr/bin/env python3
"""
gui.py - Windows Desktop GUI for WhatsApp PII Masker.
"""

from __future__ import annotations

import os
import queue
import subprocess
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from pathlib import Path

# Enable DPI awareness on Windows to prevent blurry GUI text
try:
    from ctypes import windll
    windll.shcore.SetProcessDpiAwareness(1)
except ImportError:
    pass

# Import core masking functions
from mask_core import mask_phone_numbers


class WhatsAppMaskerGUI:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("WhatsApp PII Masker")
        self.root.geometry("950x700")
        self.root.minsize(800, 550)

        # Thread safety communication queue
        self.queue: queue.Queue = queue.Queue()
        self.cancel_event = threading.Event()
        self.worker_thread: threading.Thread | None = None

        # State variables
        self.input_file_path: Path | None = None
        self.output_file_path: Path | None = None
        self.default_output_suffix = ".masked.txt"

        # Theme Colors (Dark Theme)
        self.bg_color = "#1e1e1e"
        self.panel_bg = "#252526"
        self.fg_color = "#d4d4d4"
        self.accent_color = "#007acc"
        self.accent_fg = "#ffffff"
        self.hover_color = "#1e8ad6"
        self.border_color = "#3e3e42"
        self.text_bg = "#1e1e1e"
        self.text_fg = "#d4d4d4"

        # Set up styles
        self.setup_styles()

        # Build Main Layout
        self.build_ui()

        # Start periodic queue polling
        self.poll_queue()

    def setup_styles(self) -> None:
        self.style = ttk.Style()
        self.style.theme_use("clam")

        # Global theme configuration
        self.style.configure(".", background=self.bg_color, foreground=self.fg_color, bordercolor=self.border_color)
        
        self.style.configure("TFrame", background=self.bg_color)
        self.style.configure("TLabel", background=self.bg_color, foreground=self.fg_color, font=("Segoe UI", 10))
        
        # Buttons
        self.style.configure("TButton", background=self.panel_bg, foreground=self.fg_color, bordercolor=self.border_color, padding=[10, 5], font=("Segoe UI", 9))
        self.style.map("TButton",
                       background=[("active", self.hover_color), ("disabled", "#333333")],
                       foreground=[("active", self.accent_fg), ("disabled", "#666666")])

        # Accent button for primary actions
        self.style.configure("Accent.TButton", background=self.accent_color, foreground=self.accent_fg, font=("Segoe UI", 10, "bold"))
        self.style.map("Accent.TButton",
                       background=[("active", self.hover_color), ("disabled", "#333333")],
                       foreground=[("active", self.accent_fg), ("disabled", "#666666")])

        # Danger button for Cancel action
        self.style.configure("Danger.TButton", background="#a82020", foreground=self.accent_fg, font=("Segoe UI", 9, "bold"))
        self.style.map("Danger.TButton",
                       background=[("active", "#c22d2d"), ("disabled", "#333333")],
                       foreground=[("active", self.accent_fg), ("disabled", "#666666")])

        # Notebook / Tabs
        self.style.configure("TNotebook", background=self.bg_color, tabmargins=[4, 6, 4, 0])
        self.style.configure("TNotebook.Tab", background=self.panel_bg, foreground=self.fg_color, borderwidth=1, padding=[12, 6], font=("Segoe UI", 10))
        self.style.map("TNotebook.Tab",
                       background=[("selected", self.bg_color), ("active", self.hover_color)],
                       foreground=[("selected", self.accent_fg), ("active", self.accent_fg)])

        # Checkbutton / Radiobutton
        self.style.configure("TCheckbutton", background=self.bg_color, foreground=self.fg_color, font=("Segoe UI", 10))
        self.style.map("TCheckbutton", background=[("active", self.bg_color)], foreground=[("active", self.fg_color)])
        
        self.style.configure("TRadiobutton", background=self.bg_color, foreground=self.fg_color, font=("Segoe UI", 10))
        self.style.map("TRadiobutton", background=[("active", self.bg_color)], foreground=[("active", self.fg_color)])

        # LabelFrame
        self.style.configure("TLabelframe", background=self.bg_color, bordercolor=self.border_color, padding=10)
        self.style.configure("TLabelframe.Label", background=self.bg_color, foreground=self.accent_color, font=("Segoe UI", 10, "bold"))

        # Progressbar
        self.style.configure("Horizontal.TProgressbar", background=self.accent_color, troughcolor=self.panel_bg, bordercolor=self.border_color)

    def build_ui(self) -> None:
        # Root layout uses grid for precise sizing
        self.root.configure(background=self.bg_color)
        self.root.rowconfigure(1, weight=1)
        self.root.columnconfigure(0, weight=1)

        # 1. Common Settings Header
        settings_frame = ttk.LabelFrame(self.root, text="Masking Settings")
        settings_frame.grid(row=0, column=0, padx=15, pady=(15, 5), sticky="ew")
        
        # Settings Layout (3 columns)
        self.loose_var = tk.BooleanVar(value=False)
        self.loose_cb = ttk.Checkbutton(settings_frame, text="Loose mode (mask numbers without + or 00 prefix)", variable=self.loose_var)
        self.loose_cb.grid(row=0, column=0, padx=10, pady=5, sticky="w")

        # Min digits spinbox
        min_frame = ttk.Frame(settings_frame)
        min_frame.grid(row=0, column=1, padx=20, pady=5, sticky="w")
        ttk.Label(min_frame, text="Min digits: ").pack(side=tk.LEFT)
        self.min_digits_var = tk.IntVar(value=7)
        self.min_digits_sb = ttk.Spinbox(min_frame, from_=3, to=30, width=5, textvariable=self.min_digits_var, justify="center")
        self.min_digits_sb.pack(side=tk.LEFT)

        # Max digits spinbox
        max_frame = ttk.Frame(settings_frame)
        max_frame.grid(row=0, column=2, padx=20, pady=5, sticky="w")
        ttk.Label(max_frame, text="Max digits: ").pack(side=tk.LEFT)
        self.max_digits_var = tk.IntVar(value=15)
        self.max_digits_sb = ttk.Spinbox(max_frame, from_=3, to=30, width=5, textvariable=self.max_digits_var, justify="center")
        self.max_digits_sb.pack(side=tk.LEFT)

        # 2. Main Tabbed Area (Notebook)
        self.notebook = ttk.Notebook(self.root)
        self.notebook.grid(row=1, column=0, padx=15, pady=10, sticky="nsew")

        self.file_tab = ttk.Frame(self.notebook)
        self.paste_tab = ttk.Frame(self.notebook)

        self.notebook.add(self.file_tab, text="  File Masking  ")
        self.notebook.add(self.paste_tab, text="  Paste Masking  ")

        # Build individual tabs
        self.build_file_tab()
        self.build_paste_tab()

        # 3. Status Bar & Execution Controls (Bottom)
        self.bottom_frame = ttk.Frame(self.root)
        self.bottom_frame.grid(row=2, column=0, padx=15, pady=(5, 15), sticky="ew")
        self.bottom_frame.columnconfigure(0, weight=1)

        # Status text & info
        self.status_label = ttk.Label(self.bottom_frame, text="Ready", font=("Segoe UI", 10, "italic"))
        self.status_label.grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 5))

        # Progress bar
        self.progress_bar = ttk.Progressbar(self.bottom_frame, mode="indeterminate", style="Horizontal.TProgressbar")
        self.progress_bar.grid(row=1, column=0, sticky="ew", padx=(0, 10))

        # Action Buttons frame
        self.control_buttons_frame = ttk.Frame(self.bottom_frame)
        self.control_buttons_frame.grid(row=1, column=1, sticky="e")

        self.cancel_btn = ttk.Button(self.control_buttons_frame, text="Cancel", style="Danger.TButton", command=self.cancel_task, state="disabled")
        self.cancel_btn.pack(side=tk.LEFT, padx=2)

        self.open_folder_btn = ttk.Button(self.control_buttons_frame, text="Open Folder", command=self.open_containing_folder, state="disabled")
        self.open_folder_btn.pack(side=tk.LEFT, padx=2)

    def build_file_tab(self) -> None:
        self.file_tab.rowconfigure(2, weight=1)
        self.file_tab.columnconfigure(0, weight=1)

        # File picker section
        picker_frame = ttk.Frame(self.file_tab)
        picker_frame.grid(row=0, column=0, padx=10, pady=10, sticky="ew")
        picker_frame.columnconfigure(1, weight=1)

        self.open_file_btn = ttk.Button(picker_frame, text="Open Chat File...", command=self.open_chat_file)
        self.open_file_btn.pack(side=tk.LEFT, padx=(0, 10))

        self.file_path_label = ttk.Label(picker_frame, text="No file selected", font=("Segoe UI", 9), anchor="w")
        self.file_path_label.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # Output selection section
        output_frame = ttk.LabelFrame(self.file_tab, text="Output Directory / File Settings")
        output_frame.grid(row=1, column=0, padx=10, pady=5, sticky="ew")
        
        self.output_mode_var = tk.StringVar(value="new")
        
        self.rb_new = ttk.Radiobutton(output_frame, text="Save as new file (.masked.txt)", value="new", variable=self.output_mode_var, command=self.update_output_mode)
        self.rb_new.grid(row=0, column=0, sticky="w", padx=5, pady=2)

        self.rb_inplace = ttk.Radiobutton(output_frame, text="Overwrite original (in-place)", value="inplace", variable=self.output_mode_var, command=self.update_output_mode)
        self.rb_inplace.grid(row=0, column=1, sticky="w", padx=10, pady=2)

        # Custom output file picker
        self.custom_output_frame = ttk.Frame(output_frame)
        self.custom_output_frame.grid(row=1, column=0, columnspan=2, sticky="ew", padx=5, pady=(5, 2))
        
        self.save_as_btn = ttk.Button(self.custom_output_frame, text="Save As...", command=self.select_custom_output)
        self.save_as_btn.pack(side=tk.LEFT, padx=(0, 10))
        
        self.output_path_label = ttk.Label(self.custom_output_frame, text="Output: default (<input>.masked.txt)", font=("Segoe UI", 9, "italic"))
        self.output_path_label.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # Preview Section (Scrollable read-only text widget)
        preview_frame = ttk.LabelFrame(self.file_tab, text="File Preview (First 500 lines)")
        preview_frame.grid(row=2, column=0, padx=10, pady=10, sticky="nsew")
        preview_frame.rowconfigure(0, weight=1)
        preview_frame.columnconfigure(0, weight=1)

        # Scrollbars & Text
        self.preview_text = tk.Text(preview_frame, bg=self.text_bg, fg=self.text_fg, 
                                    insertbackground=self.fg_color, selectbackground=self.accent_color,
                                    selectforeground=self.accent_fg, bd=1, relief="solid",
                                    highlightthickness=0, font=("Consolas", 10), wrap="none")
        self.preview_text.grid(row=0, column=0, sticky="nsew")
        self.preview_text.insert(tk.END, "No file loaded. Click 'Open Chat File...' to load a preview.")
        self.preview_text.config(state="disabled")

        scrollbar_y = ttk.Scrollbar(preview_frame, orient="vertical", command=self.preview_text.yview)
        scrollbar_y.grid(row=0, column=1, sticky="ns")
        self.preview_text.config(yscrollcommand=scrollbar_y.set)

        scrollbar_x = ttk.Scrollbar(preview_frame, orient="horizontal", command=self.preview_text.xview)
        scrollbar_x.grid(row=1, column=0, sticky="ew")
        self.preview_text.config(xscrollcommand=scrollbar_x.set)

        # Mask File button at the bottom of the tab
        self.mask_file_btn = ttk.Button(self.file_tab, text="Mask File", style="Accent.TButton", command=self.mask_file, state="disabled")
        self.mask_file_btn.grid(row=3, column=0, padx=10, pady=(5, 10), sticky="ew")

    def build_paste_tab(self) -> None:
        self.paste_tab.rowconfigure(1, weight=1)
        self.paste_tab.columnconfigure(0, weight=1)
        self.paste_tab.columnconfigure(1, weight=1)

        # Intro instructions
        lbl_instruct = ttk.Label(self.paste_tab, text="Paste text below, click 'Mask Text' to mask it instantly, and copy the result.", font=("Segoe UI", 9, "italic"))
        lbl_instruct.grid(row=0, column=0, columnspan=2, padx=10, pady=5, sticky="w")

        # Original / Input text frame
        orig_frame = ttk.LabelFrame(self.paste_tab, text="Original Text")
        orig_frame.grid(row=1, column=0, padx=(10, 5), pady=5, sticky="nsew")
        orig_frame.rowconfigure(0, weight=1)
        orig_frame.columnconfigure(0, weight=1)

        self.input_text = tk.Text(orig_frame, bg=self.text_bg, fg=self.text_fg, 
                                  insertbackground=self.fg_color, selectbackground=self.accent_color,
                                  selectforeground=self.accent_fg, bd=1, relief="solid",
                                  highlightthickness=0, font=("Consolas", 10))
        self.input_text.grid(row=0, column=0, sticky="nsew")

        scroller_input = ttk.Scrollbar(orig_frame, orient="vertical", command=self.input_text.yview)
        scroller_input.grid(row=0, column=1, sticky="ns")
        self.input_text.config(yscrollcommand=scroller_input.set)

        # Masked / Output text frame
        masked_frame = ttk.LabelFrame(self.paste_tab, text="Masked Text")
        masked_frame.grid(row=1, column=1, padx=(5, 10), pady=5, sticky="nsew")
        masked_frame.rowconfigure(0, weight=1)
        masked_frame.columnconfigure(0, weight=1)

        self.output_text = tk.Text(masked_frame, bg=self.text_bg, fg=self.text_fg, 
                                   insertbackground=self.fg_color, selectbackground=self.accent_color,
                                   selectforeground=self.accent_fg, bd=1, relief="solid",
                                   highlightthickness=0, font=("Consolas", 10), state="disabled")
        self.output_text.grid(row=0, column=0, sticky="nsew")

        scroller_output = ttk.Scrollbar(masked_frame, orient="vertical", command=self.output_text.yview)
        scroller_output.grid(row=0, column=1, sticky="ns")
        self.output_text.config(yscrollcommand=scroller_output.set)

        # Control panel under text panes
        control_frame = ttk.Frame(self.paste_tab)
        control_frame.grid(row=2, column=0, columnspan=2, padx=10, pady=10, sticky="ew")

        self.mask_text_btn = ttk.Button(control_frame, text="Mask Text", style="Accent.TButton", command=self.mask_pasted_text)
        self.mask_text_btn.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))

        self.copy_btn = ttk.Button(control_frame, text="Copy to Clipboard", command=self.copy_to_clipboard, state="disabled")
        self.copy_btn.pack(side=tk.RIGHT, fill=tk.X, expand=True, padx=(5, 0))

    def update_output_mode(self) -> None:
        # Enable/Disable output custom path selection
        if self.output_mode_var.get() == "inplace":
            self.save_as_btn.config(state="disabled")
            self.output_path_label.config(text="Output: Overwrite original file (in-place)", font=("Segoe UI", 9, "italic"))
        else:
            self.save_as_btn.config(state="normal")
            if self.output_file_path:
                self.output_path_label.config(text=f"Output: {self.output_file_path.name}", font=("Segoe UI", 9))
            elif self.input_file_path:
                # set default masked output label
                default_name = self.input_file_path.stem + self.default_output_suffix
                self.output_path_label.config(text=f"Output: {default_name} (default)", font=("Segoe UI", 9, "italic"))
            else:
                self.output_path_label.config(text="Output: default (<input>.masked.txt)", font=("Segoe UI", 9, "italic"))

    def open_chat_file(self) -> None:
        file_path = filedialog.askopenfilename(
            title="Open WhatsApp Chat Export",
            filetypes=[("Text Files", "*.txt"), ("All Files", "*.*")]
        )
        if not file_path:
            return

        self.input_file_path = Path(file_path)
        self.file_path_label.config(text=str(self.input_file_path), font=("Segoe UI", 9))
        self.output_file_path = None # Reset custom path on new input
        
        self.update_output_mode()
        
        # Load preview safely (only up to 500 lines)
        self.preview_text.config(state="normal")
        self.preview_text.delete("1.0", tk.END)
        self.preview_text.insert(tk.END, "Loading preview...")
        self.preview_text.config(state="disabled")
        
        # Perform preview loading in a small background thread to keep file UI instantly snappy
        threading.Thread(target=self._async_load_preview, args=(self.input_file_path,), daemon=True).start()
        
        self.mask_file_btn.config(state="normal")
        self.status_label.config(text="File loaded. Preview ready.")
        self.open_folder_btn.config(state="disabled")

    def _async_load_preview(self, path: Path) -> None:
        preview_lines = []
        try:
            with path.open("r", encoding="utf-8", errors="replace") as f:
                for _ in range(500):
                    line = f.readline()
                    if not line:
                        break
                    preview_lines.append(line)
            preview_content = "".join(preview_lines)
            if not preview_content.strip():
                preview_content = "<File is empty>"
        except Exception as e:
            preview_content = f"Error loading preview: {str(e)}"

        # Update text UI in main thread
        def update_ui():
            self.preview_text.config(state="normal")
            self.preview_text.delete("1.0", tk.END)
            self.preview_text.insert(tk.END, preview_content)
            self.preview_text.config(state="disabled")
        
        self.root.after(0, update_ui)

    def select_custom_output(self) -> None:
        if not self.input_file_path:
            messagebox.showwarning("Warning", "Please load an input file first.")
            return

        initial_name = self.input_file_path.stem + self.default_output_suffix
        out_path = filedialog.asksaveasfilename(
            title="Save Masked File As",
            initialfile=initial_name,
            defaultextension=".txt",
            filetypes=[("Text Files", "*.txt"), ("All Files", "*.*")]
        )
        if out_path:
            self.output_file_path = Path(out_path)
            self.output_path_label.config(text=f"Output: {self.output_file_path.name}", font=("Segoe UI", 9))

    def mask_file(self) -> None:
        if not self.input_file_path:
            messagebox.showerror("Error", "No input file loaded.")
            return

        if not self.input_file_path.exists():
            messagebox.showerror("Error", f"Input file no longer exists: {self.input_file_path}")
            return

        # Prepare outputs
        if self.output_mode_var.get() == "inplace":
            out_dest = None
        else:
            if self.output_file_path:
                out_dest = self.output_file_path
            else:
                # Default output companion file
                out_dest = self.input_file_path.with_name(self.input_file_path.stem + self.default_output_suffix)

        # Confirm before in-place overwrite
        if self.output_mode_var.get() == "inplace":
            confirm = messagebox.askyesno(
                "Confirm Overwrite",
                "Are you sure you want to overwrite the original file in-place?\nThis operation cannot be undone.",
                icon="warning"
            )
            if not confirm:
                return

        # Validate spinbox limits
        try:
            min_d = self.min_digits_var.get()
            max_d = self.max_digits_var.get()
            if min_d <= 0 or max_d <= 0:
                raise ValueError("Digit bounds must be greater than zero.")
            if min_d > max_d:
                raise ValueError("Min digits cannot be greater than Max digits.")
        except Exception as e:
            messagebox.showerror("Invalid Settings", f"Please check digit count bounds: {str(e)}")
            return

        mask_kwargs = {
            "min_digits": min_d,
            "max_digits": max_d,
            "require_plus": not self.loose_var.get()
        }

        # Clear state
        self.cancel_event.clear()
        self.last_saved_file = out_dest if out_dest else self.input_file_path

        # UI updates to running state
        self.set_ui_running(True)
        self.status_label.config(text="Masking file in progress...")
        self.progress_bar.start(10) # Start fast scanning animation

        # Spawn worker
        self.worker_thread = threading.Thread(
            target=self.mask_file_worker,
            args=(self.input_file_path, out_dest, mask_kwargs),
            daemon=True
        )
        self.worker_thread.start()

    def mask_file_worker(self, in_path: Path, out_path: Path | None, mask_kwargs: dict) -> None:
        try:
            # If in-place, write to a temp file in the same directory first
            actual_out_path = out_path if out_path else in_path.with_suffix(in_path.suffix + ".tmp")

            total_masked = 0
            line_count = 0

            # Ensure parent directories exist
            actual_out_path.parent.mkdir(parents=True, exist_ok=True)

            with in_path.open("r", encoding="utf-8", errors="replace") as f_in, \
                 actual_out_path.open("w", encoding="utf-8") as f_out:
                
                for line in f_in:
                    if self.cancel_event.is_set():
                        # Close files immediately
                        f_out.close()
                        f_in.close()
                        # Cleanup temp file if in-place mode
                        if not out_path and actual_out_path.exists():
                            try:
                                actual_out_path.unlink()
                            except:
                                pass
                        self.queue.put(("canceled", None))
                        return

                    masked, n = mask_phone_numbers(line, **mask_kwargs)
                    f_out.write(masked)
                    total_masked += n
                    line_count += 1

                    # Throttle queue updates
                    if line_count % 2000 == 0:
                        self.queue.put(("progress", (line_count, total_masked)))

            # If in-place, swap tmp file into the original position
            if not out_path:
                # Remove original if replace is sensitive, but replace does it atomically
                actual_out_path.replace(in_path)
                saved_to = in_path
            else:
                saved_to = actual_out_path

            self.queue.put(("success", (total_masked, saved_to)))

        except Exception as e:
            # General cleanup on exception
            if not out_path and "actual_out_path" in locals() and actual_out_path.exists():
                try:
                    actual_out_path.unlink()
                except:
                    pass
            self.queue.put(("error", str(e)))

    def cancel_task(self) -> None:
        if self.worker_thread and self.worker_thread.is_alive():
            self.cancel_event.set()
            self.status_label.config(text="Sending cancel request...")
            self.cancel_btn.config(state="disabled")

    def set_ui_running(self, running: bool) -> None:
        state = "disabled" if running else "normal"
        self.open_file_btn.config(state=state)
        self.mask_file_btn.config(state=state)
        self.rb_new.config(state=state)
        self.rb_inplace.config(state=state)
        
        if not running and self.output_mode_var.get() == "inplace":
            self.save_as_btn.config(state="disabled")
        else:
            self.save_as_btn.config(state=state)

        # Tab notebook lock
        tab_state = "disabled" if running else "normal"
        self.notebook.tab(1, state=tab_state) # Lock paste tab while file masking

        # Settings lock
        self.loose_cb.config(state=state)
        self.min_digits_sb.config(state=state)
        self.max_digits_sb.config(state=state)

        # Cancel button controls
        self.cancel_btn.config(state="normal" if running else "disabled")

    def poll_queue(self) -> None:
        """Poll thread queue and process messages to update the GUI."""
        try:
            while True:
                msg_type, data = self.queue.get_nowait()
                if msg_type == "progress":
                    lines, count = data
                    self.status_label.config(text=f"Processed {lines} lines... Masked {count} numbers so far.")
                elif msg_type == "success":
                    total_masked, saved_to = data
                    self.progress_bar.stop()
                    self.set_ui_running(False)
                    self.status_label.config(text=f"Completed! Masked {total_masked} phone number(s). Saved to: {saved_to}")
                    self.open_folder_btn.config(state="normal")
                    messagebox.showinfo("Success", f"Masking complete!\n\nMasked {total_masked} phone number(s).\nSaved to:\n{saved_to}")
                elif msg_type == "canceled":
                    self.progress_bar.stop()
                    self.set_ui_running(False)
                    self.status_label.config(text="Operation canceled by user.")
                    messagebox.showwarning("Canceled", "The masking operation was aborted.")
                elif msg_type == "error":
                    self.progress_bar.stop()
                    self.set_ui_running(False)
                    self.status_label.config(text="Error occurred during masking.")
                    messagebox.showerror("Error", f"An error occurred:\n{data}")
                
                self.queue.task_done()
        except queue.Empty:
            pass

        # Reschedule polling
        self.root.after(100, self.poll_queue)

    def open_containing_folder(self) -> None:
        if hasattr(self, "last_saved_file") and self.last_saved_file:
            path_str = str(self.last_saved_file.resolve())
            try:
                # Windows Explorer file selection command
                subprocess.Popen(["explorer", "/select,", path_str])
            except Exception as e:
                messagebox.showerror("Error", f"Could not open directory: {str(e)}")

    def mask_pasted_text(self) -> None:
        raw_text = self.input_text.get("1.0", tk.END)
        if not raw_text.strip() or raw_text.strip() == "No file loaded. Click 'Open Chat File...' to load a preview.":
            messagebox.showwarning("Empty Input", "Please paste or type some text first.")
            return

        # Validate spinboxes
        try:
            min_d = self.min_digits_var.get()
            max_d = self.max_digits_var.get()
            if min_d <= 0 or max_d <= 0:
                raise ValueError("Digit bounds must be greater than zero.")
            if min_d > max_d:
                raise ValueError("Min digits cannot be greater than Max digits.")
        except Exception as e:
            messagebox.showerror("Invalid Settings", f"Please check digit count bounds: {str(e)}")
            return

        # Run mask
        try:
            masked, count = mask_phone_numbers(
                raw_text,
                min_digits=min_d,
                max_digits=max_d,
                require_plus=not self.loose_var.get()
            )

            # Update Output UI
            self.output_text.config(state="normal")
            self.output_text.delete("1.0", tk.END)
            self.output_text.insert(tk.END, masked)
            self.output_text.config(state="disabled")

            self.copy_btn.config(state="normal")
            self.status_label.config(text=f"Pasted text masked successfully. Found and masked {count} number(s).")
        except Exception as e:
            messagebox.showerror("Masking Error", f"Failed to mask text: {str(e)}")

    def copy_to_clipboard(self) -> None:
        try:
            masked_text = self.output_text.get("1.0", tk.END)
            # Remove trailing newline added by tk.Text
            if masked_text.endswith("\n"):
                masked_text = masked_text[:-1]

            self.root.clipboard_clear()
            self.root.clipboard_append(masked_text)
            self.root.update() # Keeps text in clipboard even after window closes
            self.status_label.config(text="Masked text copied to clipboard!")
        except Exception as e:
            messagebox.showerror("Clipboard Error", f"Failed to copy to clipboard: {str(e)}")


def main() -> None:
    root = tk.Tk()
    app = WhatsAppMaskerGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
