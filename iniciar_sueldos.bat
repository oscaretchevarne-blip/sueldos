@echo off
cd /d "%~dp0"
echo Iniciando Sistema de Sueldos...

:: Intentar con python del PATH
python --version >nul 2>&1
if %errorlevel%==0 (
    python -m streamlit run app.py
    goto :end
)

:: Intentar con py launcher
py --version >nul 2>&1
if %errorlevel%==0 (
    py -m streamlit run app.py
    goto :end
)

:: Intentar ruta comun de instalacion
if exist "C:\Python314\python.exe" (
    "C:\Python314\python.exe" -m streamlit run app.py
    goto :end
)

if exist "%LOCALAPPDATA%\Programs\Python\Python314\python.exe" (
    "%LOCALAPPDATA%\Programs\Python\Python314\python.exe" -m streamlit run app.py
    goto :end
)

echo [ERROR] No se encontro Python instalado.
echo Instala Python desde https://www.python.org/downloads/
echo IMPORTANTE: Marca la opcion "Add Python to PATH" durante la instalacion.

:end
pause
