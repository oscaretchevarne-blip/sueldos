@echo off
cd /d "%~dp0"
echo ==================================================
echo   SUBIR DATOS LOCALES A LA WEB
echo ==================================================
echo.
echo Esto va a subir tu base de datos y archivos locales
echo a GitHub, lo cual actualiza la app web automaticamente.
echo.
pause

echo.
echo Subiendo cambios...
git add sueldos.db data/ BACKUPS_CIERRE/ app.py calculator.py database.py import_data.py reports.py requirements.txt iniciar_sueldos.bat crear_backup_completo.bat .gitignore
git commit -m "Actualizacion de datos %DATE% %TIME%"
git push origin master

if %errorlevel%==0 (
    echo.
    echo ==================================================
    echo   DATOS SUBIDOS EXITOSAMENTE
    echo ==================================================
    echo La app web se actualizara en unos minutos.
) else (
    echo.
    echo [ERROR] No se pudieron subir los datos.
    echo Verifica tu conexion a internet.
)
echo.
pause
