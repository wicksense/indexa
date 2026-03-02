$ErrorActionPreference = "Stop"

python -m pip install --upgrade pip
pip install -r requirements.txt pyinstaller

pyinstaller --noconfirm --clean --windowed --name Indexa --hidden-import indexa.rename --collect-all PySide6 -m indexa.gui

Write-Host "Build complete. Artifact: dist/Indexa/Indexa.exe"
