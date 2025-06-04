# veetech_app/processor.py

import os
import shutil
import tempfile
import traceback
from pathlib import Path
from typing import List, Tuple, Set
from .ocr_processor import OCRProcessor
from .text_extractor import TextExtractor
from .metadata_extractor import MetadataExtractor, CertificateMetadata
from .filename_generator import FilenameGenerator
from .pdf_splitter import PDFSplitter
from .file_organizer import FileOrganizer
from .logger import AppLogger
from dataclasses import dataclass
from typing import List, Tuple, Any

@dataclass
class ProcessingResult:
    """Container for processing results."""
    total_chunks: int
    successful: int
    failed: int
    errors: List[Tuple[str, int, int, str]]
    output_directory: str = ""

class VeetechProcessor:
    """Main processing pipeline coordinator."""

    def __init__(self, input_file: str, progress_callback=None):
        self.input_file = input_file
        self.base_name = Path(input_file).stem
        self.progress_callback = progress_callback
        self.logger = AppLogger.get_logger(__name__)

        # Setup paths
        self.ocr_output = str(Path(input_file).parent / f"{self.base_name}_OCR.pdf")
        self.split_dir = tempfile.mkdtemp(prefix="veetech_split_")
        self.output_dir = str(Path(input_file).parent / f"{self.base_name}_processed")

        # Prepare output directory
        if Path(self.output_dir).exists():
            shutil.rmtree(self.output_dir)
        Path(self.output_dir).mkdir(exist_ok=True)

    def process(self) -> ProcessingResult:
        """Execute the complete processing pipeline."""
        try:
            # Step 1: OCR
            self._update_progress("Starting OCR processing...")
            OCRProcessor.perform_ocr(self.input_file, self.ocr_output, self.progress_callback)

            # Step 2: Split PDF
            self._update_progress("Splitting PDF into certificates...")
            chunks = PDFSplitter.split_by_certificate_markers(
                self.ocr_output, self.split_dir, self.progress_callback
            )

            # Step 3: Process chunks
            self._update_progress("Processing certificate chunks...")
            result = self._process_chunks_step(chunks)

            # Step 4: Organize files
            if self.auto_organize():
                self._update_progress("Organizing files...")
                FileOrganizer.group_files_by_tag(self.output_dir, self.progress_callback)

            result.output_directory = self.output_dir
            self._update_progress("Processing complete!")
            return result

        except Exception as e:
            self.logger.error(f"Pipeline failed: {e}")
            self._update_progress(f"Error: {str(e)}")
            raise

        finally:
            # Cleanup temporary files
            if Path(self.split_dir).exists():
                shutil.rmtree(self.split_dir)
            if Path(self.ocr_output).exists():
                os.remove(self.ocr_output)

    def _update_progress(self, message: str):
        """Update progress callback if available."""
        if self.progress_callback:
            self.progress_callback(message)
        self.logger.info(message)

    def _process_chunks_step(self, chunks: List[Tuple[str, int, int]]) -> ProcessingResult:
        successful = 0
        failed = 0
        errors = []
        existing_filenames: Set[str] = set()

        for i, (chunk_path, start, end) in enumerate(chunks):
            try:
                self._update_progress(f"Processing certificate {i+1}/{len(chunks)}...")

                text = TextExtractor.extract_text_from_pdf(chunk_path)
                metadata = MetadataExtractor.extract_all_metadata(text)
                filename = self._generate_unique_filename(metadata, existing_filenames)
                existing_filenames.add(filename)

                dest_path = Path(self.output_dir) / filename
                shutil.move(chunk_path, str(dest_path))
                successful += 1

            except Exception as e:
                failed += 1
                error_info = (chunk_path, start, end, str(e))
                errors.append(error_info)
                self.logger.error(f"Failed on {Path(chunk_path).name} "
                                  f"(pages {start+1}–{end}): {e}")
                self._save_failed_chunk(chunk_path, start, end)

        return ProcessingResult(
            total_chunks=len(chunks),
            successful=successful,
            failed=failed,
            errors=errors
        )

    def _generate_unique_filename(self, metadata: CertificateMetadata,
                                  existing_files: Set[str]) -> str:
        filename = FilenameGenerator.create_filename(metadata, force_serial=False)
        if filename in existing_files:
            filename = FilenameGenerator.create_filename(metadata, force_serial=True)
        return filename

    def _save_failed_chunk(self, chunk_path: str, start: int, end: int) -> None:
        base_name = Path(chunk_path).stem
        failed_filename = f"{base_name}_pages_{start+1}-{end}.pdf"
        dest_path = Path(self.output_dir) / failed_filename
        shutil.move(chunk_path, str(dest_path))

    def auto_organize(self) -> bool:
        return True  # or read from a setting if you want this toggleable
