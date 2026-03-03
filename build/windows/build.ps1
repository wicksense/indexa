$ErrorActionPreference = "Stop"

python -m pip install --upgrade pip
pip install -r requirements.txt pyinstaller

pyinstaller --noconfirm --clean --windowed --name Indexa --hidden-import indexa.rename --collect-all PySide6 indexa/gui.py

if (Get-Command iscc -ErrorAction SilentlyContinue) {
  iscc build/windows/Indexa.iss
  Write-Host "Installer created at dist/Indexa-Setup.exe"
} else {
  Write-Host "Inno Setup compiler (iscc) not found. Skipping installer build."
}

Write-Host "Portable artifact: dist/Indexa/Indexa.exe"
