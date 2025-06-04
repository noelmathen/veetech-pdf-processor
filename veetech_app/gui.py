# veetech_app/gui.py

import sys
import os
import threading
import tempfile
import shutil
import traceback
from datetime import datetime
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
from .config import AppConfig
from .logger import AppLogger
from .update_manager import UpdateManager
from .processor import VeetechProcessor, ProcessingResult


def resource_path(rel_path: str) -> str:
    """Return absolute path to resource, works for dev and PyInstaller."""
    base = getattr(sys, "_MEIPASS", os.path.abspath("."))
    return os.path.join(base, rel_path)


class VeetechDesktopApp:
    """Main desktop application class."""

    def __init__(self):
        self.config = AppConfig()
        self.logger_manager = AppLogger(self.config)
        self.logger = AppLogger.get_logger(__name__)

        # Application state
        self.selected_file = None
        self.processing = False

        # Setup GUI (defines self.root)
        self.setup_gui()

        # Now that self.root exists, instantiate UpdateManager
        self.update_manager = UpdateManager(self.config, root_window=self.root)

        # Check for updates on startup
        if self.config.auto_check_updates:
            self.check_updates_silent()

    def setup_gui(self):
        """Setup the main GUI."""
        self.root = tk.Tk()
        self.root.title(f"{self.config.app_name} v{self.config.version}")
        self.root.geometry("800x600")
        self.root.resizable(True, True)

        try:
            self.root.iconbitmap(resource_path("assets\\veetech_icon.ico"))
        except:
            pass

        self.setup_styles()

        self.main_frame = ttk.Frame(self.root, padding="20")
        self.main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        self.main_frame.columnconfigure(1, weight=1)

        self.create_header()
        self.create_file_selection()
        self.create_processing_options()
        self.create_progress_section()
        self.create_log_section()
        self.create_action_buttons()
        self.create_menu()

    def setup_styles(self):
        style = ttk.Style()
        style.configure("Header.TLabel", font=("Segoe UI", 16, "bold"))
        style.configure("Subheader.TLabel", font=("Segoe UI", 10, "bold"))
        style.configure("Action.TButton", font=("Segoe UI", 10, "bold"))

    def create_header(self):
        header_frame = ttk.Frame(self.main_frame)
        header_frame.grid(row=0, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(0, 20))

        ttk.Label(
            header_frame,
            text=self.config.app_name,
            style="Header.TLabel"
        ).grid(row=0, column=0, sticky=tk.W)

        ttk.Label(
            header_frame,
            text=f"Version {self.config.version}",
            foreground="gray"
        ).grid(row=1, column=0, sticky=tk.W)

    def create_file_selection(self):
        ttk.Label(
            self.main_frame,
            text="Select PDF File:",
            style="Subheader.TLabel"
        ).grid(row=1, column=0, sticky=tk.W, pady=(0, 5))

        file_frame = ttk.Frame(self.main_frame)
        file_frame.grid(row=2, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(0, 15))
        file_frame.columnconfigure(1, weight=1)

        self.file_path_var = tk.StringVar()
        self.file_path_entry = ttk.Entry(
            file_frame,
            textvariable=self.file_path_var,
            state="readonly",
            width=50
        )
        self.file_path_entry.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(0, 10))

        ttk.Button(
            file_frame,
            text="Browse...",
            command=self.browse_file
        ).grid(row=0, column=2, sticky=tk.W)

    def create_processing_options(self):
        options_frame = ttk.LabelFrame(
            self.main_frame,
            text="Processing Options",
            padding="10"
        )
        options_frame.grid(row=3, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(0, 15))

        self.auto_organize_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            options_frame,
            text="Automatically organize files by tag",
            variable=self.auto_organize_var
        ).grid(row=0, column=0, sticky=tk.W, pady=2)

        self.save_logs_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            options_frame,
            text="Save processing logs",
            variable=self.save_logs_var
        ).grid(row=1, column=0, sticky=tk.W, pady=2)

        self.force_ocr_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            options_frame,
            text="Force OCR processing (recommended)",
            variable=self.force_ocr_var
        ).grid(row=2, column=0, sticky=tk.W, pady=2)

    def create_progress_section(self):
        progress_frame = ttk.LabelFrame(
            self.main_frame,
            text="Processing Progress",
            padding="10"
        )
        progress_frame.grid(row=4, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(0, 15))
        progress_frame.columnconfigure(0, weight=1)

        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(
            progress_frame,
            variable=self.progress_var,
            mode="indeterminate"
        )
        self.progress_bar.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 5))

        self.status_var = tk.StringVar(value="Ready to process")
        self.status_label = ttk.Label(
            progress_frame,
            textvariable=self.status_var,
            foreground="blue"
        )
        self.status_label.grid(row=1, column=0, sticky=tk.W)

    def create_log_section(self):
        log_frame = ttk.LabelFrame(
            self.main_frame,
            text="Processing Log",
            padding="10"
        )
        log_frame.grid(row=5, column=0, columnspan=3, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 15))
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)
        self.main_frame.rowconfigure(5, weight=1)

        self.log_text = scrolledtext.ScrolledText(
            log_frame,
            height=10,
            state="disabled",
            wrap=tk.WORD
        )
        self.log_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        log_controls = ttk.Frame(log_frame)
        log_controls.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=(5, 0))

        ttk.Button(
            log_controls,
            text="Clear Log",
            command=self.clear_log
        ).grid(row=0, column=0, sticky=tk.W)

        ttk.Button(
            log_controls,
            text="Save Log",
            command=self.save_log
        ).grid(row=0, column=1, sticky=tk.W, padx=(10, 0))

    def create_action_buttons(self):
        button_frame = ttk.Frame(self.main_frame)
        button_frame.grid(row=6, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(10, 0))

        self.process_button = ttk.Button(
            button_frame,
            text="Process PDF",
            command=self.start_processing,
            style="Action.TButton"
        )
        self.process_button.grid(row=0, column=0, sticky=tk.W)

        self.cancel_button = ttk.Button(
            button_frame,
            text="Cancel",
            command=self.cancel_processing,
            state="disabled"
        )
        self.cancel_button.grid(row=0, column=1, sticky=tk.W, padx=(10, 0))

        self.open_output_button = ttk.Button(
            button_frame,
            text="Open Output Folder",
            command=self.open_output_folder,
            state="disabled"
        )
        self.open_output_button.grid(row=0, column=2, sticky=tk.W, padx=(10, 0))

        button_frame.columnconfigure(3, weight=1)

        ttk.Button(
            button_frame,
            text="Exit",
            command=self.root.quit
        ).grid(row=0, column=4, sticky=tk.E)

    def create_menu(self):
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)

        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="Open PDF...", command=self.browse_file, accelerator="Ctrl+O")
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.root.quit, accelerator="Ctrl+Q")

        tools_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Tools", menu=tools_menu)
        tools_menu.add_command(label="Clear Log", command=self.clear_log)
        tools_menu.add_command(label="Save Log...", command=self.save_log)
        tools_menu.add_separator()
        tools_menu.add_command(label="Open Output Folder", command=self.open_output_folder)

        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Help", menu=help_menu)
        help_menu.add_command(label="Check for Updates", command=self.check_updates_manual)
        help_menu.add_separator()
        help_menu.add_command(label="About", command=self.show_about)

        self.root.bind("<Control-o>", lambda e: self.browse_file())
        self.root.bind("<Control-q>", lambda e: self.root.quit())

    # ────────────────────────────────────────────────────────────────────────────
    # EVENT HANDLERS
    # ────────────────────────────────────────────────────────────────────────────

    def browse_file(self):
        """Open file browser to select PDF file."""
        filename = filedialog.askopenfilename(
            title="Select PDF File",
            filetypes=[("PDF files", "*.pdf"), ("All files", "*.*")]
        )
        if filename:
            self.selected_file = filename
            self.file_path_var.set(filename)
            self.log_message(f"Selected file: {filename}")
            self.process_button.config(state="normal")

    def start_processing(self):
        if not self.selected_file:
            messagebox.showerror("Error", "Please select a PDF file first.")
            return

        if self.processing:
            messagebox.showwarning("Warning", "Processing is already in progress.")
            return

        if not os.path.exists(self.selected_file):
            messagebox.showerror("Error", "Selected file does not exist.")
            return

        # Update UI state
        self.processing = True
        self.process_button.config(state="disabled")
        self.cancel_button.config(state="normal")
        self.open_output_button.config(state="disabled")
        self.progress_bar.start()

        self.clear_log()
        self.log_message("Starting PDF processing...")

        # Start processing thread
        self.processing_thread = threading.Thread(
            target=self.process_pdf_thread,
            daemon=True
        )
        self.processing_thread.start()

    def process_pdf_thread(self):
        """Execute PDF processing in separate thread."""
        try:
            processor = VeetechProcessor(
                self.selected_file,
                progress_callback=self.update_progress_safe
            )
            result = processor.process()
            self.root.after(0, self.processing_complete, result)
        except Exception as e:
            error_msg = f"Processing failed: {str(e)}"
            self.logger.error(error_msg)
            self.logger.error(traceback.format_exc())
            self.root.after(0, self.processing_error, error_msg)

    def update_progress_safe(self, message: str):
        self.root.after(0, self.update_progress, message)

    def update_progress(self, message: str):
        """Update progress display."""
        self.status_var.set(message)
        self.log_message(message)
        self.root.update_idletasks()

    def processing_complete(self, result: ProcessingResult):
        """Handle successful processing completion."""
        self.processing = False
        self.progress_bar.stop()
        self.process_button.config(state="normal")
        self.cancel_button.config(state="disabled")
        self.open_output_button.config(state="normal")

        self.status_var.set("Processing complete!")
        self.log_message("=" * 50)
        self.log_message("PROCESSING RESULTS:")
        self.log_message(f"Total certificates: {result.total_chunks}")
        self.log_message(f"Successfully processed: {result.successful}")
        self.log_message(f"Failed: {result.failed}")

        if result.errors:
            self.log_message("\nERRORS ENCOUNTERED:")
            for chunk_path, start, end, error in result.errors:
                chunk_name = os.path.basename(chunk_path)
                self.log_message(f"- {chunk_name} (pages {start+1}-{end}): {error}")

        self.log_message(f"\nOutput directory: {result.output_directory}")
        self.log_message("=" * 50)

        success_rate = (result.successful / result.total_chunks) * 100 if result.total_chunks > 0 else 0
        if result.failed == 0:
            messagebox.showinfo(
                "Processing Complete",
                f"Successfully processed all {result.successful} certificates!\n\n"
                f"Output directory:\n{result.output_directory}"
            )
        else:
            messagebox.showwarning(
                "Processing Complete with Errors",
                f"Processed {result.successful}/{result.total_chunks} certificates successfully ({success_rate:.1f}%)\n\n"
                f"{result.failed} certificates failed to process.\n"
                f"Check the log for details.\n\n"
                f"Output directory:\n{result.output_directory}"
            )

        self.last_output_dir = result.output_directory

    def processing_error(self, error_msg: str):
        """Handle processing error."""
        self.processing = False
        self.progress_bar.stop()
        self.process_button.config(state="normal")
        self.cancel_button.config(state="disabled")
        self.status_var.set("Processing failed!")
        self.log_message(f"ERROR: {error_msg}")
        messagebox.showerror("Processing Error", error_msg)

    def cancel_processing(self):
        """Cancel ongoing processing."""
        if self.processing:
            self.processing = False
            self.progress_bar.stop()
            self.process_button.config(state="normal")
            self.cancel_button.config(state="disabled")
            self.status_var.set("Processing cancelled")
            self.log_message("Processing cancelled by user")

    def open_output_folder(self):
        """Open the output folder in Windows Explorer."""
        if hasattr(self, "last_output_dir") and os.path.exists(self.last_output_dir):
            os.startfile(self.last_output_dir)
        else:
            messagebox.showwarning("Warning", "No output folder available.")

    def clear_log(self):
        """Clear the log display."""
        self.log_text.config(state="normal")
        self.log_text.delete(1.0, tk.END)
        self.log_text.config(state="disabled")

    def save_log(self):
        """Save log content to file."""
        filename = filedialog.asksaveasfilename(
            title="Save Log File",
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
        )
        if filename:
            try:
                log_content = self.log_text.get(1.0, tk.END)
                with open(filename, "w", encoding="utf-8") as f:
                    f.write(log_content)
                messagebox.showinfo("Success", f"Log saved to:\n{filename}")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to save log:\n{str(e)}")

    def log_message(self, message: str):
        """Add message to log display."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        formatted_message = f"[{timestamp}] {message}\n"
        self.log_text.config(state="normal")
        self.log_text.insert(tk.END, formatted_message)
        self.log_text.see(tk.END)
        self.log_text.config(state="disabled")

    # ────────────────────────────────────────────────────────────────────────────
    # UPDATE MANAGEMENT (silent/manual checks)
    # ────────────────────────────────────────────────────────────────────────────

    def check_updates_silent(self):
        """Check for updates silently on startup."""
        def check_thread():
            update_info = self.update_manager.check_for_updates()
            if not update_info.get("error") and update_info.get("update_available"):
                self.root.after(0, lambda: self.show_update_notification(update_info))

        threading.Thread(target=check_thread, daemon=True).start()

    def check_updates_manual(self):
        """Manual “Check for Updates…” menu action."""
        self.update_manager.prompt_and_update()

    def show_update_notification(self, update_info: dict):
        """Show update notification popup."""
        result = messagebox.askyesno(
            "Update Available",
            f"A new version ({update_info['latest_version']}) is available!\n\n"
            f"Current version: {self.config.version}\n"
            f"New version: {update_info['latest_version']}\n\n"
            "Would you like to download and install the update?"
        )
        if result:
            self.download_and_install_update(update_info["download_url"])

    def download_and_install_update(self, download_url: str):
        """Download and install update."""
        def download_thread():
            try:
                update_file = self.update_manager.download_update(
                    download_url,
                    progress_callback=self.update_download_progress
                )
                success = self.update_manager.apply_update(update_file)
                self.root.after(0, lambda: self.update_download_complete(success))
            except Exception as e:
                error_msg = f"Update failed: {str(e)}"
                self.root.after(0, lambda: self.update_download_error(error_msg))

        self.log_message("Starting update download...")
        threading.Thread(target=download_thread, daemon=True).start()

    def update_download_progress(self, message: str):
        self.root.after(0, lambda: self.log_message(message))

    def update_download_complete(self, success: bool):
        if success:
            messagebox.showinfo(
                "Update Complete",
                "Update downloaded successfully!\nThe application will restart to apply the update."
            )
        else:
            messagebox.showerror(
                "Update Failed",
                "Failed to apply update. Please try again later."
            )

    def update_download_error(self, error_msg: str):
        self.log_message(f"Update error: {error_msg}")
        messagebox.showerror("Update Error", error_msg)

    # ────────────────────────────────────────────────────────────────────────────
    # HELP AND ABOUT
    # ────────────────────────────────────────────────────────────────────────────

    def show_about(self):
        about_text = f"""
{self.config.app_name}
Version {self.config.version}

