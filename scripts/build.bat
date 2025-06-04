@echo off
echo Building SplitMe Application...
cd /d "%~dp0\.."
python build/build_script.py
if %ERRORLEVEL% == 0 (
    echo Build completed successfully!
    echo Running Inno Setup...
    "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" build/SplitMe.iss
) else (
    echo Build failed!
    pause
)