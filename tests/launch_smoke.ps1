$ErrorActionPreference = "Stop"
$launcher = Start-Process wscript.exe -ArgumentList "launch.vbs" -PassThru -WindowStyle Hidden
try {
    $deadline = (Get-Date).AddSeconds(45)
    do {
        Start-Sleep -Milliseconds 500
        $child = Get-CimInstance Win32_Process -Filter "ParentProcessId = $($launcher.Id)" | Where-Object Name -eq "pythonw.exe"
        if ($child) {
            # A virtual-environment launcher may delegate to the base interpreter.
            $interpreter = Get-CimInstance Win32_Process -Filter "ParentProcessId = $($child.ProcessId)" | Where-Object Name -eq "pythonw.exe" | Select-Object -First 1
            $gui = if ($interpreter) {Get-Process -Id $interpreter.ProcessId} else {Get-Process -Id $child.ProcessId}
            if ($gui.MainWindowTitle -like "Slides2Handouts*") {
                Write-Output $gui.MainWindowTitle
                [void]$gui.CloseMainWindow()
                if (-not $launcher.WaitForExit(10000)) {throw "Launcher did not exit"}
                exit $launcher.ExitCode
            }
        }
    } while ((Get-Date) -lt $deadline)
    throw "Main window did not appear"
} finally {
    if ($gui -and -not $gui.HasExited) {$gui.Kill()}
    if (-not $launcher.HasExited) {$launcher.Kill()}
}
