# veetech_app/date_formatter.py

from datetime import datetime
from typing import Optional

class DateFormatter:
    """Handles date formatting operations."""

    @staticmethod
    def format_date(date_str: str) -> Optional[str]:
        """Normalize various date formats to YYYYMMDD."""
        if not date_str:
            return None
        date_formats = ("%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y")
        for fmt in date_formats:
            try:
                return datetime.strptime(date_str, fmt).strftime("%Y%m%d")
            except ValueError:
                continue
        return None
