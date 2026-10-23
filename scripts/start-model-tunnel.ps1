param(
    [Parameter(Mandatory = $true)]
    [ValidateRange(1, 65535)]
    [int]$RemotePort,
    [string]$SshHost = 'bai-vscode',
    [ValidateRange(1, 65535)]
    [int]$LocalPort = 18000,
    [string]$IdentityFile = (Join-Path $env:USERPROFILE '.ssh\id_container'),
    [switch]$Background
)
$ErrorActionPreference = 'Stop'
if (-not (Get-Command ssh -ErrorAction SilentlyContinue)) { throw 'OpenSSH client is required.' }
if ($SshHost -notmatch '^[a-zA-Z0-9][a-zA-Z0-9._-]*$') { throw 'Use an SSH config host alias.' }
if (-not (Test-Path -LiteralPath $IdentityFile -PathType Leaf)) { throw "SSH key not found: $IdentityFile" }
$IdentityFile = (Resolve-Path -LiteralPath $IdentityFile).Path
$cache = Join-Path (Split-Path $PSScriptRoot -Parent) '.cache'
New-Item -ItemType Directory -Path $cache -Force | Out-Null
$knownHosts = Join-Path $cache 'ktcloud_known_hosts'
$stateFile = Join-Path $cache 'model-tunnel.json'
if ($Background -and (Test-Path -LiteralPath $stateFile)) {
    throw 'A managed tunnel record exists. Use stop-model-tunnel.ps1 before restarting.'
}
$listener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, $LocalPort)
try { $listener.Start() } catch { throw "Local port $LocalPort is already in use." }
finally { $listener.Stop() }
Write-Host "Model API: http://127.0.0.1:$LocalPort/v1"
$sshArgs = @('-N', '-T', '-i', $IdentityFile, '-o', 'IdentitiesOnly=yes',
    '-o', 'ExitOnForwardFailure=yes', '-o', 'ConnectTimeout=15',
    '-o', 'ServerAliveInterval=30', '-o', 'ServerAliveCountMax=3',
    '-o', "UserKnownHostsFile=$knownHosts",
    '-L', "127.0.0.1:${LocalPort}:127.0.0.1:${RemotePort}")
if ($Background) {
    if (-not (Test-Path -LiteralPath $knownHosts)) {
        throw 'First run without -Background to verify the SSH host key, then stop with Ctrl+C.'
    }
    $sshArgs += @('-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=yes', $SshHost)
    # Start-Process joins arguments on Windows. Quote paths (including those with spaces).
    $quotedArgs = $sshArgs | ForEach-Object {
        if ($_ -match '["\r\n]') { throw 'Quotes and newlines are not supported in SSH arguments.' }
        '"' + $_ + '"'
    }
    $log = Join-Path $cache 'model-tunnel.stderr.log'
    $process = Start-Process -FilePath (Get-Command ssh).Source -ArgumentList $quotedArgs `
        -WindowStyle Hidden -RedirectStandardError $log -PassThru
    @{ pid = $process.Id; local_port = $LocalPort; remote_port = $RemotePort; ssh_host = $SshHost } |
        ConvertTo-Json | Set-Content -LiteralPath $stateFile -Encoding UTF8
    Start-Sleep -Seconds 2
    $process.Refresh()
    if ($process.HasExited) {
        Remove-Item -LiteralPath $stateFile
        throw "SSH exited. Review $log (no private key is logged by this script)."
    }
    Write-Host 'Tunnel started in background. Stop with scripts/stop-model-tunnel.ps1.'
} else {
    Write-Host 'Keep this terminal open. Verify the host key if prompted. Stop with Ctrl+C.'
    & ssh @sshArgs -o StrictHostKeyChecking=ask $SshHost
    if ($LASTEXITCODE -ne 0) { throw "SSH tunnel exited with code $LASTEXITCODE" }
}