Automated PDF certificate processing application with intelligent 
metadata extraction and file organization capabilities.

Features:
• Automatic OCR processing
• Certificate detection and splitting
• Metadata extraction (due dates, tags, serials)
• Intelligent file naming and organization
• Remote update management

© 2024 Veetech Solutions
        """.strip()
        messagebox.showinfo("About", about_text)

    # ────────────────────────────────────────────────────────────────────────────
    # APPLICATION LIFECYCLE
    # ────────────────────────────────────────────────────────────────────────────

    def run(self):
        """Start the application main loop."""
        self.logger.info(f"Starting {self.config.app_name} v{self.config.version}")
        self.center_window()
        try:
            self.root.mainloop()
        except KeyboardInterrupt:
            self.logger.info("Application interrupted by user")
        except Exception as e:
            self.logger.error(f"Application error: {e}")
            self.logger.error(traceback.format_exc())
        finally:
            self.logger.info("Application shutting down")

    def center_window(self):
        """Center the application window on screen."""
        self.root.update_idletasks()
        window_width = self.root.winfo_width()
        window_height = self.root.winfo_height()
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        x = (screen_width // 2) - (window_width // 2)
        y = (screen_height // 2) - (window_height // 2)
        self.root.geometry(f"{window_width}x{window_height}+{x}+{y}")
