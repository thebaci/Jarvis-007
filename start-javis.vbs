' ============================================
'  Javis OS - run in the BACKGROUND (hidden cmd window)
'  Double-click this file (or start-javis.bat) to start the server in the background.
'  The log goes to server\javis.log. Stop with stop-javis.bat.
' ============================================
Set fso = CreateObject("Scripting.FileSystemObject")
root = fso.GetParentFolderName(WScript.ScriptFullName)
Set sh = CreateObject("WScript.Shell")

' IMPORTANT: every command does cd /d into root first - do NOT rely on the inherited working directory
' (CurrentDirectory is unreliable depending on the caller, and once made the stop step die
' silently with the error 'stop-javis.bat is not recognized').

' Stop the old instance first (hidden, wait for it to finish). Output goes to server\stop-last.log for troubleshooting.
' CALL BY ABSOLUTE PATH: the bare name "stop-javis.bat" is refused by cmd when it looks in the current folder
' when the environment has NoDefaultCurrentDirectoryInExePath (a path containing "\" is fine).
sh.Run "cmd /c cd /d """ & root & """ && call """ & root & "\stop-javis.bat"" > server\stop-last.log 2>&1", 0, True

' Run the server hidden (0 = hidden window, False = do not wait). Output -> server\javis.log
sh.Run "cmd /c cd /d """ & root & """ && .venv\Scripts\python.exe server\main.py > server\javis.log 2>&1", 0, False
