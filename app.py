#!/usr/bin/env python3

"""
Veetech PDF Desktop Application
A Windows desktop application for automated PDF certificate processing with remote management capabilities.
"""

import os
import sys
import json
import zipfile
import requests
import threading
import tempfile
import shutil
import logging
import traceback
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple, Dict, Any, Callable
from dataclasses import dataclass, asdict
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import webbrowser

# Core processing imports (from the refactored code)
import fitz  # PyMuPDF
import ocrmypdf
from PyPDF2 import PdfReader, PdfWriter
import re


# ===============================================================================
# APPLICATION CONFIGURATION
# ===============================================================================

@dataclass
class AppConfig:
    """Application configuration settings."""
    app_name: str = "Veetech PDF Processor"
    version: str = "1.0.0"
    update_server_url: str = "https://your-update-server.com/api"
    config_file: str = "veetech_config.json"
    log_file: str = "veetech_app.log"
    temp_dir: str = "veetech_temp"
    auto_check_updates: bool = True
    save_logs: bool = True


# ===============================================================================
# CORE PROCESSING CLASSES (from refactored code)
# ===============================================================================

@dataclass
class CertificateMetadata:
    """Container for extracted certificate metadata."""
    due_date: str
    tag: Optional[str] = None
    serial: Optional[str] = None
    unit_id: Optional[str] = None
    certificate_type: str = ""


@dataclass
class ProcessingResult:
    """Container for processing results."""
    total_chunks: int
    successful: int
    failed: int
    errors: List[Tuple[str, int, int, str]]
    output_directory: str = ""


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


# ===============================================================================
# LOGGING SETUP
# ===============================================================================

class AppLogger:
    """Application logging manager."""
    
    def __init__(self, config: AppConfig):
        self.config = config
        self.setup_logging()
    
    def setup_logging(self):
        """Configure application logging."""
        log_format = "%(asctime)s [%(levelname)s] %(message)s"
        date_format = "%Y-%m-%d %H:%M:%S"
        
        # Configure root logger
        logging.basicConfig(
            level=logging.INFO,
            format=log_format,
            datefmt=date_format,
            handlers=[]
        )
        
        logger = logging.getLogger()
        
        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(logging.Formatter(log_format, date_format))
        logger.addHandler(console_handler)
        
        # File handler (if enabled)
        if self.config.save_logs:
            file_handler = logging.FileHandler(self.config.log_file)
            file_handler.setFormatter(logging.Formatter(log_format, date_format))
            logger.addHandler(file_handler)
    
    @staticmethod
    def get_logger(name: str = __name__) -> logging.Logger:
        """Get logger instance."""
        return logging.getLogger(name)


# ===============================================================================
# CORE PROCESSING CLASSES (CONDENSED FROM REFACTORED CODE)
# ===============================================================================

