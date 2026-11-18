@echo off
echo ============================================================
echo  alice-brain: UNLOCK ONLY (root + ADB, no brain install)
echo  Press YES in the Windows admin window when it appears.
echo ============================================================
python "%~dp0alice_install.py" --hotspot --unlock-only %*
pause
