' ============================================================
'  QUASAR MINING - double-click me. No black window appears.
'  The mining window opens directly.
' ============================================================
Set fso = CreateObject("Scripting.FileSystemObject")
scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)
Set sh = CreateObject("WScript.Shell")
sh.Run "powershell -NoProfile -ExecutionPolicy Bypass -File """ & scriptDir & "\QuasarMiner.ps1""", 0, False
