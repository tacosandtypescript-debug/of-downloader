@echo off
set "ROOT=%~dp0..\.."
call "%ROOT%\of-windows.cmd" %*
exit /b %ERRORLEVEL%

