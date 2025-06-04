# veetech_app/update_manager.py

import requests
import webbrowser
import re
import threading
import tkinter as tk
from tkinter import messagebox
from .config import AppConfig

class UpdateManager:
    """
    Manages checking for updates via GitHub Releases.
    """

    def __init__(self, config: AppConfig, root_window: tk.Tk = None):
        """
        :param config: AppConfig instance (holds version, app name, etc.)
        :param root_window: (optional) the Tk root, for threading-safe messageboxes.
        """
        self.config = config
        self.root = root_window
        # POINT THIS at your GitHub Releases "latest" API endpoint.
        self.github_api_latest = "https://api.github.com/repos/noelmathen/veetech-pdf-processor/releases/latest"

    @staticmethod
    def parse_version(tag: str) -> tuple[int, ...]:
        """
        Convert a version string like "v1.2.3" or "1.2.3" into a tuple of ints: (1, 2, 3).
        - Ignores any leading "v" or "V".
        - Splits on dots.
        """
        if tag.lower().startswith("v"):
            tag = tag[1:]
        parts = tag.split(".")
        # Convert each part to int if possible, else 0
        nums = []
        for p in parts:
            try:
                nums.append(int(p))
            except ValueError:
                nums.append(0)
        return tuple(nums)

    def check_for_updates(self) -> dict:
        """
        Check GitHub for the latest release. Returns a dict:
          {
            "update_available": True/False,
            "latest_version": "vX.Y.Z",
            "download_url": "https://github.com/.../SplitMe-X.Y.Z-Setup.exe",
            "error": None or "<error message>"
          }
        """
        try:
            resp = requests.get(self.github_api_latest, timeout=10)
            resp.raise_for_status()
            data = resp.json()

            # Example: "tag_name": "v1.2.3"
            latest_tag = data.get("tag_name", "")
            if not latest_tag:
                return {"update_available": False, "latest_version": None,
                        "download_url": None, "error": "No tag_name in response."}

            latest_ver_tuple = UpdateManager.parse_version(latest_tag)
            current_ver_tuple = UpdateManager.parse_version(self.config.version)

            if latest_ver_tuple > current_ver_tuple:
                # Find the Setup.exe asset
                assets = data.get("assets", [])
                download_url = None
                for asset in assets:
                    name = asset.get("name", "")
                    if name.lower().endswith("-setup.exe"):
                        download_url = asset.get("browser_download_url")
                        break

                if not download_url:
                    return {
                        "update_available": False,
                        "latest_version": latest_tag,
                        "download_url": None,
                        "error": "No Setup.exe asset found in release."
                    }

                return {
                    "update_available": True,
                    "latest_version": latest_tag,
                    "download_url": download_url,
                    "error": None
                }

            # No update needed
            return {"update_available": False, "latest_version": latest_tag,
                    "download_url": None, "error": None}

        except requests.RequestException as e:
            return {"update_available": False, "latest_version": None,
                    "download_url": None, "error": f"Network error: {e}"}
        except ValueError as e:
            # JSON parsing error
            return {"update_available": False, "latest_version": None,
                    "download_url": None, "error": f"Invalid JSON: {e}"}
        except Exception as e:
            return {"update_available": False, "latest_version": None,
                    "download_url": None, "error": str(e)}

    def prompt_and_update(self):
        """
        Perform the check in a background thread, then prompt the user if new version found.
        Must be called from the main thread (e.g. in response to a menu click).
        """
        def worker():
            result = self.check_for_updates()
            # Use root.after so the messagebox is shown on the main thread
            if self.root:
                self.root.after(0, lambda: self._show_result(result))
            else:
                # If no root was provided, show immediately (may block)
                self._show_result(result)

        threading.Thread(target=worker, daemon=True).start()

    def _show_result(self, result: dict):
        """
        Called on the main thread to display the appropriate dialog.
        """
        if result["error"]:
            messagebox.showerror("Update Check Failed", f"Error: {result['error']}")
            return

        if result["update_available"]:
            latest = result["latest_version"]
            url = result["download_url"]

            if messagebox.askyesno(
                "Update Available",
                f"A new version ({latest}) is available!\n"
                f"Your version: {self.config.version}\n\n"
                "Would you like to download it now?"
            ):
                webbrowser.open(url)
        else:
            messagebox.showinfo(
                "No Updates Found",
                f"You are running the latest version ({self.config.version})."
            )
