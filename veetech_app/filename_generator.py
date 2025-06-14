# veetech_app/filename_generator.py

from typing import Set
from .metadata_extractor import CertificateMetadata

class FilenameGenerator:
    """Generates standardized filenames for certificates."""

    @staticmethod
    def create_filename(metadata: CertificateMetadata, force_serial: bool = False) -> str:
        """Generate filename from metadata."""
        core_id = FilenameGenerator._build_core_id(metadata, force_serial)
        filename = f"{metadata.issue_date}_{core_id.replace(' ', '-')}_{metadata.certificate_type}.pdf"
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
