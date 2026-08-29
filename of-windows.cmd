@echo off
REM Atajo para instalaciones existentes. Implementación: deploy\windows\launcher.cmd
call "%~dp0deploy\windows\launcher.cmd" %*
exit /b %ERRORLEVEL%
