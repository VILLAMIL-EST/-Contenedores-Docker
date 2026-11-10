# Preferir iniciar.cmd: no depende de ExecutionPolicy.
# Si igual desea este .ps1, ejecute:
#   powershell -NoProfile -ExecutionPolicy Bypass -File .\iniciar.ps1 -servidores 2
param(
    [ValidateSet(2, 3)]
    [int]$servidores = 3
)
$ErrorActionPreference = 'Stop'
$cmd = Join-Path -Path $PSScriptRoot -ChildPath 'iniciar.cmd'
if (-not (Test-Path -LiteralPath $cmd)) {
    throw "Falta iniciar.cmd en $PSScriptRoot"
}
$process = Start-Process -FilePath $env:ComSpec `
    -ArgumentList @('/c', "`"$cmd`" --servidores $servidores") `
    -WorkingDirectory $PSScriptRoot `
    -NoNewWindow -Wait -PassThru
if ($null -eq $process.ExitCode) { exit 1 }
exit $process.ExitCode
