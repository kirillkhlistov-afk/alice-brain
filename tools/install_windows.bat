@echo off
chcp 65001 >nul
echo ============================================
echo  alice-brain: авто-установка на колонку
echo ============================================
python "%~dp0alice_install.py" %*
pause
