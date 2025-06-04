# veetech_app/pdf_splitter.py

import os
import re
from pathlib import Path
from typing import List, Tuple
import fitz  # PyMuPDF
from PyPDF2 import PdfReader, PdfWriter

class PDFSplitter:
    """Handles PDF splitting operations."""

    @staticmethod
    def split_by_certificate_markers(pdf_path: str, output_dir: str,
                                     progress_callback=None) -> List[Tuple[str,int,int]]:
        """Split PDF into certificate chunks based on 'Recommended Due Date' markers."""
        fitz_doc = fitz.open(pdf_path)
        reader = PdfReader(pdf_path)
        total_pages = len(fitz_doc)
        base_name = Path(pdf_path).stem

        Path(output_dir).mkdir(parents=True, exist_ok=True)
        if progress_callback:
            progress_callback(f"Analyzing {total_pages} pages for certificate markers...")

        try:
            start_pages = PDFSplitter._find_certificate_start_pages(fitz_doc, total_pages)
            if progress_callback:
                progress_callback(f"Found {len(start_pages)} certificates, splitting...")

            chunks = []
            for idx, start in enumerate(start_pages, start=1):
                end = start_pages[idx] if idx < len(start_pages) else total_pages
                chunk_path = PDFSplitter._create_chunk(reader, start, end, output_dir, base_name, idx)
                chunks.append((chunk_path, start, end))
                if progress_callback:
                    progress_callback(f"Created certificate chunk {idx}/{len(start_pages)}")
            return chunks
        finally:
            fitz_doc.close()

    @staticmethod
    def _find_certificate_start_pages(fitz_doc, total_pages: int) -> List[int]:
        """Find pages that start new certificates."""
        start_pages = [
            i for i in range(total_pages)
            if re.search(r"Recommended Due Date", fitz_doc[i].get_text(), re.IGNORECASE)
        ]
        if not start_pages:
            start_pages = [0]
        if start_pages[0] != 0:
            start_pages.insert(0, 0)
        return start_pages

    @staticmethod
    def _create_chunk(reader: PdfReader, start: int, end: int,
                      output_dir: str, base_name: str, chunk_idx: int) -> str:
        """Create a PDF chunk from page range."""
        writer = PdfWriter()
        for page_num in range(start, end):
            writer.add_page(reader.pages[page_num])
        chunk_path = os.path.join(output_dir, f"{base_name}_cert_{chunk_idx}.pdf")
        with open(chunk_path, "wb") as f:
            writer.write(f)
        return chunk_path
