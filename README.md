# SplitMe – Veetech PDF Processor

> **Automated certificate splitter, OCR-enhancer & file-organiser for multi-page PDF bundles.**  
> Built with Python + Tkinter, bundled as a single Windows EXE – no Python required.

---

## ✨  Key Features

| Capability | Details |
|------------|---------|
| **One-click processing** | Drag-and-drop or browse to a large PDF containing many certificates; SplitMe OCRs it, finds each certificate boundary, and saves individual files. |
| **Smart OCR** | Bundles **Tesseract 5** + **Ghostscript 10** internally – installs them automatically. |
| **Metadata extraction** | Pulls Tag No., Serial No., Unit ID, Due Date, and Certificate Type via regex heuristics. |
| **Intelligent filenames** | Generates `YYYYMMDD_TAG_CertificateType.pdf` (or falls back to Serial/Unit) – avoids duplicates automatically. |
| **Auto-foldering** | Optionally groups output PDFs into sub-folders by base tag. |
| **In-app update** | “Help → Check for updates” fetches the newest Release from GitHub. |
| **Portable build** | Works on any Windows system with a single EXE + installer. No manual dependencies required. |

---

## 🚀  How to Install & Use (Step-by-Step)

1. **[⬇️ Download the installer](https://github.com/noelmathen/veetech-pdf-processor/releases/download/v1.0.1/SplitMe-1.0.1-Setup.exe)**

2. Run the downloaded `SplitMe-1.0.1-Setup.exe`.

3. **When asked for installation location, choose a folder like `Downloads`** (you can avoid Desktop or Program Files for convenience).

4. Continue the installer.

5. **Tesseract OCR installation will pop up automatically** – just follow the prompt and install it. You can install it anywhere.

6. **Ghostscript installation will also pop up** – follow the same steps and install it (anywhere is fine).

7. Once installation completes, **launch SplitMe** from the created shortcut or from the install folder.

8. Inside the app:
   - Click **Browse...** and select your PDF.
   - Click **Process PDF**.

9. Once completed, the **output folder will be in the same location as the input PDF**, containing all the split and renamed certificate PDFs.

---

## 📸  Screenshots
| Main window | Finished run |
|-------------|--------------|
| ![UI](docs/img/ui.png) | ![Results](docs/img/results.png) |

---

## 🛠️  For Developers – Build from Source

```bash
git clone https://github.com/noelmathen/veetech-pdf-processor.git
cd veetech-pdf-processor
python -m venv build_env && build_env\Scripts\activate
pip install -r requirements.txt
pyinstaller --onefile --windowed --name SplitMe --icon assets\veetech_icon.ico --add-data "assets\veetech_icon.ico;assets" --collect-submodules ocrmypdf --collect-data ocrmypdf run.py
