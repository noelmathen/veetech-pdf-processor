# veetech_app/file_organizer.py

import os
import re
import shutil
from pathlib import Path
from typing import Optional

class FileOrganizer:
    """Handles file organization and grouping operations."""

    @staticmethod
    def group_files_by_tag(output_dir: str, progress_callback=None) -> None:
        """Group PDF files into subfolders by base tag."""
        moved_count = 0
        pdf_files = [f for f in os.listdir(output_dir) if f.lower().endswith(".pdf")]

        for i, filename in enumerate(pdf_files):
            base_tag = FileOrganizer._extract_base_tag(filename)
            if not base_tag:
                continue
            dest_folder = Path(output_dir) / base_tag
            dest_folder.mkdir(exist_ok=True)

            src_path = Path(output_dir) / filename
            dst_path = dest_folder / filename
            shutil.move(str(src_path), str(dst_path))
            moved_count += 1

            if progress_callback:
                progress_callback(f"Organizing files... {i+1}/{len(pdf_files)}")

    @staticmethod
    def _extract_base_tag(filename: str) -> Optional[str]:
        """Extract base tag from filename for grouping."""
        parts = filename.split("_", 2)
        if len(parts) < 2:
            return None
        id_str = parts[1]
        match = re.match(r"^([A-Za-z]{2,5})-(\d+)", id_str)
        if match:
            return f"{match[1]}-{match[2]}"
        return None
