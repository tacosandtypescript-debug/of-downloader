@echo off
REM Alias de deploy\windows\launcher.cmd.
call "%~dp0launcher.cmd" %*
exit /b %ERRORLEVEL%
