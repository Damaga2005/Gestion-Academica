# Reconstruye el ejecutable de escritorio (Fase 6).
# Uso: .\build.ps1
# Requiere haber instalado las dependencias de requirements-dev.txt en el venv.

$ErrorActionPreference = "Stop"

$proyecto = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $proyecto

if (Test-Path ".\venv\Scripts\Activate.ps1") {
    . .\venv\Scripts\Activate.ps1
}

pyinstaller escritorio.spec --noconfirm --clean

Write-Host ""
Write-Host "Listo. Ejecutable generado en dist\GestionAcademicaGREELEC.exe" -ForegroundColor Green
Write-Host "La primera vez que se ejecute creara alli mismo academico.db y la carpeta documentos\ (con el seed real cargado automaticamente)." -ForegroundColor Yellow
