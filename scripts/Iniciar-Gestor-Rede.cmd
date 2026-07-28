@echo off
setlocal
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Start-NetworkServer.ps1"
if errorlevel 1 (
    echo.
    echo Nao foi possivel iniciar o Gestor Eletrico.
    pause
)
endlocal