class OCRProcessor:
    """Handles OCR operations and text correction."""
    
    @staticmethod
    def perform_ocr(input_path: str, output_path: str, progress_callback: Callable = None) -> None:
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
            language="eng"
        )
        
        if progress_callback:
            progress_callback("OCR processing complete")
    
    @staticmethod
    def correct_ocr_errors(text: str) -> str:
        """Apply regex fixes for common OCR misreads."""
        corrections = [
            (r"KTOO(\d+)", r"KT00\1"),
            (r"(\b[A-Za-z0-9]+)-([A-Za-z0-9]+)-5-([A-Za-z0-9]+)-([A-Za-z0-9]+\b)", r"\1-\2-S-\3-\4"),
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
        
        text = re.sub(r"\b[A-Z]{2,5}(?:[-/][A-Za-z0-9]{1,10})+\b", OCRProcessor._fix_tag_format, text)
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
            return OCRProcessor.correct_ocr_errors(raw_text)
        finally:
            doc.close()


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
        
        if match := re.match(r"^([A-Za-z]{2,5})O(\d+)$", value):
            return f"{match[1]}-0{match[2]}"
        
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
        raw_type = MetadataExtractor.extract_field(PatternConfig.CERTIFICATE_PATTERNS, text, "Certificate Type")
        
        if not raw_type:
            raise ValueError("Certificate type not found")
        
        normalized = PatternConfig.CERTIFICATE_TYPE_MAP.get(raw_type.upper(), raw_type.title().replace(" ", ""))
        return normalized
    
    @classmethod
    def extract_all_metadata(cls, text: str) -> CertificateMetadata:
        """Extract all metadata from certificate text."""
        return CertificateMetadata(
            due_date=cls.extract_due_date(text),
            tag=cls.extract_field(PatternConfig.TAG_PATTERNS, text, "Tag Number"),
            serial=cls.extract_field(PatternConfig.SERIAL_PATTERNS, text, "Serial Number"),
            unit_id=cls.extract_field(PatternConfig.UNIT_PATTERNS, text, "Unit ID"),
            certificate_type=cls.extract_certificate_type(text)
        )


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


class FilenameGenerator:
    """Generates standardized filenames for certificates."""
    
    @staticmethod
    def create_filename(metadata: CertificateMetadata, force_serial: bool = False) -> str:
        """Generate filename from metadata."""
        core_id = FilenameGenerator._build_core_id(metadata, force_serial)
        filename = f"{metadata.due_date}_{core_id.replace(' ', '-')}_{metadata.certificate_type}.pdf"
        return filename.replace("/", "-")
    
    @staticmethod
    def _build_core_id(metadata: CertificateMetadata, force_serial: bool) -> str:
        """Build the core identifier part of the filename."""
        if not force_serial:
            return FilenameGenerator._build_standard_core_id(metadata)
        else:
            return FilenameGenerator._build_serial_based_core_id(metadata)
    
    @staticmethod
    def _build_standard_core_id(metadata: CertificateMetadata) -> str:
        """Build standard core ID (unit_tag > tag > serial)."""
        if metadata.unit_id:
            return f"{metadata.unit_id}_{metadata.tag}" if metadata.tag else metadata.unit_id
        elif metadata.tag:
            return metadata.tag
        elif metadata.serial:
            return metadata.serial
        else:
            raise ValueError("No ID (tag/unit/serial) found")
    
    @staticmethod
    def _build_serial_based_core_id(metadata: CertificateMetadata) -> str:
        """Build serial-based core ID for collision resolution."""
        core = ""
        
        if metadata.serial and metadata.tag:
            if metadata.serial.startswith(metadata.tag + "-"):
                core = metadata.serial
            else:
                core = f"{metadata.tag}_{metadata.serial}"
        elif metadata.serial:
            core = metadata.serial
        elif metadata.tag:
            core = metadata.tag
        elif metadata.unit_id:
            core = metadata.unit_id
        else:
            raise ValueError("No ID (tag/unit/serial) found")
        
        if metadata.unit_id:
            core = f"{metadata.unit_id}_{core}"
        
        return core


class PDFSplitter:
    """Handles PDF splitting operations."""
    
    @staticmethod
    def split_by_certificate_markers(pdf_path: str, output_dir: str, 
                                   progress_callback: Callable = None) -> List[Tuple[str, int, int]]:
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


class FileOrganizer:
    """Handles file organization and grouping operations."""
    
    @staticmethod
    def group_files_by_tag(output_dir: str, progress_callback: Callable = None) -> None:
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


# ===============================================================================
# UPDATE MANAGER
# ===============================================================================

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
    
    def download_update(self, update_url: str, progress_callback: Callable = None) -> str:
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
            # Create update script
            update_script = self._create_update_script(update_file)
            
            # Launch update script and exit
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


# ===============================================================================
# MAIN PROCESSING PIPELINE
# ===============================================================================

class VeetechProcessor:
    """Main processing pipeline coordinator."""
    
    def __init__(self, input_file: str, progress_callback: Callable = None):
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
            self._perform_ocr_step()
            
            # Step 2: Split PDF
            self._update_progress("Splitting PDF into certificates...")
            chunks = self._split_pdf_step()
            
            # Step 3: Process chunks
            self._update_progress("Processing certificate chunks...")
            result = self._process_chunks_step(chunks)
            
            # Step 4: Organize files
            self._update_progress("Organizing files...")
            self._organize_files_step()
            
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
            
            # Clean up OCR file
            if Path(self.ocr_output).exists():
                os.remove(self.ocr_output)
    
    def _update_progress(self, message: str):
        """Update progress callback if available."""
        if self.progress_callback:
            self.progress_callback(message)
        self.logger.info(message)
    
    def _perform_ocr_step(self) -> None:
        """Execute OCR processing step."""
        OCRProcessor.perform_ocr(self.input_file, self.ocr_output, self.progress_callback)
    
    def _split_pdf_step(self) -> List[Tuple[str, int, int]]:
        """Execute PDF splitting step."""
        return PDFSplitter.split_by_certificate_markers(
            self.ocr_output, self.split_dir, self.progress_callback
        )
    
    def _process_chunks_step(self, chunks: List[Tuple[str, int, int]]) -> ProcessingResult:
        """Execute chunk processing step."""
        successful = 0
        failed = 0
        errors = []
        existing_filenames = set()
        
        for i, (chunk_path, start, end) in enumerate(chunks):
            try:
                self._update_progress(f"Processing certificate {i+1}/{len(chunks)}...")
                
                # Extract text and metadata
                text = TextExtractor.extract_text_from_pdf(chunk_path)
                metadata = MetadataExtractor.extract_all_metadata(text)
                
                # Generate filename with collision handling
                filename = self._generate_unique_filename(metadata, existing_filenames)
                existing_filenames.add(filename)
                
                # Move file to final location
                dest_path = Path(self.output_dir) / filename
                shutil.move(chunk_path, str(dest_path))
                
                successful += 1
            
            except Exception as e:
                failed += 1
                error_info = (chunk_path, start, end, str(e))
                errors.append(error_info)
                
                self.logger.error(f"Failed on {Path(chunk_path).name} (pages {start+1}–{end}): {e}")
                self._save_failed_chunk(chunk_path, start, end)
        
        return ProcessingResult(
            total_chunks=len(chunks),
            successful=successful,
            failed=failed,
            errors=errors
        )
    
    def _generate_unique_filename(self, metadata: CertificateMetadata, existing_files: set) -> str:
        """Generate unique filename with collision handling."""
        filename = FilenameGenerator.create_filename(metadata, force_serial=False)
        
        if filename in existing_files:
            filename = FilenameGenerator.create_filename(metadata, force_serial=True)
        
        return filename
    
    def _save_failed_chunk(self, chunk_path: str, start: int, end: int) -> None:
        """Save problematic chunk with descriptive filename."""
        base_name = Path(chunk_path).stem
        failed_filename = f"{base_name}_pages_{start+1}-{end}.pdf"
        dest_path = Path(self.output_dir) / failed_filename
        
        shutil.move(chunk_path, str(dest_path))
    
    def _organize_files_step(self) -> None:
        """Execute file organization step."""
        FileOrganizer.group_files_by_tag(self.output_dir, self.progress_callback)


# ===============================================================================
# DESKTOP APPLICATION GUI
# ===============================================================================

class VeetechDesktopApp:
    """Main desktop application class."""
    
    def __init__(self):
        self.config = AppConfig()
        self.logger_manager = AppLogger(self.config)
        self.logger = AppLogger.get_logger(__name__)
        self.update_manager = UpdateManager(self.config)
        
        # Application state
        self.selected_file = None
        self.processing = False
        
        # Setup GUI
        self.setup_gui()
        
        # Check for updates on startup
        if self.config.auto_check_updates:
            self.check_updates_silent()
    
    def setup_gui(self):
        """Setup the main GUI."""
        self.root = tk.Tk()
        self.root.title(f"{self.config.app_name} v{self.config.version}")
        self.root.geometry("800x600")
        self.root.resizable(True, True)
        
        # Set icon (if available)
        try:
            self.root.iconbitmap("veetech_icon.ico")
        except:
            pass
        
        # Setup styles
        self.setup_styles()
        
        # Create main frame
        self.main_frame = ttk.Frame(self.root, padding="20")
        self.main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Configure grid weights
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        self.main_frame.columnconfigure(1, weight=1)
        
        # Create GUI elements
        self.create_header()
        self.create_file_selection()
        self.create_processing_options()
        self.create_progress_section()
        self.create_log_section()
        self.create_action_buttons()
        self.create_menu()
    
    def setup_styles(self):
        """Setup custom styles for the application."""
        style = ttk.Style()
        
        # Configure custom styles
        style.configure('Header.TLabel', font=('Segoe UI', 16, 'bold'))
        style.configure('Subheader.TLabel', font=('Segoe UI', 10, 'bold'))
        style.configure('Action.TButton', font=('Segoe UI', 10, 'bold'))
    
    def create_header(self):
        """Create application header."""
        header_frame = ttk.Frame(self.main_frame)
        header_frame.grid(row=0, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(0, 20))
        
        ttk.Label(
            header_frame, 
            text=self.config.app_name,
            style='Header.TLabel'
        ).grid(row=0, column=0, sticky=tk.W)
        
        ttk.Label(
            header_frame,
            text=f"Version {self.config.version}",
            foreground='gray'
        ).grid(row=1, column=0, sticky=tk.W)
    
    def create_file_selection(self):
        """Create file selection section."""
        # File selection label
        ttk.Label(
            self.main_frame,
            text="Select PDF File:",
            style='Subheader.TLabel'
        ).grid(row=1, column=0, sticky=tk.W, pady=(0, 5))
        
        # File selection frame
        file_frame = ttk.Frame(self.main_frame)
        file_frame.grid(row=2, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(0, 15))
        file_frame.columnconfigure(1, weight=1)
        
        # File path entry
        self.file_path_var = tk.StringVar()
        self.file_path_entry = ttk.Entry(
            file_frame,
            textvariable=self.file_path_var,
            state='readonly',
            width=50
        )
        self.file_path_entry.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(0, 10))
        
        ttk.Button(
            file_frame,
            text="Browse...",
            command=self.browse_file
        ).grid(row=0, column=2, sticky=tk.W)
    
    def create_processing_options(self):
        """Create processing options section."""
        options_frame = ttk.LabelFrame(self.main_frame, text="Processing Options", padding="10")
        options_frame.grid(row=3, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(0, 15))
        
        # Auto-organize option
        self.auto_organize_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            options_frame,
            text="Automatically organize files by tag",
            variable=self.auto_organize_var
        ).grid(row=0, column=0, sticky=tk.W, pady=2)
        
        # Save logs option
        self.save_logs_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            options_frame,
            text="Save processing logs",
            variable=self.save_logs_var
        ).grid(row=1, column=0, sticky=tk.W, pady=2)
        
        # Force OCR option
        self.force_ocr_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            options_frame,
            text="Force OCR processing (recommended)",
            variable=self.force_ocr_var
        ).grid(row=2, column=0, sticky=tk.W, pady=2)
    
    def create_progress_section(self):
        """Create progress tracking section."""
        progress_frame = ttk.LabelFrame(self.main_frame, text="Processing Progress", padding="10")
        progress_frame.grid(row=4, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(0, 15))
        progress_frame.columnconfigure(0, weight=1)
        
        # Progress bar
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(
            progress_frame,
            variable=self.progress_var,
            mode='indeterminate'
        )
        self.progress_bar.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 5))
        
        # Status label
        self.status_var = tk.StringVar(value="Ready to process")
        self.status_label = ttk.Label(
            progress_frame,
            textvariable=self.status_var,
            foreground='blue'
        )
        self.status_label.grid(row=1, column=0, sticky=tk.W)
    
    def create_log_section(self):
        """Create log display section."""
        log_frame = ttk.LabelFrame(self.main_frame, text="Processing Log", padding="10")
        log_frame.grid(row=5, column=0, columnspan=3, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 15))
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)
        self.main_frame.rowconfigure(5, weight=1)
        
        # Log text area with scrollbar
        self.log_text = scrolledtext.ScrolledText(
            log_frame,
            height=10,
            state='disabled',
            wrap=tk.WORD
        )
        self.log_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Log controls
        log_controls = ttk.Frame(log_frame)
        log_controls.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=(5, 0))
        
        ttk.Button(
            log_controls,
            text="Clear Log",
            command=self.clear_log
        ).grid(row=0, column=0, sticky=tk.W)
        
        ttk.Button(
            log_controls,
            text="Save Log",
            command=self.save_log
        ).grid(row=0, column=1, sticky=tk.W, padx=(10, 0))
    
    def create_action_buttons(self):
        """Create main action buttons."""
        button_frame = ttk.Frame(self.main_frame)
        button_frame.grid(row=6, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(10, 0))
        
        # Process button
        self.process_button = ttk.Button(
            button_frame,
            text="Process PDF",
            command=self.start_processing,
            style='Action.TButton'
        )
        self.process_button.grid(row=0, column=0, sticky=tk.W)
        
        # Cancel button
        self.cancel_button = ttk.Button(
            button_frame,
            text="Cancel",
            command=self.cancel_processing,
            state='disabled'
        )
        self.cancel_button.grid(row=0, column=1, sticky=tk.W, padx=(10, 0))
        
        # Open output button
        self.open_output_button = ttk.Button(
            button_frame,
            text="Open Output Folder",
            command=self.open_output_folder,
            state='disabled'
        )
        self.open_output_button.grid(row=0, column=2, sticky=tk.W, padx=(10, 0))
        
        # Spacer
        button_frame.columnconfigure(3, weight=1)
        
        # Exit button
        ttk.Button(
            button_frame,
            text="Exit",
            command=self.root.quit
        ).grid(row=0, column=4, sticky=tk.E)
    
    def create_menu(self):
        """Create application menu bar."""
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)
        
        # File menu
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="Open PDF...", command=self.browse_file, accelerator="Ctrl+O")
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.root.quit, accelerator="Ctrl+Q")
        
        # Tools menu
        tools_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Tools", menu=tools_menu)
        tools_menu.add_command(label="Clear Log", command=self.clear_log)
        tools_menu.add_command(label="Save Log...", command=self.save_log)
        tools_menu.add_separator()
        tools_menu.add_command(label="Open Output Folder", command=self.open_output_folder)
        
        # Help menu
        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Help", menu=help_menu)
        help_menu.add_command(label="Check for Updates", command=self.check_updates_manual)
        help_menu.add_separator()
        help_menu.add_command(label="About", command=self.show_about)
        
        # Keyboard shortcuts
        self.root.bind('<Control-o>', lambda e: self.browse_file())
        self.root.bind('<Control-q>', lambda e: self.root.quit())
    
    # ===============================================================================
    # EVENT HANDLERS
    # ===============================================================================
    
    def browse_file(self):
        """Open file browser to select PDF file."""
        filename = filedialog.askopenfilename(
            title="Select PDF File",
            filetypes=[
                ("PDF files", "*.pdf"),
                ("All files", "*.*")
            ]
        )
        
        if filename:
            self.selected_file = filename
            self.file_path_var.set(filename)
            self.log_message(f"Selected file: {filename}")
            
            # Enable process button
            self.process_button.config(state='normal')
    
    def start_processing(self):
        """Start the PDF processing in a separate thread."""
        if not self.selected_file:
            messagebox.showerror("Error", "Please select a PDF file first.")
            return
        
        if self.processing:
            messagebox.showwarning("Warning", "Processing is already in progress.")
            return
        
        # Validate file exists
        if not os.path.exists(self.selected_file):
            messagebox.showerror("Error", "Selected file does not exist.")
            return
        
        # Update UI state
        self.processing = True
        self.process_button.config(state='disabled')
        self.cancel_button.config(state='normal')
        self.open_output_button.config(state='disabled')
        self.progress_bar.start()
        
        # Clear previous log
        self.clear_log()
        self.log_message("Starting PDF processing...")
        
        # Start processing thread
        self.processing_thread = threading.Thread(
            target=self.process_pdf_thread,
            daemon=True
        )
        self.processing_thread.start()
    
    def process_pdf_thread(self):
        """Execute PDF processing in separate thread."""
        try:
            # Create processor with progress callback
            processor = VeetechProcessor(
                self.selected_file,
                progress_callback=self.update_progress_safe
            )
            
            # Execute processing
            result = processor.process()
            
            # Update UI with results
            self.root.after(0, self.processing_complete, result)
        
        except Exception as e:
            error_msg = f"Processing failed: {str(e)}"
            self.logger.error(error_msg)
            self.logger.error(traceback.format_exc())
            self.root.after(0, self.processing_error, error_msg)
    
    def update_progress_safe(self, message: str):
        """Thread-safe progress update."""
        self.root.after(0, self.update_progress, message)
    
    def update_progress(self, message: str):
        """Update progress display."""
        self.status_var.set(message)
        self.log_message(message)
        self.root.update_idletasks()
    
    def processing_complete(self, result: ProcessingResult):
        """Handle successful processing completion."""
        self.processing = False
        self.progress_bar.stop()
        
        # Update UI state
        self.process_button.config(state='normal')
        self.cancel_button.config(state='disabled')
        self.open_output_button.config(state='normal')
        
        # Display results
        self.status_var.set("Processing complete!")
        self.log_message("=" * 50)
        self.log_message("PROCESSING RESULTS:")
        self.log_message(f"Total certificates: {result.total_chunks}")
        self.log_message(f"Successfully processed: {result.successful}")
        self.log_message(f"Failed: {result.failed}")
        
        if result.errors:
            self.log_message("\nERRORS ENCOUNTERED:")
            for chunk_path, start, end, error in result.errors:
                chunk_name = os.path.basename(chunk_path)
                self.log_message(f"- {chunk_name} (pages {start+1}-{end}): {error}")
        
        self.log_message(f"\nOutput directory: {result.output_directory}")
        self.log_message("=" * 50)
        
        # Show completion dialog
        success_rate = (result.successful / result.total_chunks) * 100 if result.total_chunks > 0 else 0
        
        if result.failed == 0:
            messagebox.showinfo(
                "Processing Complete",
                f"Successfully processed all {result.successful} certificates!\n\n"
                f"Output directory:\n{result.output_directory}"
            )
        else:
            messagebox.showwarning(
                "Processing Complete with Errors",
                f"Processed {result.successful}/{result.total_chunks} certificates successfully ({success_rate:.1f}%)\n\n"
                f"{result.failed} certificates failed to process.\n"
                f"Check the log for details.\n\n"
                f"Output directory:\n{result.output_directory}"
            )
        
        # Store output directory for later use
        self.last_output_dir = result.output_directory
    
    def processing_error(self, error_msg: str):
        """Handle processing error."""
        self.processing = False
        self.progress_bar.stop()
        
        # Update UI state
        self.process_button.config(state='normal')
        self.cancel_button.config(state='disabled')
        self.status_var.set("Processing failed!")
        
        # Log error
        self.log_message(f"ERROR: {error_msg}")
        
        # Show error dialog
        messagebox.showerror("Processing Error", error_msg)
    
    def cancel_processing(self):
        """Cancel ongoing processing."""
        if self.processing:
            # Note: This is a simple implementation
            # A more robust version would properly terminate the processing thread
            self.processing = False
            self.progress_bar.stop()
            self.process_button.config(state='normal')
            self.cancel_button.config(state='disabled')
            self.status_var.set("Processing cancelled")
            self.log_message("Processing cancelled by user")
    
    def open_output_folder(self):
        """Open the output folder in Windows Explorer."""
        if hasattr(self, 'last_output_dir') and os.path.exists(self.last_output_dir):
            os.startfile(self.last_output_dir)
        else:
            messagebox.showwarning("Warning", "No output folder available.")
    
    def clear_log(self):
        """Clear the log display."""
        self.log_text.config(state='normal')
        self.log_text.delete(1.0, tk.END)
        self.log_text.config(state='disabled')
    
    def save_log(self):
        """Save log content to file."""
        filename = filedialog.asksaveasfilename(
            title="Save Log File",
            defaultextension=".txt",
            filetypes=[
                ("Text files", "*.txt"),
                ("All files", "*.*")
            ]
        )
        
        if filename:
            try:
                log_content = self.log_text.get(1.0, tk.END)
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write(log_content)
                messagebox.showinfo("Success", f"Log saved to:\n{filename}")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to save log:\n{str(e)}")
    
    def log_message(self, message: str):
        """Add message to log display."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        formatted_message = f"[{timestamp}] {message}\n"
        
        self.log_text.config(state='normal')
        self.log_text.insert(tk.END, formatted_message)
        self.log_text.see(tk.END)
        self.log_text.config(state='disabled')
    
    # ===============================================================================
    # UPDATE MANAGEMENT
    # ===============================================================================
    
    def check_updates_silent(self):
        """Check for updates silently on startup."""
        def check_thread():
            update_info = self.update_manager.check_for_updates()
            if not update_info.get('error') and update_info.get('update_available'):
                self.root.after(0, self.show_update_notification, update_info)
        
        threading.Thread(target=check_thread, daemon=True).start()
    
    def check_updates_manual(self):
        """Manually check for updates."""
        def check_thread():
            update_info = self.update_manager.check_for_updates()
            self.root.after(0, self.show_update_results, update_info)
        
        # Show checking dialog
        messagebox.showinfo("Update Check", "Checking for updates...")
        threading.Thread(target=check_thread, daemon=True).start()
    
    def show_update_notification(self, update_info: Dict[str, Any]):
        """Show update notification popup."""
        result = messagebox.askyesno(
            "Update Available",
            f"A new version ({update_info['latest_version']}) is available!\n\n"
            f"Current version: {self.config.version}\n"
            f"New version: {update_info['latest_version']}\n\n"
            f"Would you like to download and install the update?"
        )
        
        if result:
            self.download_and_install_update(update_info['download_url'])
    
    def show_update_results(self, update_info: Dict[str, Any]):
        """Show manual update check results."""
        if update_info.get('error'):
            messagebox.showerror(
                "Update Check Failed",
                f"Failed to check for updates:\n{update_info['error']}"
            )
        elif update_info.get('update_available'):
            self.show_update_notification(update_info)
        else:
            messagebox.showinfo(
                "No Updates Available",
                f"You are running the latest version ({self.config.version})."
            )
    
    def download_and_install_update(self, download_url: str):
        """Download and install update."""
        def download_thread():
            try:
                # Download update
                update_file = self.update_manager.download_update(
                    download_url,
                    progress_callback=self.update_download_progress
                )
                
                # Apply update
                success = self.update_manager.apply_update(update_file)
                self.root.after(0, self.update_download_complete, success)
            
            except Exception as e:
                error_msg = f"Update failed: {str(e)}"
                self.root.after(0, self.update_download_error, error_msg)
        
        # Start download
        self.log_message("Starting update download...")
        threading.Thread(target=download_thread, daemon=True).start()
    
    def update_download_progress(self, message: str):
        """Update download progress."""
        self.root.after(0, self.log_message, message)
    
    def update_download_complete(self, success: bool):
        """Handle update download completion."""
        if success:
            messagebox.showinfo(
                "Update Complete",
                "Update downloaded successfully!\n"
                "The application will restart to apply the update."
            )
        else:
            messagebox.showerror(
                "Update Failed",
                "Failed to apply update. Please try again later."
            )
    
    def update_download_error(self, error_msg: str):
        """Handle update download error."""
        self.log_message(f"Update error: {error_msg}")
        messagebox.showerror("Update Error", error_msg)
    
    # ===============================================================================
    # HELP AND ABOUT
    # ===============================================================================
    
    def show_about(self):
        """Show about dialog."""
        about_text = f"""
{self.config.app_name}
Version {self.config.version}

