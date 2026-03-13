@echo off
setlocal

:: --- CONFIGURACION ---
set "APP_NAME=Sistema_Sueldos"
cd /d "%~dp0"
set "SRC_DIR=%~dp0"

:: Obtener fecha y hora
for /f "tokens=*" %%a in ('powershell -Command "Get-Date -format 'yyyy-MM-dd_HHmm'"') do set "STAMP=%%a"

if "%STAMP%"=="" (
    set "STAMP=Desconocido"
)

set "BACKUP_DIR=%SRC_DIR%BACKUP_%APP_NAME%_%STAMP%"

echo ==================================================
echo   GENERADOR DE BACKUP COMPLETO PARA %APP_NAME%
echo ==================================================
echo.
echo Creando carpeta de respaldo en:
echo %BACKUP_DIR%
echo.

:: Crear carpeta principal
mkdir "%BACKUP_DIR%" 2>nul

:: ============================================
:: 1. ARCHIVOS CORE (Python, Bat, Requirements)
:: ============================================
echo [1/5] Copiando archivos del sistema...
copy "%SRC_DIR%*.py" "%BACKUP_DIR%\" /y >nul 2>nul
copy "%SRC_DIR%*.bat" "%BACKUP_DIR%\" /y >nul 2>nul
copy "%SRC_DIR%requirements.txt" "%BACKUP_DIR%\" /y >nul 2>nul

:: ============================================
:: 2. BASE DE DATOS PRINCIPAL
:: ============================================
echo [2/5] Copiando base de datos...
if exist "%SRC_DIR%sueldos.db" (
    xcopy "%SRC_DIR%sueldos.db" "%BACKUP_DIR%\" /y /k /h /r >nul
    if not exist "%BACKUP_DIR%\sueldos.db" (
        echo [ERROR CRITICO] No se pudo copiar sueldos.db!
        pause
    )
) else (
    echo [ADVERTENCIA] No se encontro sueldos.db en el origen.
)

:: ============================================
:: 3. CARPETA DATA (PDFs, Excel de datos, etc)
:: ============================================
echo [3/5] Copiando carpeta data...
if exist "%SRC_DIR%data\" (
    mkdir "%BACKUP_DIR%\data" 2>nul
    xcopy "%SRC_DIR%data\*.*" "%BACKUP_DIR%\data\" /y /k /h /r /e >nul 2>nul
) else (
    echo [INFO] No se encontro carpeta data.
)

:: ============================================
:: 4. CARPETA BACKUPS_CIERRE (respaldos de DB)
:: ============================================
echo [4/5] Copiando respaldos de cierre...
if exist "%SRC_DIR%BACKUPS_CIERRE\" (
    mkdir "%BACKUP_DIR%\BACKUPS_CIERRE" 2>nul
    xcopy "%SRC_DIR%BACKUPS_CIERRE\*.*" "%BACKUP_DIR%\BACKUPS_CIERRE\" /y /k /h /r /e >nul 2>nul
) else (
    echo [INFO] No se encontro carpeta BACKUPS_CIERRE.
)

:: ============================================
:: 5. ARCHIVOS SUELTOS (Excel, PDF en raiz)
:: ============================================
echo [5/5] Copiando archivos adicionales...
if exist "%SRC_DIR%*.xlsx" (
    for %%f in ("%SRC_DIR%*.xlsx") do (
        echo %%~nf | findstr /b "~$" >nul 2>nul
        if errorlevel 1 (
            copy "%%f" "%BACKUP_DIR%\" /y >nul 2>nul
        )
    )
)
if exist "%SRC_DIR%*.pdf" copy "%SRC_DIR%*.pdf" "%BACKUP_DIR%\" /y >nul 2>nul
if exist "%SRC_DIR%*.csv" copy "%SRC_DIR%*.csv" "%BACKUP_DIR%\" /y >nul 2>nul
if exist "%SRC_DIR%*.json" copy "%SRC_DIR%*.json" "%BACKUP_DIR%\" /y >nul 2>nul

:: ============================================
:: ELIMINAR EL PROPIO BACKUP BAT DE LA COPIA
:: (evita backups recursivos dentro del backup)
:: ============================================
del "%BACKUP_DIR%\crear_backup_completo.bat" >nul 2>nul

:: ============================================
:: INSTRUCCIONES DE INSTALACION
:: ============================================
(
echo =============================================
echo   %APP_NAME% - Backup Portatil
echo   Fecha de creacion: %DATE% %TIME%
echo =============================================
echo.
echo CONTENIDO DE ESTE BACKUP:
echo  - Archivos Python del sistema (.py^)
echo  - Base de datos principal (sueldos.db^)
echo  - Carpeta data/ con planillas y documentos
echo  - Carpeta BACKUPS_CIERRE/ con respaldos
echo  - iniciar_sueldos.bat para ejecutar el sistema
echo  - requirements.txt con las dependencias
echo.
echo =============================================
echo   INSTRUCCIONES PARA OTRA PC
echo =============================================
echo.
echo 1. Instalar Python 3.10 o superior desde:
echo    https://www.python.org/downloads/
echo    IMPORTANTE: Marcar "Add Python to PATH" durante la instalacion
echo.
echo 2. Abrir una terminal (cmd^) en esta carpeta
echo    (Click derecho en la carpeta ^> "Abrir en Terminal"^)
echo.
echo 3. Instalar dependencias ejecutando:
echo    pip install -r requirements.txt
echo.
echo 4. Ejecutar iniciar_sueldos.bat para abrir el sistema
echo.
echo =============================================
) > "%BACKUP_DIR%\LEEME_INSTRUCCIONES.txt"

:: ============================================
:: VERIFICACION FINAL
:: ============================================
echo.
echo --------------------------------------------------
echo   VERIFICACION DEL BACKUP:
echo --------------------------------------------------
set "HAY_ERROR=0"

if not exist "%BACKUP_DIR%\app.py" echo [FALTA] app.py & set "HAY_ERROR=1"
if not exist "%BACKUP_DIR%\database.py" echo [FALTA] database.py & set "HAY_ERROR=1"
if not exist "%BACKUP_DIR%\calculator.py" echo [FALTA] calculator.py & set "HAY_ERROR=1"
if not exist "%BACKUP_DIR%\reports.py" echo [FALTA] reports.py & set "HAY_ERROR=1"
if not exist "%BACKUP_DIR%\import_data.py" echo [FALTA] import_data.py & set "HAY_ERROR=1"
if not exist "%BACKUP_DIR%\sueldos.db" echo [FALTA] sueldos.db & set "HAY_ERROR=1"
if not exist "%BACKUP_DIR%\requirements.txt" echo [FALTA] requirements.txt & set "HAY_ERROR=1"
if not exist "%BACKUP_DIR%\iniciar_sueldos.bat" echo [FALTA] iniciar_sueldos.bat & set "HAY_ERROR=1"

if "%HAY_ERROR%"=="0" echo   Todos los archivos criticos estan presentes. OK

echo.
echo ==================================================
echo    RESPALDO COMPLETADO EXITOSAMENTE
echo ==================================================
echo Carpeta: %BACKUP_DIR%
echo.
echo Copia esta carpeta a un pendrive para llevarla a otra PC.
echo.
pause
