@echo off
setlocal EnableExtensions
rem Entrada Windows equivalente a iniciar.sh.
rem No requiere Set-ExecutionPolicy: Bypass aplica solo a este arranque.
cd /d "%~dp0" || exit /b 1

set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
title Practica servidores Docker

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\windows\preparar.ps1" %*
set "CODE=%ERRORLEVEL%"

if "%CODE%"=="0" exit /b 0

echo.
if "%CODE%"=="2" (
    echo Reinicie Windows y vuelva a ejecutar: iniciar.cmd --servidores 2
) else (
    echo La practica no se inicio. Revise los mensajes anteriores.
    echo Uso: iniciar.cmd --servidores 2
    echo      iniciar.cmd --servidores 3
    echo      iniciar.cmd --detener
)
echo.
pause
exit /b %CODE%
