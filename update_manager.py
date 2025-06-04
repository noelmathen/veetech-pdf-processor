# veetech_app/update_manager.py

import os
import sys
import tempfile
import requests
from typing import Dict, Any
from .config import AppConfig
from .logger import AppLogger

class UpdateManager:
    """Manages application updates and remote management."""

    def __init__(self, config: AppConfig):
        self.config = config
        self.logger = AppLogger.get_logger(__name__)

    def check_for_updates(self) -> Dict[str, Any]:
        """Check for available updates."""
        try:
            response = requests.get(
                f"{self.config.update_server_url}/check-update",
                params={"current_version": self.config.version},
                timeout=10
            )
            if response.status_code == 200:
                return response.json()
            else:
                return {"error": f"Server returned {response.status_code}"}
        except requests.RequestException as e:
            self.logger.error(f"Update check failed: {e}")
            return {"error": str(e)}

    def download_update(self, update_url: str, progress_callback=None) -> str:
        """Download update file."""
        try:
            response = requests.get(update_url, stream=True)
            response.raise_for_status()

            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".exe")
            total_size = int(response.headers.get('content-length', 0))
            downloaded = 0

            with temp_file as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
                    downloaded += len(chunk)
                    if progress_callback and total_size > 0:
                        progress = (downloaded / total_size) * 100
                        progress_callback(f"Downloading update... {progress:.1f}%")
            return temp_file.name
        except Exception as e:
            self.logger.error(f"Update download failed: {e}")
            raise

    def apply_update(self, update_file: str) -> bool:
        """Apply downloaded update."""
        try:
            update_script = self._create_update_script(update_file)
            os.startfile(update_script)
            return True
        except Exception as e:
            self.logger.error(f"Update application failed: {e}")
            return False

    def _create_update_script(self, update_file: str) -> str:
        """Create Windows batch script for update."""
        script_content = f"""@echo off
echo Updating Veetech PDF Processor...
timeout /t 3 /nobreak
taskkill /f /im VeetechPDFProcessor.exe 2>nul
copy "{update_file}" "{sys.executable}" /y
del "{update_file}"
start "" "{sys.executable}"
del "%~f0"
"""
        script_path = "update_veetech.bat"
        with open(script_path, 'w') as f:
            f.write(script_content)
        return script_path
