$ErrorActionPreference = "Stop"

python -m pip install --upgrade pip
pip install -r requirements.txt pyinstaller

pyinstaller --noconfirm --clean --windowed --name Indexa --hidden-import indexa.rename `
  --exclude-module PySide6.Qt3DCore --exclude-module PySide6.Qt3DRender --exclude-module PySide6.Qt3DInput `
  --exclude-module PySide6.QtCharts --exclude-module PySide6.QtDataVisualization --exclude-module PySide6.QtMultimedia `
  --exclude-module PySide6.QtMultimediaWidgets --exclude-module PySide6.QtNetworkAuth --exclude-module PySide6.QtPdf `
  --exclude-module PySide6.QtPdfWidgets --exclude-module PySide6.QtPositioning --exclude-module PySide6.QtQml `
  --exclude-module PySide6.QtQuick --exclude-module PySide6.QtQuickControls2 --exclude-module PySide6.QtRemoteObjects `
  --exclude-module PySide6.QtScxml --exclude-module PySide6.QtSensors --exclude-module PySide6.QtSerialBus `
  --exclude-module PySide6.QtSerialPort --exclude-module PySide6.QtSql --exclude-module PySide6.QtStateMachine `
  --exclude-module PySide6.QtSvg --exclude-module PySide6.QtSvgWidgets --exclude-module PySide6.QtTest `
  --exclude-module PySide6.QtTextToSpeech --exclude-module PySide6.QtWebChannel --exclude-module PySide6.QtWebEngineCore `
  --exclude-module PySide6.QtWebEngineWidgets --exclude-module PySide6.QtWebSockets --exclude-module PySide6.QtBluetooth `
  indexa/gui.py

if (Get-Command iscc -ErrorAction SilentlyContinue) {
  iscc build/windows/Indexa.iss
  Write-Host "Installer created at dist/Indexa-Setup.exe"
} else {
  Write-Host "Inno Setup compiler (iscc) not found. Skipping installer build."
}

Write-Host "Portable artifact: dist/Indexa/Indexa.exe"
