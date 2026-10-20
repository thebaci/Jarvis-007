# Dung Jarvis 007 - giet theo DUNG python cua venv nay (moi tien trinh cha/con), khong dua vao port/tieu de.
$killed = $false
# LUU Y: python cua venv chi la LAUNCHER - no re-exec Python goc lam tien trinh CON
# (con nay moi giu port). Vi vay chi loc theo COMMANDLINE, KHONG loc theo duong dan exe
# (se bo sot thang con vi exe cua no la Python goc, khong phai venv).
Get-CimInstance Win32_Process -Filter "Name='python.exe'" -ErrorAction SilentlyContinue | Where-Object {
  $_.CommandLine -like '*server\main.py*'
} | ForEach-Object {
  Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
  Write-Host "  - Da tat python PID $($_.ProcessId)"
  $killed = $true
}
# Phong ho: ai dang giu port 7777 (truong hop chay bang python khac / cai dat khac)
Get-NetTCPConnection -LocalPort 7777 -State Listen -ErrorAction SilentlyContinue | ForEach-Object {
  Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue
  Write-Host "  - Da tat PID $($_.OwningProcess) (chu port 7777)"
  $killed = $true
}
if (-not $killed) { Write-Host '  (Khong thay server nao dang chay)' }
exit 0
