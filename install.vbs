Option Explicit
Dim fs, sh, root, rc
Set fs = CreateObject("Scripting.FileSystemObject")
Set sh = CreateObject("WScript.Shell")
root = fs.GetParentFolderName(WScript.ScriptFullName)
sh.CurrentDirectory = root
On Error Resume Next
rc = sh.Run("python.exe -m venv .venv", 0, True)
If Err.Number <> 0 Or rc <> 0 Then
    MsgBox "Install Python 3.11+ and add python.exe to PATH.", 16
    WScript.Quit 1
End If
rc = sh.Run(""".venv\Scripts\python.exe"" -m pip install -r requirements.txt --log install.log", 0, True)
If rc <> 0 Then
    MsgBox "Installation failed. See install.log.", 16
Else
    rc = sh.Run("wscript.exe launch.vbs /shortcuts", 0, True)
    If rc <> 0 Then MsgBox "Shortcut creation failed. Use launch.vbs.", 48
    MsgBox "Ready. Double-click launch.vbs.", 64
End If
