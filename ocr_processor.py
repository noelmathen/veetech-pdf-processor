# veetech_app/ocr_processor.py

import re
import ocrmypdf

class OCRProcessor:
    """Handles OCR operations and text correction."""

    @staticmethod
    def perform_ocr(input_path: str, output_path: str, progress_callback=None) -> None:
        """Run OCR on input PDF and save searchable PDF to output path."""
        if progress_callback:
            progress_callback("Starting OCR processing...")
        ocrmypdf.ocr(
            input_file=input_path,
            output_file=output_path,
            force_ocr=True,
            use_threads=True,
            skip_text=False,
            deskew=True,
            language="eng",
        )
        if progress_callback:
            progress_callback("OCR processing complete")

    @staticmethod
    def correct_ocr_errors(text: str) -> str:
        """Apply regex fixes for common OCR misreads."""
        corrections = [
            (r"KTOO(\d+)", r"KT00\1"),
            (r"(\b[A-Za-z0-9]+)-([A-Za-z0-9]+)-5-([A-Za-z0-9]+)-([A-Za-z0-9]+\b)",
             r"\1-\2-S-\3-\4"),
            (r"TEST\s*CERTTFICATE", "TEST CERTIFICATE"),
        ]
        for pattern, replacement in corrections:
            text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)

        multiline_fixes = {
            r"CERTIFICATE[\s\r\n]+OF[\s\r\n]+CALIBRATION": "CERTIFICATE OF CALIBRATION",
            r"CERTIFICATE[\s\r\n]+OF[\s\r\n]+TEST": "CERTIFICATE OF TEST",
            r"CERTIFICATE[\s\r\n]+OF[\s\r\n]+INSPECTION": "CERTIFICATE OF INSPECTION",
        }
        for pattern, replacement in multiline_fixes.items():
            text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)

        # Fix tag‐format (O vs 0, etc.)
        text = re.sub(r"\b[A-Z]{2,5}(?:[-/][A-Za-z0-9]{1,10})+\b",
                      OCRProcessor._fix_tag_format, text)
        return text

    @staticmethod
    def _fix_tag_format(match: re.Match) -> str:
        """Fix O/0 confusion in tag numbers."""
        tag = match.group(0)
        parts = re.split(r"([-\/])", tag)
        rebuilt = []
        for part in parts:
            if part in "-/":
                rebuilt.append(part)
            elif any(ch.isdigit() for ch in part) and "O" in part:
                rebuilt.append(part.replace("O", "0"))
            else:
                rebuilt.append(part)
        return "".join(rebuilt)
