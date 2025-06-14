# veetech_app/text_extractor.py

import fitz  # PyMuPDF
from .ocr_processor import OCRProcessor

class TextExtractor:
    """Handles text extraction from PDFs."""

    @staticmethod
    def extract_text_from_pdf(pdf_path: str) -> str:
        """Extract and correct text from PDF."""
        doc = fitz.open(pdf_path)
        try:
            raw_text = "".join(page.get_text() for page in doc)
            if not raw_text.strip():
                raise ValueError("No text extracted from PDF")
            # print(f"\n\nText: {raw_text[:3000]}...\n\n")  # Debug output
            return OCRProcessor.correct_ocr_errors(raw_text)
        finally:
            doc.close()
