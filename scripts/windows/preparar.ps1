# Bootstrap Windows de la practica (invocado con -ExecutionPolicy Bypass desde .cmd).
# No requiere Set-ExecutionPolicy permanente. No modifica iniciar.sh.
[CmdletBinding()]
param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$Passthrough = @()
)

$ErrorActionPreference = 'Stop'
$Root = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
Set-Location -LiteralPath $Root

$VenvPython = Join-Path $Root '.venv\Scripts\python.exe'
$Requirements = Join-Path $Root 'requirements-cli.txt'
$Launcher = Join-Path $Root 'launcher.py'
$Informes = Join-Path $Root 'informes'

function Write-Step([string]$Message) { Write-Host "[*] $Message" -ForegroundColor Cyan }
function Write-Warn([string]$Message) { Write-Host "[!] $Message" -ForegroundColor Yellow }
function Write-Err([string]$Message) { Write-Host "[x] $Message" -ForegroundColor Red }

function Test-IsAdmin {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($identity)
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Update-SessionPath {
    $machine = [Environment]::GetEnvironmentVariable('Path', 'Machine')
    $user = [Environment]::GetEnvironmentVariable('Path', 'User')
    $parts = @()
    if ($machine) { $parts += $machine }
    if ($user) { $parts += $user }

    $candidates = @(
        (Join-Path $env:ProgramFiles 'Docker\Docker\resources\bin'),
        (Join-Path $env:ProgramFiles 'Docker\Docker'),
        (Join-Path $env:LOCALAPPDATA 'Programs\DockerDesktop\resources\bin'),
        (Join-Path $env:LOCALAPPDATA 'Programs\Docker\Docker\resources\bin'),
        (Join-Path $env:LOCALAPPDATA 'Programs\Python\Python312'),
        (Join-Path $env:LOCALAPPDATA 'Programs\Python\Python312\Scripts'),
        (Join-Path $env:LOCALAPPDATA 'Programs\Python\Python311'),
        (Join-Path $env:LOCALAPPDATA 'Programs\Python\Python311\Scripts'),
        (Join-Path $env:ProgramFiles 'Python312'),
        (Join-Path $env:ProgramFiles 'Python311')
    )
    foreach ($dir in $candidates) {
        if ($dir -and (Test-Path -LiteralPath $dir)) {
            $parts = @($dir) + $parts
        }
    }
    $env:Path = ($parts -join ';')
}

function Get-CommandPath([string]$Name) {
    $cmd = Get-Command $Name -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    return $null
}

function Find-PythonExe {
    foreach ($name in @('py', 'python')) {
        $path = Get-CommandPath $name
        if (-not $path) { continue }
        try {
            if ($name -eq 'py') {
                $exe = & py -3 -c "import sys; print(sys.executable)" 2>$null
            } else {
                $exe = & $path -c "import sys; print(sys.executable)" 2>$null
            }
            if ($exe -and (Test-Path -LiteralPath $exe.Trim())) {
                return $exe.Trim()
            }
        } catch { }
    }
    $guesses = @(
        (Join-Path $env:LOCALAPPDATA 'Programs\Python\Python312\python.exe'),
        (Join-Path $env:LOCALAPPDATA 'Programs\Python\Python311\python.exe'),
        (Join-Path $env:ProgramFiles 'Python312\python.exe'),
        (Join-Path $env:ProgramFiles 'Python311\python.exe')
    )
    foreach ($guess in $guesses) {
        if (Test-Path -LiteralPath $guess) { return $guess }
    }
    return $null
}

function Test-PythonVersion([string]$Exe) {
    & $Exe -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)"
    return ($LASTEXITCODE -eq 0)
}

function Install-WingetPackage([string]$Id, [string]$Label) {
    if (-not (Get-CommandPath 'winget')) {
        throw "winget no esta disponible. Instale $Label manualmente y vuelva a ejecutar iniciar.cmd"
    }
    Write-Step "Instalando $Label con winget ($Id)..."
    & winget install -e --id $Id --accept-package-agreements --accept-source-agreements
    if ($LASTEXITCODE -ne 0) {
        throw "winget no pudo instalar $Id (codigo $LASTEXITCODE)"
    }
    Update-SessionPath
}

function Ensure-Python {
    Update-SessionPath
    $python = Find-PythonExe
    if ($python -and (Test-PythonVersion $python)) {
        Write-Step "Python OK: $python"
        return $python
    }
    if ($python) {
        Write-Warn "Python encontrado pero < 3.11: $python"
    } else {
        Write-Warn 'No se encontro Python 3.11+ en PATH ni en rutas habituales.'
    }
    $answer = Read-Host 'Instalar Python 3.12 con winget ahora? [S/N]'
    if ($answer -notmatch '^(S|s|Y|y|SI|si)$') {
        throw 'Instale Python 3.11+ (marque Add python.exe to PATH) y reejecute iniciar.cmd'
    }
    Install-WingetPackage 'Python.Python.3.12' 'Python 3.12'
    Update-SessionPath
    $python = Find-PythonExe
    if (-not $python -or -not (Test-PythonVersion $python)) {
        throw 'Python se instalo, pero esta terminal aun no lo ve. Cierre la terminal, abra una nueva y ejecute iniciar.cmd'
    }
    Write-Step "Python OK tras instalacion: $python"
    return $python
}

