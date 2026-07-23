@echo off
title Empaquetando agente cliente...
echo.
echo  Instalando PyInstaller...
pip install pyinstaller --quiet

echo  Empaquetando agente_cliente.py → AsistenciaTucTuc.exe
echo.

pyinstaller --onefile --windowed --name "AsistenciaTucTuc" ^
  --noupx ^
  --version-file=file_version_info.txt ^
  --hidden-import=mss ^
  --hidden-import=mss.windows ^
  --hidden-import=PIL ^
  --hidden-import=PIL.Image ^
  --hidden-import=pyautogui ^
  --hidden-import=socketio ^
  --hidden-import=engineio ^
  agente_cliente.py

echo.
if exist dist\AsistenciaTucTuc.exe (
  echo  ✓ Listo: dist\AsistenciaTucTuc.exe
  echo  Ese archivo es el que le mandas al cliente.
) else (
  echo  ✗ Algo falló. Revisa los errores arriba.
)
echo.
pause
