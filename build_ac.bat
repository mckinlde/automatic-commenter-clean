@echo off
REM PySide6 AutoCommenter Build Script for Windows
REM Builds a standalone Windows executable
REM
REM Usage in PowerShell: .\build_ac.bat
REM Usage in Command Prompt: build_ac.bat

echo Activating virtual environment...
call .venv\Scripts\activate.bat

echo Installing requirements...
pip install -r requirements.txt

echo Building PySide6 AutoCommenter executable...

REM Create version info file for metadata
echo Creating version info...
python -c "
with open('version_info.txt', 'w') as f:
    f.write('''VSVersionInfo(
  ffi=FixedFileInfo(
    filevers=(1, 0, 0, 0),
    prodvers=(1, 0, 0, 0),
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo([
      StringTable(
        u'040904B0',
        [StringStruct(u'CompanyName', u'AutoCommenter'),
         StringStruct(u'FileDescription', u'AutoCommenter - Social Media Automation'),
         StringStruct(u'FileVersion', u'1.0.0.0'),
         StringStruct(u'InternalName', u'AutoCommenter'),
         StringStruct(u'LegalCopyright', u'Copyright (C) 2026 AutoCommenter'),
         StringStruct(u'OriginalFilename', u'AutoCommenter.exe'),
         StringStruct(u'ProductName', u'AutoCommenter'),
         StringStruct(u'ProductVersion', u'1.0.0.0')]
      )
    ]),
    VarFileInfo([VarStruct(u'Translation', [1033, 1200])])
  ]
)''')
"

REM Build the executable
python -m PyInstaller ^
  --noconfirm ^
  --onedir ^
  --windowed ^
  --name AutoCommenter ^
  --icon assets\app.ico ^
  --version-file version_info.txt ^
  --add-data "assets;assets" ^
  --add-data "config_ac.py;." ^
  --add-data "license_manager.py;." ^
  --add-data "models_ac.py;." ^
  --add-data "platform_strategies.py;." ^
  --add-data "browser_engine.py;." ^
  --add-data "campaign_client.py;." ^
  --add-data "cursor_manager.py;." ^
  --add-data "worker.py;." ^
  --add-data "gui_ac.py;." ^
  --hidden-import PySide6.QtCore ^
  --hidden-import PySide6.QtGui ^
  --hidden-import PySide6.QtWidgets ^
  --hidden-import requests ^
  --hidden-import selenium ^
  --hidden-import webdriver_manager ^
  --hidden-import json ^
  --hidden-import pathlib ^
  --hidden-import hashlib ^
  --hidden-import uuid ^
  --hidden-import platform ^
  --hidden-import subprocess ^
  --hidden-import webbrowser ^
  --hidden-import os ^
  --hidden-import threading ^
  --hidden-import time ^
  --hidden-import base64 ^
  app_ac.py

REM Clean up version info file
del version_info.txt

echo Build complete! Check the 'dist' folder for AutoCommenter.exe
echo.
echo To run: dist\AutoCommenter\AutoCommenter.exe
pause
