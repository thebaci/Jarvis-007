@echo off
chcp 65001 >nul
title Khoi dong Jarvis 007
cd /d "%~dp0"

echo Bat Jarvis 007 chay NEN - khong con cua so den (port 7777)...
REM Viec tat instance cu + chay server AN giao het cho start-javis.vbs (cua so an hoan toan).
REM Log ghi vao server\javis.log (mo file do neu can xem loi). Tat server: stop-javis.bat.
wscript //nologo start-javis.vbs

echo.
echo Da bat. Cho ~10 giay roi mo http://localhost:7777 va bam Ctrl+Shift+R.
echo (Tat server: chay stop-javis.bat. Xem loi: mo file server\javis.log)
timeout /t 4 >nul
