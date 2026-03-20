@echo off
setlocal enabledelayedexpansion
title BACKUP PORTABLE - Sistema de Sueldos
cd /d "%~dp0"

set "APP_NAME=Sistema_Sueldos"
set "SRC_DIR=%~dp0"

:: Obtener fecha y hora
for /f "tokens=*" %%a in ('powershell -NoProfile -Command "Get-Date -format 'yyyyMMdd_HHmm'"') do set "STAMP=%%a"
if "%STAMP%"=="" set "STAMP=backup"

set "BACKUP_NAME=%APP_NAME%_Portable_%STAMP%"
set "BACKUP_BASE=C:\Antigravity Proyectos\BACKUP"
if not exist "%BACKUP_BASE%" mkdir "%BACKUP_BASE%"
set "BACKUP_DIR=%BACKUP_BASE%\%BACKUP_NAME%"
set "ZIP_FILE=%BACKUP_BASE%\%BACKUP_NAME%.zip"

echo.
echo ==================================================
echo   BACKUP PORTABLE - %APP_NAME%
echo ==================================================
echo.
echo   Incluye: App + Datos + Entorno Python completo
echo   Destino: Escritorio\%BACKUP_NAME%.zip
echo.
echo ==================================================
echo.

:: ============================================
:: 1. CREAR CARPETA Y COPIAR ARCHIVOS CORE
:: ============================================
echo [1/6] Copiando archivos del sistema...

if exist "%BACKUP_DIR%" rmdir /s /q "%BACKUP_DIR%"
mkdir "%BACKUP_DIR%"

:: Archivos Python principales
for %%f in (app.py database.py calculator.py reports.py import_data.py) do (
    if exist "%SRC_DIR%%%f" (
        copy "%SRC_DIR%%%f" "%BACKUP_DIR%\" /y >nul
    ) else (
        echo        [FALTA] %%f
    )
)
copy "%SRC_DIR%requirements.txt" "%BACKUP_DIR%\" /y >nul 2>nul
copy "%SRC_DIR%.gitignore" "%BACKUP_DIR%\" /y >nul 2>nul

:: ============================================
:: 2. BASE DE DATOS
:: ============================================
echo [2/6] Copiando base de datos...
if exist "%SRC_DIR%sueldos.db" (
    copy "%SRC_DIR%sueldos.db" "%BACKUP_DIR%\" /y >nul
) else (
    echo        [ADVERTENCIA] No se encontro sueldos.db
)

:: ============================================
:: 3. CARPETAS DE DATOS
:: ============================================
echo [3/6] Copiando carpetas de datos...
if exist "%SRC_DIR%data\" (
    xcopy "%SRC_DIR%data" "%BACKUP_DIR%\data\" /y /e /i /q >nul 2>nul
)
if exist "%SRC_DIR%BACKUPS_CIERRE\" (
    xcopy "%SRC_DIR%BACKUPS_CIERRE" "%BACKUP_DIR%\BACKUPS_CIERRE\" /y /e /i /q >nul 2>nul
)

:: Archivos sueltos (Excel, PDF, CSV, JSON en raiz)
for %%x in (xlsx pdf csv json) do (
    if exist "%SRC_DIR%*.%%x" (
        for %%f in ("%SRC_DIR%*.%%x") do (
            echo %%~nf | findstr /b "~$" >nul 2>nul
            if errorlevel 1 copy "%%f" "%BACKUP_DIR%\" /y >nul 2>nul
        )
    )
)

:: ============================================
:: 4. COPIAR BATs (excepto este backup bat)
:: ============================================
echo [4/6] Copiando scripts de ejecucion...
for %%f in ("%SRC_DIR%*.bat") do (
    if /I not "%%~nxf"=="crear_backup_completo.bat" (
        copy "%%f" "%BACKUP_DIR%\" /y >nul 2>nul
    )
)

:: ============================================
:: 5. ENTORNO PYTHON PORTABLE
:: ============================================
echo [5/6] Creando entorno Python portable...
echo        (esto puede tardar un momento)

:: Buscar Python
set "PY_CMD="
if exist "%LOCALAPPDATA%\Programs\Python\Python314\python.exe" (
    set "PY_CMD=%LOCALAPPDATA%\Programs\Python\Python314\python.exe"
) else (
    where py >nul 2>nul && set "PY_CMD=py"
)
if "%PY_CMD%"=="" (
    where python >nul 2>nul && set "PY_CMD=python"
)

