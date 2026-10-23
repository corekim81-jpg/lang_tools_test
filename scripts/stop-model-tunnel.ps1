$ErrorActionPreference = 'Stop'
$stateFile = Join-Path (Split-Path $PSScriptRoot -Parent) '.cache\model-tunnel.json'
if (-not (Test-Path -LiteralPath $stateFile)) {
    Write-Host 'No managed background tunnel. Foreground tunnels stop with Ctrl+C.'
    return
}
$state = Get-Content -LiteralPath $stateFile -Raw | ConvertFrom-Json
$tunnelPid = [int]$state.pid
if ($tunnelPid -le 0) { throw 'Invalid tunnel PID.' }
$process = Get-CimInstance Win32_Process -Filter "ProcessId = $tunnelPid"
if ($process) {
    $forward = "127.0.0.1:$($state.local_port):127.0.0.1:$($state.remote_port)"
    # A PID can be reused: never stop a process unless it is our recorded SSH forward.
    if ($process.Name -ne 'ssh.exe' -or -not $process.CommandLine -or
        -not $process.CommandLine.Contains($forward) -or
        -not $process.CommandLine.Contains([string]$state.ssh_host)) {
        throw 'Recorded PID does not match the SSH tunnel. No process was stopped.'
    }
    Stop-Process -Id $tunnelPid -ErrorAction Stop
}
Remove-Item -LiteralPath $stateFile
Write-Host 'Managed model tunnel stopped.'
