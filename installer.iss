; installer.iss

[Setup]
AppName=SplitMe
AppVersion=1.0.0
DefaultDirName={pf}\SplitMe
OutputBaseFilename=SplitMe-1.0.0-Setup
Compression=lzma
SolidCompression=yes

[Files]
; 1) Copy your frozen EXE
Source: "dist\SplitMe.exe"; DestDir: "{app}"; Flags: ignoreversion

; 2) Include the Tesseract installer and Ghostscript EXE
Source: "assets\tesseract-ocr-w64-setup-5.5.0.20241111.exe"; DestDir: "{tmp}"; Flags: deleteafterinstall
Source: "assets\gs10051w64.exe";                       DestDir: "{tmp}"; Flags: deleteafterinstall

[Run]
; 3) Install Tesseract silently if not already present
Filename: "{tmp}\tesseract-ocr-w64-setup-5.5.0.20241111.exe"; \
  Parameters: "/SILENT"; \
  Check: not IsTesseractInstalled

; 4) Install Ghostscript silently if not already present
Filename: "{tmp}\gs10051w64.exe"; \
  Parameters: "/SILENT"; \
  Check: not IsGhostscriptInstalled

[Code]
function IsTesseractInstalled: Boolean;
begin
  // Tesseract usually writes this key under HKLM for version 5.x
  Result := RegKeyExists(HKLM, 'SOFTWARE\Tesseract-OCR\5.0');
end;

function IsGhostscriptInstalled: Boolean;
begin
  // Ghostscript 10.x writes a key like:
  //   HKLM\SOFTWARE\GPL Ghostscript\10.0
  // Adjust “10.0” to match your Ghostscript version if needed.
  Result := RegKeyExists(HKLM, 'SOFTWARE\GPL Ghostscript\10.0');
end;
