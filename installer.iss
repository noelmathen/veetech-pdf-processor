; ----------------------------------------------------------------------
; SplitMe installer for Windows (Inno Setup)
; ----------------------------------------------------------------------

[Setup]
; Application details
AppName=SplitMe
AppVersion=1.0.0
DefaultDirName={pf}\SplitMe
DefaultGroupName=SplitMe
OutputBaseFilename=SplitMe-1.0.0-Setup

; Use solid LZMA compression
Compression=lzma
SolidCompression=yes

; Allow the installer and uninstaller to run as administrator if needed
PrivilegesRequired=admin

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

; ----------------------------------------------------------------------
; Files to install
; ----------------------------------------------------------------------
[Files]
; 1) Copy the main EXE (already built by PyInstaller).
;    "ignoreversion" means “don’t bother checking version when overwriting.”
;    "restartreplace" ensures the EXE is replaced on reboot if in use.
Source: "dist\SplitMe.exe"; DestDir: "{app}"; Flags: ignoreversion restartreplace

; 2) Include Tesseract and Ghostscript installers for optional runtime install.
;    They go to {tmp} and get deleted after install (deleteafterinstall).
Source: "assets\tesseract-ocr-w64-setup-5.5.0.20241111.exe"; DestDir: "{tmp}"; Flags: deleteafterinstall
Source: "assets\gs10051w64.exe";                           DestDir: "{tmp}"; Flags: deleteafterinstall

; 3) (Optional) If your application creates logs or output subfolders at runtime,
;    you don’t need to list them here. We’ll remove them in [UninstallDelete].

; ----------------------------------------------------------------------
; Desktop and Start Menu shortcuts
; ----------------------------------------------------------------------
[Icons]
; Start Menu\Programs\SplitMe → SplitMe.exe
Name: "{group}\SplitMe";           Filename: "{app}\SplitMe.exe"
; Desktop shortcut
Name: "{userdesktop}\SplitMe";     Filename: "{app}\SplitMe.exe"

; ----------------------------------------------------------------------
; Run external installers at install time
; ----------------------------------------------------------------------
[Run]
; 1) Install Tesseract silently if not already installed
Filename: "{tmp}\tesseract-ocr-w64-setup-5.5.0.20241111.exe"; \
  Parameters: "/SILENT"; \
  Check: not IsTesseractInstalled

; 2) Install Ghostscript silently if not already installed
Filename: "{tmp}\gs10051w64.exe"; \
  Parameters: "/SILENT"; \
  Check: not IsGhostscriptInstalled

; ----------------------------------------------------------------------
; Uninstallation: delete any files/folders we may have created at runtime
; ----------------------------------------------------------------------
[UninstallDelete]
; Remove any files or folders under {app} (even if app created them later)
Type: filesandordirs; Name: "{app}"

; ----------------------------------------------------------------------
; Registry checks to see if Tesseract/Ghostscript is already installed
; ----------------------------------------------------------------------
[Code]
function IsTesseractInstalled: Boolean;
begin
  // Tesseract 5 writes this key:
  Result := RegKeyExists(HKLM, 'SOFTWARE\Tesseract-OCR\5.0');
end;

function IsGhostscriptInstalled: Boolean;
begin
  // Ghostscript 10.x writes "SOFTWARE\GPL Ghostscript\10.0"
  // Adjust if your GS version is different.
  Result := RegKeyExists(HKLM, 'SOFTWARE\GPL Ghostscript\10.0');
end;
