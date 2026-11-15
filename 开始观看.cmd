@echo off
setlocal DisableDelayedExpansion
chcp 65001 >nul
cd /d "%~dp0"
if exist "%~dp0瞳界星渊.exe" (
    start "" "%~dp0瞳界星渊.exe" %*
    exit /b 0
)
if exist "%~dp0dist\EyeBeyond.exe" (
    start "" "%~dp0dist\EyeBeyond.exe" %*
    exit /b 0
)
where py >nul 2>&1
if not errorlevel 1 goto use_py
where python >nul 2>&1
if not errorlevel 1 goto use_python
echo 请下载 Windows 免安装版，解压后双击“瞳界星渊.exe”即可观看。
echo https://github.com/Lcpt7/eye-beyond-the-universe/releases/latest
pause
exit /b 1
:use_py
py -3 "%~dp0start_here.py" %*
goto finished
:use_python
python "%~dp0start_here.py" %*
:finished
set "EYE_LAUNCH_EXIT=%errorlevel%"
if not "%EYE_LAUNCH_EXIT%"=="0" pause
exit /b %EYE_LAUNCH_EXIT%
