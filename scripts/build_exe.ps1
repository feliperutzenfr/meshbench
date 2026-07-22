# Builda o frontend e empacota a MeshBench num executável one-dir + .zip.
# Uso: powershell -ExecutionPolicy Bypass -File scripts/build_exe.ps1
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$py = Join-Path $root ".venv/Scripts/python.exe"

Write-Host "==> build do frontend"
npm --prefix "$root/web" install
npm --prefix "$root/web" run build

Write-Host "==> PyInstaller (one-dir)"
& $py -m PyInstaller "$root/meshbench.spec" --noconfirm `
    --distpath "$root/dist" --workpath "$root/build"

Write-Host "==> compactando .zip"
$version = "0.1.0"
$zip = Join-Path $root "dist/MeshBench-$version.zip"
if (Test-Path $zip) { Remove-Item $zip }
Compress-Archive -Path (Join-Path $root "dist/MeshBench/*") -DestinationPath $zip
Write-Host "pronto: $zip"
