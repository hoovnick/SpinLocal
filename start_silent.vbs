' SpinLocal Silent Launcher
' Runs launcher.py completely hidden — no console window, nothing in taskbar.
' This is what Task Scheduler calls at logon.
' To stop SpinLocal: open Task Manager -> Details -> kill pythonw.exe processes.

Dim scriptDir
scriptDir = CreateObject("Scripting.FileSystemObject").GetParentFolderName(WScript.ScriptFullName)

Set sh = CreateObject("WScript.Shell")
sh.Run "pythonw """ & scriptDir & "\launcher.py""", 0, False