function Test-WslPresent {
    $wsl = Get-CommandPath 'wsl'
    if (-not $wsl) { $wsl = Join-Path $env:SystemRoot 'System32\wsl.exe' }
    if (-not (Test-Path -LiteralPath $wsl)) { return $false }
    try {
        $output = & $wsl --status 2>&1 | Out-String
        if ($LASTEXITCODE -eq 0) { return $true }
        if ($output -match 'no tiene|not installed|not enabled|no esta instalado') { return $false }
        # wsl existe; --version suele funcionar aunque no haya distro
        $null = & $wsl --version 2>&1
        return ($LASTEXITCODE -eq 0)
    } catch {
        return $false
    }
}

function Ensure-Wsl {
    if (Test-WslPresent) {
        Write-Step 'WSL detectado.'
        try { & wsl --update | Out-Null } catch { }
        return
    }

    Write-Warn 'Docker Desktop necesita WSL 2. En este equipo WSL no esta listo.'
    Write-Host 'Se va a intentar: wsl --install --no-distribution (requiere administrador y luego reiniciar).'
    $answer = Read-Host 'Instalar/activar WSL ahora? [S/N]'
    if ($answer -notmatch '^(S|s|Y|y|SI|si)$') {
        throw 'Active WSL 2 (PowerShell Admin: wsl --install --no-distribution), reinicie e intente de nuevo.'
    }

    if (-not (Test-IsAdmin)) {
        Write-Step 'Abriendo PowerShell elevado para instalar WSL...'
        $cmd = 'wsl --install --no-distribution; if ($LASTEXITCODE -ne 0) { wsl --update }; Write-Host ""; Write-Host "Si Windows lo pide, reinicie el PC. Luego ejecute iniciar.cmd otra vez."; pause'
        Start-Process -FilePath 'powershell.exe' -Verb RunAs -ArgumentList @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-Command', $cmd) | Out-Null
        Write-Warn 'Tras aceptar el UAC y completar WSL, REINICIE Windows y vuelva a ejecutar iniciar.cmd'
        exit 2
    }

    Write-Step 'Instalando WSL (sin distro obligatoria)...'
    & wsl --install --no-distribution
    if ($LASTEXITCODE -ne 0) {
        & wsl --update
    }
    Write-Warn 'WSL instalado/actualizado. REINICIE Windows y ejecute iniciar.cmd de nuevo.'
    exit 2
}

function Find-DockerDesktopExe {
    $candidates = @(
        (Join-Path $env:ProgramFiles 'Docker\Docker\Docker Desktop.exe'),
        (Join-Path $env:LOCALAPPDATA 'Programs\DockerDesktop\Docker Desktop.exe'),
        (Join-Path $env:LOCALAPPDATA 'Programs\Docker\Docker\Docker Desktop.exe')
    )
    foreach ($path in $candidates) {
        if (Test-Path -LiteralPath $path) { return $path }
    }
    return $null
}

function Find-DockerCli {
    Update-SessionPath
    $fromPath = Get-CommandPath 'docker'
    if ($fromPath) { return $fromPath }
    $candidates = @(
        (Join-Path $env:ProgramFiles 'Docker\Docker\resources\bin\docker.exe'),
        (Join-Path $env:LOCALAPPDATA 'Programs\DockerDesktop\resources\bin\docker.exe'),
        (Join-Path $env:LOCALAPPDATA 'Programs\Docker\Docker\resources\bin\docker.exe')
    )
    foreach ($path in $candidates) {
        if (Test-Path -LiteralPath $path) { return $path }
    }
    return $null
}

function Ensure-DockerInstalled {
    $desktop = Find-DockerDesktopExe
    $cli = Find-DockerCli
    if ($desktop -or $cli) {
        Write-Step "Docker Desktop/CLI detectado (no se reinstala)."
        if ($desktop) { Write-Host "    Desktop: $desktop" }
        if ($cli) { Write-Host "    CLI: $cli" }
        return
    }

    Write-Warn 'Docker Desktop no esta instalado.'
    $answer = Read-Host 'Instalar Docker Desktop con winget ahora? [S/N]'
    if ($answer -notmatch '^(S|s|Y|y|SI|si)$') {
        throw 'Instale Docker Desktop y reejecute iniciar.cmd'
    }
    Install-WingetPackage 'Docker.DockerDesktop' 'Docker Desktop'
    Update-SessionPath
    Start-Sleep -Seconds 3
    $desktop = Find-DockerDesktopExe
    $cli = Find-DockerCli
    if (-not $desktop -and -not $cli) {
        throw 'Docker Desktop se instalo, pero no aparece aun. Cierre la terminal, abra Docker Desktop una vez, reinicie si lo pide y ejecute iniciar.cmd'
    }
}

