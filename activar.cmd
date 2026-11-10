@echo off
rem Alias de iniciar.cmd (misma entrada Windows).
cd /d "%~dp0" || exit /b 1
call "%~dp0iniciar.cmd" %*
exit /b %ERRORLEVEL%
