# veetech_app/metadata_extractor.py

import re
from typing import List, Optional
from .ocr_processor import OCRProcessor
from .date_formatter import DateFormatter
from .config import AppConfig
from dataclasses import dataclass, asdict


class PatternConfig:
    """Centralized regex patterns for field extraction."""

    TAG_PATTERNS = [
        r"Tag No\.?[:+\s]*([A-Za-z0-9\-\/]+)",
        r"Tag Number[:+\s]*([A-Za-z0-9\-\/]+)",
    ]
    SERIAL_PATTERNS = [
        r"Serial No\.?[:|+\s]*([A-Za-z0-9\-]+)",
        r"Serial number[:|+\s]*([A-Za-z0-9\-]+)",
    ]
    UNIT_PATTERNS = [
        r"Unit ID[:\s]*([A-Za-z0-9\-]+)",
    ]
    DUE_PATTERNS = [
        r"Recommended Due Date[^\d]*(\d{2}/\d{2}/\d{4})",
        r"Calibration Due Date[^\d]*(\d{2}/\d{2}/\d{4})",
        r"Expiry Date[^\d]*(\d{2}/\d{2}/\d{4})",
    ]
    CERTIFICATE_PATTERNS = [
        r"(TEST CERTIFICATE|TEST CERTIFICATH|TEST CERTIFICA'|CERTIFICATE OF CALIBRATION)"
    ]
    CERTIFICATE_TYPE_MAP = {
        "TEST CERTIFICATE": "TestCertificate",
        "TEST CERTIFICATH": "TestCertificate",
        "TEST CERTIFICA'": "TestCertificate",
        "CERTIFICATE OF CALIBRATION": "CalibrationCertificate"
    }

@dataclass
class CertificateMetadata:
    """Container for extracted certificate metadata."""
    due_date: str
    tag: Optional[str] = None
    serial: Optional[str] = None
    unit_id: Optional[str] = None
    certificate_type: str = ""

class MetadataExtractor:
    """Extracts metadata fields from certificate text."""

    @staticmethod
    def extract_field(patterns: List[str], text: str, field_name: str) -> Optional[str]:
        """Search text using regex patterns and return first match."""
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                value = match.group(1).strip()
                if field_name.lower() == "tag number":
                    value = MetadataExtractor._process_tag_value(value)
                if value.upper() in ("N/A", "NA"):
                    return None
                return value
        return None

    @staticmethod
    def _process_tag_value(value: str) -> str:
        """Process and correct tag number values."""
        value = OCRProcessor.correct_ocr_errors(value)
        # If O vs 0 confusion
        if match := re.match(r"^([A-Za-z]{2,5})O(\d+)$", value):
            return f"{match[1]}-0{match[2]}"
        # If no hyphen but alphanumeric
        if "-" not in value and re.match(r"^[A-Za-z]{2,5}\d+$", value):
            letters, numbers = re.match(r"^([A-Za-z]{2,5})(\d+)$", value).groups()
            return f"{letters}-{numbers}"
        return value

    @staticmethod
    def extract_due_date(text: str) -> str:
        """Extract and format due date."""
        raw_date = MetadataExtractor.extract_field(PatternConfig.DUE_PATTERNS, text, "Due Date")
        due_date = DateFormatter.format_date(raw_date)
        if not due_date:
            all_dates = re.findall(r"\d{2}/\d{2}/\d{4}", text)
            if len(all_dates) >= 5:
                due_date = DateFormatter.format_date(all_dates[4])
        if not due_date:
            raise ValueError("Due date not found")
        return due_date

    @staticmethod
    def extract_certificate_type(text: str) -> str:
        """Extract and normalize certificate type."""
        raw_type = MetadataExtractor.extract_field(PatternConfig.CERTIFICATE_PATTERNS,
                                                  text, "Certificate Type")
        if not raw_type:
            raise ValueError("Certificate type not found")
        normalized = PatternConfig.CERTIFICATE_TYPE_MAP.get(
            raw_type.upper(), raw_type.title().replace(" ", "")
        )
        return normalized

    @classmethod
    def extract_all_metadata(cls, text: str) -> CertificateMetadata:
        """Extract all metadata from certificate text."""
        return CertificateMetadata(
            due_date=cls.extract_due_date(text),
            tag=cls.extract_field(PatternConfig.TAG_PATTERNS, text, "Tag Number"),
            serial=cls.extract_field(PatternConfig.SERIAL_PATTERNS, text, "Serial Number"),
            unit_id=cls.extract_field(PatternConfig.UNIT_PATTERNS, text, "Unit ID"),
            certificate_type=cls.extract_certificate_type(text),
        )
