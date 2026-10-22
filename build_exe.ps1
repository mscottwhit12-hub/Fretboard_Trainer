# Build a single-file Windows executable.
# Run from the fretboard_app folder (the one containing main.py):
#     powershell -ExecutionPolicy Bypass -File .\build_exe.ps1
# Result: dist\FretboardTrainer.exe

$ErrorActionPreference = "Stop"

python -m pip install --upgrade pip pyinstaller PyQt6
if ($LASTEXITCODE -ne 0) { throw "pip install failed" }

if (-not (Test-Path "main.py")) { throw "main.py not found - run this from the fretboard_app folder" }
if (-not (Test-Path "fonts\ArchivoBlack-Regular.ttf")) { throw "fonts folder is missing" }

python -m PyInstaller `
    --noconfirm --clean `
    --onefile --windowed `
    --name FretboardTrainer `
    --add-data "fonts;fonts" `
    --collect-submodules ui `
    --collect-submodules core `
    --collect-submodules data `
    main.py
if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed" }

Write-Host ""
Write-Host "Done: $(Resolve-Path dist\FretboardTrainer.exe)"
