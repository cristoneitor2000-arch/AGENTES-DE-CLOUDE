@echo off
REM Genera dist\Cuantificador.exe (PyInstaller --onefile --windowed) y copia junto al exe los JSON editables.
REM Requisitos: Python 3.11+ en el PATH (python --version).
setlocal
cd /d "%~dp0"
python -m venv .venv_build || goto :error
call .venv_build\Scripts\activate.bat || goto :error
python -m pip install --upgrade pip
python -m pip install -r requirements.txt pyinstaller || goto :error
python -m PyInstaller --noconfirm --clean --onefile --windowed --name Cuantificador ^
  --collect-submodules ezdxf --collect-data ezdxf --collect-submodules shapely ^
  app.py || goto :error
copy /Y convenciones.json dist\ >nul
copy /Y config.json dist\ >nul
echo.
echo Listo: dist\Cuantificador.exe  (convenciones.json y config.json van junto al exe y se editan ahi)
goto :eof
:error
echo.
echo ERROR en la compilacion. Revisar los mensajes de arriba.
exit /b 1
