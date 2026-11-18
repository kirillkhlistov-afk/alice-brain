@echo off
setlocal
echo ============================================================
echo  alice-brain ONE CLICK: download + hotspot + auto setup
echo  When Windows asks for admin rights - press YES.
echo ============================================================
set "KIT=%USERPROFILE%\.alice-tools"
if not exist "%KIT%" mkdir "%KIT%"
set "DIR=%KIT%\oneclick"
if exist "%DIR%" rmdir /s /q "%DIR%"
echo Downloading the project (small, once per run)...
powershell -NoProfile -Command "$ProgressPreference='SilentlyContinue'; [Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -Uri 'https://github.com/kirillkhlistov-afk/alice-brain/archive/refs/heads/main.zip' -OutFile '%DIR%.zip'; Expand-Archive -Path '%DIR%.zip' -DestinationPath '%DIR%' -Force"
set "SRC=%DIR%\alice-brain-main"
if not exist "%SRC%\tools\alice_install.py" (
  echo Download failed - check internet and run this file again.
  pause
  exit /b 1
)
cd /d "%SRC%\tools"
python alice_install.py --hotspot --unlock-only %*
pause
