# veetech_app/main.py

import logging
import traceback
import tempfile
import shutil
import os
from tkinter import messagebox
import tkinter as tk  # only needed if error happens before Tk is created
from .gui import VeetechDesktopApp
from .logger import AppLogger

def main():
    """Application entry point."""
    try:
        app = VeetechDesktopApp()
        app.run()

    except Exception as e:
        logging.error(f"Critical application error: {e}")
        logging.error(traceback.format_exc())
        try:
            messagebox.showerror(
                "Critical Error",
                f"A critical error occurred:\n{str(e)}\n\n"
                f"Please check the log file for details."
            )
        except:
            print(f"Critical error: {e}")

    finally:
        # Cleanup any leftover temp dirs
        temp_dir = tempfile.gettempdir()
        for item in os.listdir(temp_dir):
            if item.startswith("veetech_"):
                item_path = os.path.join(temp_dir, item)
                try:
                    if os.path.isdir(item_path):
                        shutil.rmtree(item_path)
                    else:
                        os.remove(item_path)
                except:
                    pass

if __name__ == "__main__":
    main()
