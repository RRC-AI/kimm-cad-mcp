@echo off
setlocal EnableExtensions
chcp 65001 >nul
pushd "%~dp0" || exit /b 1

echo Installing KIMM-CAD V26 MCP...
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0install.ps1" %*
set "result=%ERRORLEVEL%"

if not "%result%"=="0" (
    echo.
    echo Installation failed. Review the error above.
) else (
    echo.
    echo Installation completed. Restart Codex to load the MCP connection.
)
if not defined KIMM_CAD_INSTALL_NO_PAUSE pause
popd
exit /b %result%
