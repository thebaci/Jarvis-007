@echo off
chcp 65001 >nul
title Reset dang nhap Jarvis 007
cd /d "%~dp0"
echo ==========================================
echo   RESET DANG NHAP JARVIS 007
echo   (Xoa tai khoan/mat khau -> ve bo cai dat)
echo ==========================================
echo.
.venv\Scripts\python.exe -c "import json,os; p='server/settings.json'; d=(json.load(open(p,encoding='utf-8')) if os.path.exists(p) else {}); d['auth']={'username':'','password_hash':'','salt':''}; d['setup_done']=False; json.dump(d, open(p,'w',encoding='utf-8'), ensure_ascii=False, indent=2); print('OK - da xoa mat khau.')"
echo.
echo Da reset. Bay gio:
echo   1) Chay stop-javis.bat roi start-javis.vbs (hoac de nguyen cung duoc).
echo   2) Mo lai trang -> se ra bo cai dat de tao tai khoan moi.
echo.
pause
