@echo off
echo ============================================================
echo  alice-brain: HOTSPOT install (laptop replaces the router)
echo  Press YES in the Windows admin window when it appears.
echo ============================================================
python "%~dp0alice_install.py" --hotspot %*
pause
