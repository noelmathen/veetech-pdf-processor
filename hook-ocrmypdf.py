# hook-ocrmypdf.py
from PyInstaller.utils.hooks import collect_submodules, collect_data_files

hiddenimports = collect_submodules("ocrmypdf")
datas         = collect_data_files("ocrmypdf")   # pulls in ocrmypdf/data/*