function Start-DockerEngine {
    $docker = Find-DockerCli
    if (-not $docker) {
        throw 'docker.exe no esta en PATH ni en Program Files / LocalAppData. Abra Docker Desktop una vez y reintente.'
    }

    # Asegura que esta sesion pueda invocar docker aunque PATH del usuario no se actualizo.
    $bin = Split-Path -Parent $docker
    if ($env:Path -notlike "*$bin*") {
        $env:Path = "$bin;$env:Path"
    }

    $info = & $docker info 2>&1 | Out-String
    if ($LASTEXITCODE -eq 0) {
        Write-Step 'Motor Docker respondiendo.'
        return $docker
    }

    $joined = $info
    if ($joined -match '(?i)wsl.*(not installed|no instalad|is not installed)|WSL 2.*(instal|install)') {
        Write-Warn 'Docker reporta que WSL no esta instalado/disponible.'
        Ensure-Wsl
        throw 'Complete la instalacion de WSL, reinicie y vuelva a ejecutar iniciar.cmd'
    }

    $desktop = Find-DockerDesktopExe
    if ($desktop) {
        $running = Get-Process -Name 'Docker Desktop' -ErrorAction SilentlyContinue
        if (-not $running) {
            Write-Step "Iniciando Docker Desktop..."
            Start-Process -FilePath $desktop | Out-Null
        } else {
            Write-Step 'Docker Desktop ya esta abierto; esperando al motor...'
        }
    } else {
        Write-Warn 'No se encontro Docker Desktop.exe; espere a que el servicio Docker arranque.'
    }

    $deadline = (Get-Date).AddSeconds(180)
    do {
        Start-Sleep -Seconds 3
        $info = & $docker info 2>&1 | Out-String
        if ($LASTEXITCODE -eq 0) {
            Write-Step 'Motor Docker listo.'
            return $docker
        }
        if ($info -match '(?i)wsl.*(not installed|no instalad|is not installed)') {
            Ensure-Wsl
            throw 'WSL requerido. Reinicie Windows y ejecute iniciar.cmd'
        }
        Write-Host '    Esperando Engine running...'
    } while ((Get-Date) -lt $deadline)

    throw "Docker no respondio a tiempo. Abra Docker Desktop, corrija avisos (WSL/virtualizacion) y reejecute iniciar.cmd. Detalle: $($info.Trim().Substring(0, [Math]::Min(400, $info.Trim().Length)))"
}

function Ensure-Venv([string]$PythonExe) {
    if (-not (Test-Path -LiteralPath $VenvPython)) {
        Write-Step "Creando .venv en $Root"
        & $PythonExe -m venv (Join-Path $Root '.venv')
        if ($LASTEXITCODE -ne 0) { throw 'No se pudo crear el entorno virtual .venv' }
    } else {
        Write-Step 'Entorno .venv ya existe.'
    }
    if (-not (Test-Path -LiteralPath $Requirements)) { throw "Falta $Requirements" }
    if (-not (Test-Path -LiteralPath $Launcher)) { throw "Falta $Launcher" }
    Write-Step 'Sincronizando dependencias CLI (Typer/Rich) en .venv...'
    & $VenvPython -m pip install -q -r $Requirements
    if ($LASTEXITCODE -ne 0) { throw 'pip no pudo instalar requirements-cli.txt' }
    if (-not (Test-Path -LiteralPath $Informes)) {
        New-Item -ItemType Directory -Path $Informes | Out-Null
    }
}

try {
    Write-Host ''
    Write-Host '=== Practica servidores Docker (Windows) ===' -ForegroundColor Green
    Write-Host "Carpeta: $Root"
    Write-Host 'Entrada recomendada: iniciar.cmd  (no necesita Set-ExecutionPolicy)'
    Write-Host ''

    Update-SessionPath
    $python = Ensure-Python
    Ensure-Wsl
    Ensure-DockerInstalled
    Update-SessionPath
    $null = Start-DockerEngine
    Ensure-Venv -PythonExe $python

    Write-Host ''
    Write-Step 'Arrancando la misma consola interactiva que en Linux...'
    Write-Host ''
    $argsToLaunch = @($Launcher) + $Passthrough
    & $VenvPython @argsToLaunch
    exit $LASTEXITCODE
} catch {
    Write-Err $_.Exception.Message
    Write-Host ''
    Write-Host 'Uso: iniciar.cmd --servidores 2'
    Write-Host '     iniciar.cmd --servidores 3'
    Write-Host 'Si PowerShell bloquea .ps1, use siempre iniciar.cmd (aplica Bypass solo a este arranque).'
    exit 1
}
