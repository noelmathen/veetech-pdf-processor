import os
import shutil
import subprocess
import sys
from pathlib import Path

def clean_build():
    """Clean previous build artifacts"""
    dirs_to_clean = ['build', 'dist', '__pycache__']
    for dir_name in dirs_to_clean:
        if os.path.exists(dir_name):
            shutil.rmtree(dir_name)
            print(f"Cleaned {dir_name}")

def build_executable():
    """Build the executable using PyInstaller"""
    cmd = [
        'pyinstaller',
        '--onefile',
        '--windowed',
        '--name', 'SplitMe',
        '--icon', 'assets/veetech_icon.ico',
        '--add-data', 'assets/veetech_icon.ico;assets',
        '--collect-submodules', 'ocrmypdf',
        '--collect-data', 'ocrmypdf',
        '--distpath', 'dist',
        '--workpath', 'build/temp',
        'run.py'
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode == 0:
        print("✅ Executable built successfully!")
        return True
    else:
        print("❌ Build failed:")
        print(result.stderr)
        return False

if __name__ == "__main__":
    print("🔧 Starting build process...")
    clean_build()
    if build_executable():
        print("🎉 Build completed successfully!")
        print("📁 Executable location: dist/SplitMe.exe")
    else:
        sys.exit(1)