Automated PDF certificate processing application with intelligent 
metadata extraction and file organization capabilities.

Features:
• Automatic OCR processing
• Certificate detection and splitting
• Metadata extraction (due dates, tags, serials)
• Intelligent file naming and organization
• Remote update management

© 2024 Veetech Solutions
        """.strip()
        
        messagebox.showinfo("About", about_text)
    
    # ===============================================================================
    # APPLICATION LIFECYCLE
    # ===============================================================================
    
    def run(self):
        """Start the application main loop."""
        self.logger.info(f"Starting {self.config.app_name} v{self.config.version}")
        
        # Center window on screen
        self.center_window()
        
        # Start main loop
        try:
            self.root.mainloop()
        except KeyboardInterrupt:
            self.logger.info("Application interrupted by user")
        except Exception as e:
            self.logger.error(f"Application error: {e}")
            self.logger.error(traceback.format_exc())
        finally:
            self.logger.info("Application shutting down")
    
    def center_window(self):
        """Center the application window on screen."""
        self.root.update_idletasks()
        
        # Get window dimensions
        window_width = self.root.winfo_width()
        window_height = self.root.winfo_height()
        
        # Get screen dimensions
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        
        # Calculate center position
        x = (screen_width // 2) - (window_width // 2)
        y = (screen_height // 2) - (window_height // 2)
        
        # Set window position
        self.root.geometry(f"{window_width}x{window_height}+{x}+{y}")


# ===============================================================================
# APPLICATION ENTRY POINT
# ===============================================================================

def main():
    """Application entry point."""
    try:
        # Create and run application
        app = VeetechDesktopApp()
        app.run()
    
    except Exception as e:
        # Log critical error
        logging.error(f"Critical application error: {e}")
        logging.error(traceback.format_exc())
        
        # Show error to user
        try:
            messagebox.showerror(
                "Critical Error",
                f"A critical error occurred:\n{str(e)}\n\n"
                f"Please check the log file for details."
            )
        except:
            print(f"Critical error: {e}")
    
    finally:
        # Cleanup
        try:
            # Clean up temporary files
            temp_dir = tempfile.gettempdir()
            for item in os.listdir(temp_dir):
                if item.startswith("veetech_"):
                    item_path = os.path.join(temp_dir, item)
                    try:
                        if os.path.isdir(item_path):
                            shutil.rmtree(item_path)
                        else:
                            os.remove(item_path)
                    except:
                        pass
        except:
            pass


if __name__ == "__main__":
    main()