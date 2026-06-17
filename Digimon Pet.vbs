Option Explicit

Dim shell, fso, scriptDir, logPath, command, args, i, exitCode

Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)
shell.CurrentDirectory = scriptDir
shell.Environment("PROCESS")("DIGIMON_PET_SILENT") = "1"

If Not fso.FolderExists(fso.BuildPath(scriptDir, ".local")) Then
    fso.CreateFolder(fso.BuildPath(scriptDir, ".local"))
End If

logPath = fso.BuildPath(scriptDir, ".local\launcher-windows.log")

args = ""
For i = 0 To WScript.Arguments.Count - 1
    args = args & " " & Quote(WScript.Arguments(i))
Next

command = "cmd.exe /c " & Chr(34) & Chr(34) & fso.BuildPath(scriptDir, "Digimon Pet.bat") & Chr(34) & _
    args & " > " & Chr(34) & logPath & Chr(34) & " 2>&1" & Chr(34)

exitCode = shell.Run(command, 0, True)
If exitCode <> 0 Then
    MsgBox "Digimon Pet failed to start. See:" & vbCrLf & logPath, vbExclamation, "Digimon Pet"
End If

Function Quote(value)
    Quote = Chr(34) & Replace(value, Chr(34), Chr(34) & Chr(34)) & Chr(34)
End Function