if "%PY_CMD%"=="" (
    echo        [ERROR] No se encontro Python. El backup se crea sin entorno portable.
    echo        En la otra PC debera instalar Python y ejecutar: pip install -r requirements.txt
    goto :skip_venv
)

:: Crear venv en el backup
%PY_CMD% -m venv "%BACKUP_DIR%\venv" >nul 2>nul
if not exist "%BACKUP_DIR%\venv\Scripts\python.exe" (
    echo        [ERROR] No se pudo crear el entorno virtual.
    goto :skip_venv
)

:: Instalar dependencias en el venv del backup
"%BACKUP_DIR%\venv\Scripts\pip.exe" install --quiet --disable-pip-version-check -r "%SRC_DIR%requirements.txt" >nul 2>nul
if errorlevel 1 (
    echo        [ADVERTENCIA] Algunas dependencias no se instalaron correctamente.
) else (
    echo        Entorno Python creado con todas las dependencias.
)

:: Crear launcher que usa el venv local
(
echo @echo off
echo cd /d "%%~dp0"
echo echo Iniciando %APP_NAME%...
echo echo.
echo.
echo :: Usar venv local si existe
echo if exist "%%~dp0venv\Scripts\python.exe" ^(
echo     "%%~dp0venv\Scripts\python.exe" -m streamlit run app.py
echo     goto :end
echo ^)
echo.
echo :: Fallback: buscar Python en el sistema
echo py -m streamlit run app.py 2^>nul
echo if %%errorlevel%%==0 goto :end
echo python -m streamlit run app.py 2^>nul
echo if %%errorlevel%%==0 goto :end
echo.
echo echo [ERROR] No se encontro Python con Streamlit.
echo echo Instala Python desde https://www.python.org/downloads/
echo echo Luego ejecuta: pip install -r requirements.txt
echo.
echo :end
echo pause
) > "%BACKUP_DIR%\INICIAR.bat"

:: Sobreescribir el iniciar_sueldos.bat tambien
copy "%BACKUP_DIR%\INICIAR.bat" "%BACKUP_DIR%\iniciar_sueldos.bat" /y >nul 2>nul

:skip_venv

:: ============================================
:: 6. COMPRIMIR EN ZIP
:: ============================================
echo [6/6] Comprimiendo backup en ZIP...
echo        (esto puede tardar unos minutos)

if exist "%ZIP_FILE%" del "%ZIP_FILE%" >nul 2>nul
powershell -NoProfile -Command "Compress-Archive -Path '%BACKUP_DIR%\*' -DestinationPath '%ZIP_FILE%' -Force" 2>nul

if exist "%ZIP_FILE%" (
    echo        ZIP creado exitosamente.
    :: Eliminar carpeta temporal
    rmdir /s /q "%BACKUP_DIR%" >nul 2>nul
) else (
    echo        [INFO] No se pudo comprimir. La carpeta queda en el Escritorio.
)

:: ============================================
:: VERIFICACION FINAL
:: ============================================
echo.
echo ==================================================
echo   VERIFICACION DEL BACKUP
echo ==================================================

set "HAY_ERROR=0"
if exist "%ZIP_FILE%" (
    echo   [OK] ZIP creado: %ZIP_FILE%
    for %%f in ("%ZIP_FILE%") do echo   [OK] Tamano: %%~zf bytes
) else if exist "%BACKUP_DIR%\app.py" (
    echo   [OK] Carpeta creada: %BACKUP_DIR%
) else (
    echo   [ERROR] No se genero el backup correctamente.
    set "HAY_ERROR=1"
)

echo.
echo ==================================================
if "%HAY_ERROR%"=="0" (
    echo   BACKUP PORTABLE COMPLETADO EXITOSAMENTE
) else (
    echo   BACKUP COMPLETADO CON ADVERTENCIAS
)
echo ==================================================
echo.
echo   Para usar en otra PC:
echo   1. Copiar el ZIP a la otra PC
echo   2. Descomprimir en cualquier carpeta
echo   3. Ejecutar INICIAR.bat
echo.
pause
