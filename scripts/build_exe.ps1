# Builda o frontend e empacota a MeshBench num executável one-dir + .zip.
# Uso: powershell -ExecutionPolicy Bypass -File scripts/build_exe.ps1
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot

# Python do venv local quando existe; senão o do PATH — é assim que o CI roda,
# onde não há .venv
$py = Join-Path $root ".venv/Scripts/python.exe"
if (-not (Test-Path $py)) { $py = "python" }

# $ErrorActionPreference não pega falha de executável externo: sem checar o
# código de saída, um npm/pyinstaller quebrado seguia adiante em silêncio
function Assert-ExitOk($what) {
    if ($LASTEXITCODE -ne 0) { throw "$what falhou (exit $LASTEXITCODE)" }
}

Write-Host "==> build do frontend"
# entra em web/ em vez de usar `npm --prefix`: com --prefix, o npm instala no
# diretório certo mas lê o package.json do diretório ATUAL em parte das versões
# (quebrou no runner, passou na máquina local com npm 11)
Push-Location (Join-Path $root "web")
try {
    npm install
    Assert-ExitOk "npm install"
    npm run build
    Assert-ExitOk "npm run build"
} finally {
    Pop-Location
}

Write-Host "==> PyInstaller (one-dir)"
# o .spec usa caminhos relativos (src/...), então roda a partir da raiz
Push-Location $root
try {
    & $py -m PyInstaller "$root/meshbench.spec" --noconfirm `
        --distpath "$root/dist" --workpath "$root/build"
    Assert-ExitOk "PyInstaller"
} finally {
    Pop-Location
}

Write-Host "==> compactando .zip"
# versão vem do pacote — um lugar só, para o zip nunca discordar da tag
$version = (& $py -c "import meshbench; print(meshbench.__version__)").Trim()
Assert-ExitOk "leitura da versão"
if (-not $version) { throw "não consegui ler meshbench.__version__" }
$zip = Join-Path $root "dist/MeshBench-$version.zip"
if (Test-Path $zip) { Remove-Item $zip }
Compress-Archive -Path (Join-Path $root "dist/MeshBench/*") -DestinationPath $zip
Write-Host "pronto: $zip"
