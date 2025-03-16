@echo off
cd /d "%~dp0"
call venv\Scripts\activate
for /f "delims=" %%i in ('where python') do @echo Virtual environment activated: %%i & goto :break
:break
cmd /k
