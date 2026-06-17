Option Explicit

Dim shell, fso, scriptDir, command, args, i, waitOnReturn

Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)
shell.CurrentDirectory = scriptDir
shell.Environment("PROCESS")("DIGIMON_PET_SILENT") = "1"

If Not fso.FolderExists(fso.BuildPath(scriptDir, ".local")) Then
    fso.CreateFolder(fso.BuildPath(scriptDir, ".local"))
End If

args = ""
For i = 0 To WScript.Arguments.Count - 1
    args = args & " " & Quote(WScript.Arguments(i))
Next
waitOnReturn = WScript.Arguments.Count > 0

command = "cmd.exe /c " & Chr(34) & Chr(34) & fso.BuildPath(scriptDir, "Digimon Pet.bat") & Chr(34) & _
    args & " > " & Chr(34) & fso.BuildPath(scriptDir, ".local\launcher-windows.log") & Chr(34) & " 2>&1" & Chr(34)

shell.Run command, 0, waitOnReturn

Function Quote(value)
    Quote = Chr(34) & Replace(value, Chr(34), Chr(34) & Chr(34)) & Chr(34)
End Function
