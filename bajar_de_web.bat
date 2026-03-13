@echo off
cd /d "%~dp0"
echo ==================================================
echo   BAJAR DATOS DESDE LA WEB
echo ==================================================
echo.
echo Esto va a descargar la ultima version del codigo
echo y datos desde GitHub a tu PC local.
echo.
echo ATENCION: Si hiciste cambios locales que no subiste,
echo se van a combinar con los de la web.
echo.
pause

echo.
echo Descargando cambios...
git pull origin master

if %errorlevel%==0 (
    echo.
    echo ==================================================
    echo   DATOS DESCARGADOS EXITOSAMENTE
    echo ==================================================
    echo Tu app local ya tiene la ultima version.
) else (
    echo.
    echo [ERROR] No se pudieron descargar los datos.
    echo Verifica tu conexion a internet.
)
echo.
pause
