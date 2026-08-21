@echo off
setlocal
chcp 65001 >nul 2>&1
set "SCRIPT_DIR=%~dp0"
set "LAUNCHER=%SCRIPT_DIR%run_flowdocs.py"

if not exist "%LAUNCHER%" (
  echo [ERROR] Le fichier run_flowdocs.py est introuvable.
  echo Placez run.bat et run_flowdocs.py dans le meme dossier.
  pause
  exit /b 1
)

where py.exe >nul 2>&1
if not errorlevel 1 goto RUN_WITH_PY

where python.exe >nul 2>&1
if not errorlevel 1 goto RUN_WITH_PYTHON

where python >nul 2>&1
if not errorlevel 1 goto RUN_WITH_PYTHON_CMD

echo [ERROR] Python est introuvable dans PATH.
echo Installez Python 3.11 ou plus recent puis rouvrez Windows.
pause
exit /b 1

:RUN_WITH_PY
py -3 "%LAUNCHER%"
goto FINISH

:RUN_WITH_PYTHON
python.exe "%LAUNCHER%"
goto FINISH

:RUN_WITH_PYTHON_CMD
python "%LAUNCHER%"

:FINISH
set "EXIT_CODE=%ERRORLEVEL%"
if not "%EXIT_CODE%"=="0" pause
exit /b %EXIT_CODE%
