@echo off
cd /d "%~dp0"
echo Iniciando Sistema de Sueldos...

:: Intentar con la ruta conocida que tiene streamlit instalado
if exist "%LOCALAPPDATA%\Programs\Python\Python314\python.exe" (
    "%LOCALAPPDATA%\Programs\Python\Python314\python.exe" -m streamlit run app.py
    goto :end
)

:: Intentar con py launcher
py -m streamlit run app.py 2>nul
if %errorlevel%==0 goto :end

:: Intentar con python del PATH
python -m streamlit run app.py 2>nul
if %errorlevel%==0 goto :end

echo.
echo [ERROR] No se encontro Python con Streamlit instalado.
echo Instala Python desde https://www.python.org/downloads/
echo IMPORTANTE: Marca la opcion "Add Python to PATH" durante la instalacion.
echo Luego ejecuta: pip install -r requirements.txt

:end
pause
