# veetech_app/update_manager.py
"""
Auto-update via GitHub Releases
✓ Works for public repos without auth
✓ For private repos set GITHUB_TOKEN env-var
✓ Expects an asset named  SplitMe-Setup-<ver>.exe  OR  SplitMe.exe
   (whichever you uploaded to the release)
"""

import os, sys, json, tempfile, subprocess, requests
from pathlib import Path
from packaging.version import Version, InvalidVersion     # pip install packaging
from .config import AppConfig
from .logger import AppLogger
from tkinter import messagebox

# ──────────────────────────────────────────────────────────────────────────────
OWNER  = "noelmathen"
REPO   = "veetech-pdf-processor"                       # ← repo name
APP_EXE_NAME = "SplitMe.exe"             # how your exe is called after install
ASSET_PREFIX = "SplitMe-Setup-"          # asset must start with this
# ──────────────────────────────────────────────────────────────────────────────

LATEST_API_URL = f"https://api.github.com/repos/{OWNER}/{REPO}/releases/latest"
HEADERS = {
    "Accept": "application/vnd.github+json",
    "User-Agent": f"{REPO} Updater",
}
if token := os.getenv("GITHUB_TOKEN"):   # needed only for private repos
    HEADERS["Authorization"] = f"Bearer {token}"

class UpdateManager:
    """Check GitHub releases, download installer, run silently"""

    def __init__(self, cfg: AppConfig):
        self.cfg = cfg
        self.log = AppLogger.get_logger(__name__)

    # ── public API ────────────────────────────────────────────────────────────
    def check_for_updates(self):
        """Return dict: {'update_available':bool, 'latest_version':str, 'download_url':str}"""
        try:
            r = requests.get(LATEST_API_URL, headers=HEADERS, timeout=10)
            r.raise_for_status()
            data = r.json()
            latest_tag = data["tag_name"].lstrip("v")               # e.g. '1.2.0'
            self.log.info(f"Latest GitHub tag: {latest_tag}")
            if self._is_newer(latest_tag, self.cfg.version):
                asset_url = self._find_asset_url(data["assets"], latest_tag)
                if asset_url:
                    return {
                        "update_available": True,
                        "latest_version": latest_tag,
                        "download_url": asset_url,
                    }
            return {"update_available": False}
        except Exception as err:
            self.log.error(f"Update check failed: {err}")
            return {"error": str(err)}

    def download_update(self, url: str, progress_cb=None) -> Path:
        """Stream-download installer → returns local Path"""
        resp = requests.get(url, stream=True, headers=HEADERS, timeout=60)
        resp.raise_for_status()
        total = int(resp.headers.get("content-length", 0))
        tmp = Path(tempfile.gettempdir()) / Path(url).name
        with tmp.open("wb") as f:
            dl = 0
            for chunk in resp.iter_content(chunk_size=8192):
                f.write(chunk)
                dl += len(chunk)
                if progress_cb and total:
                    progress_cb(f"Downloading update… {dl*100/total:4.1f}%")
        return tmp

    def apply_update(self, installer: Path) -> None:
        """
        Launch the Inno-Setup installer silently and exit current app.
        The INI flag /VERYSILENT auto-updates in place.
        """
        try:
            self.log.info(f"Running installer {installer}")
            # Inno switches: /VERYSILENT /NORESTART /SUPPRESSMSGBOXES
            subprocess.Popen([str(installer), "/VERYSILENT", "/NORESTART"])
            sys.exit(0)         # quit current app → installer replaces files
        except Exception as e:
            self.log.error(f"Failed to run installer: {e}")

    # ── helpers ───────────────────────────────────────────────────────────────
    def _is_newer(self, latest: str, current: str) -> bool:
        try:
            return Version(latest) > Version(current)
        except InvalidVersion:
            return latest != current    # fallback: simple string diff

    def _find_asset_url(self, assets, latest_tag):
        """
        Pick first asset whose name starts with ASSET_PREFIX
        Falls back to 'SplitMe.exe' if you ship the raw exe instead of installer
        """
        # Prioritize the installer asset (SplitMe-Setup-...)
        for a in assets:
            if a["name"].startswith(ASSET_PREFIX): # This is your desired installer
                self.log.info(f"Update asset: {a['name']}")
                return a["browser_download_url"]
        
        # Fallback to the raw exe if no installer is found (less ideal for updates)
        for a in assets:
            if a["name"] == APP_EXE_NAME:
                self.log.info(f"Update asset: {a['name']} (fallback to raw exe)")
                return a["browser_download_url"]

        self.log.warning("No matching asset found in release.")
        return None

    def check_updates_manual(self):
        info = self.update_manager.check_for_updates()
        if info.get("error"):
            messagebox.showerror("Update Error", info["error"])
        elif info["update_available"]:
            if messagebox.askyesno("Update Available",
                                f"SplitMe {info['latest_version']} is out!\n"
                                "Download and install now?"):
                self.download_and_install_update(info["download_url"])
        else:
            messagebox.showinfo("Up to date",
                                f"You already have SplitMe {self.config.version}.")
