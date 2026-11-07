# setup-windows.ps1: instalacion del editor en Windows (Intel o AMD Ryzen).
# Instala con winget lo que falte (Git para tener Git Bash, ffmpeg, Node y uv) y despues
# corre setup.sh dentro de Git Bash, igual que en Mac.
# Uso, desde PowerShell en la carpeta del editor (o doble clic en instalar-windows.bat):
#   powershell -ExecutionPolicy Bypass -File setup-windows.ps1
# Este archivo va sin acentos: PowerShell 5 lee los .ps1 sin BOM con la codificacion del sistema.

$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot

function Ok($texto) { Write-Host "  OK  $texto" -ForegroundColor Green }
function Falla($texto) { Write-Host "  !!  $texto" -ForegroundColor Red }

function Actualizar-Path {
    # winget deja las rutas nuevas en el registro; esta ventana todavia no las ve.
    $maquina = [Environment]::GetEnvironmentVariable("Path", "Machine")
    $usuario = [Environment]::GetEnvironmentVariable("Path", "User")
    $env:Path = "$maquina;$usuario"
}

function Tiene($comando) { return [bool](Get-Command $comando -ErrorAction SilentlyContinue) }

function Node-AlDia {
    # hyperframes 0.7.110 (el motor de render) declara node >= 22.
    if (-not (Tiene "node")) { return $false }
    try { return ([int]((& node -v).TrimStart("v").Split(".")[0]) -ge 22) } catch { return $false }
}

function Instalar-SiFalta([scriptblock]$listo, $paquete, $nombre) {
    if (& $listo) { Ok $nombre; return }
    Write-Host "  ..  instalando $nombre"
    # Si ya hay una version vieja, winget install la actualiza.
    winget install --id $paquete --exact --silent --accept-source-agreements --accept-package-agreements | Out-Null
    Actualizar-Path
    if (& $listo) { Ok $nombre }
    else { Falla "no se pudo instalar $nombre. Cierra esta ventana, abre otra y vuelve a ejecutar este archivo."; exit 1 }
}

function Buscar-GitBash {
    $rutas = @("$env:ProgramFiles\Git\bin\bash.exe", "${env:ProgramFiles(x86)}\Git\bin\bash.exe",
               "$env:LOCALAPPDATA\Programs\Git\bin\bash.exe")
    foreach ($r in $rutas) { if ($r -and (Test-Path $r)) { return $r } }
    $git = Get-Command git -ErrorAction SilentlyContinue
    if ($git) {
        $candidato = Join-Path (Split-Path (Split-Path $git.Source)) "bin\bash.exe"
        if (Test-Path $candidato) { return $candidato }
    }
    return $null
}

Write-Host ""
Write-Host "Editor de video con IA, de Devia Consulting: instalacion en Windows"
Write-Host ""

if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
    Falla "Falta winget. Instala 'App Installer' desde la Microsoft Store y vuelve a ejecutar este archivo."
    exit 1
}

Instalar-SiFalta { Tiene "git" } "Git.Git" "Git (trae Git Bash)"
Instalar-SiFalta { Tiene "ffmpeg" } "Gyan.FFmpeg" "ffmpeg"
Instalar-SiFalta { Node-AlDia } "OpenJS.NodeJS.LTS" "Node 22 o mas nuevo"
Instalar-SiFalta { Tiene "uv" } "astral-sh.uv" "uv"

$bash = Buscar-GitBash
if (-not $bash) { Falla "No encontre Git Bash (bash.exe). Reinstala Git desde https://git-scm.com/downloads/win"; exit 1 }

# Sin comillas ni cd: PowerShell 5.1 no escapa las comillas internas al pasarlas a un
# programa, y con un espacio en la ruta (C:\Users\Maria Perez) el cd se partia en dos.
# Bash arranca en la carpeta actual, que ya es la del editor (Set-Location de arriba).
& $bash setup.sh
exit $LASTEXITCODE
