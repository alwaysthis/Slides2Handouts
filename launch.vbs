Option Explicit
Dim sh, fs, root, exe, rc
Set sh = CreateObject("WScript.Shell")
Set fs = CreateObject("Scripting.FileSystemObject")
root = fs.GetParentFolderName(WScript.ScriptFullName)
sh.CurrentDirectory = root
If WScript.Arguments.Named.Exists("shortcuts") Then
    Dim folder, link
    For Each folder In Array(root, sh.SpecialFolders("Desktop"))
        Set link = sh.CreateShortcut(folder & "\Slides2Handouts.lnk")
        link.TargetPath = sh.ExpandEnvironmentStrings("%SystemRoot%\System32\wscript.exe")
        link.Arguments = Chr(34) & WScript.ScriptFullName & Chr(34)
        link.WorkingDirectory = root
        link.IconLocation = root & "\assets\handouts.ico,0"
        link.Save
    Next
    WScript.Quit 0
End If
exe = root & "\.venv\Scripts\pythonw.exe"
If Not fs.FileExists(exe) Then exe = "pythonw.exe"
On Error Resume Next
rc = sh.Run(Chr(34) & exe & Chr(34) & " main.py", 0, True)
If Err.Number <> 0 Then MsgBox Err.Description, 16, "Slides2Handouts"
If rc <> 0 Then MsgBox "Startup failed. See startup.log or check Python installation.",16,"Slides2Handouts"
