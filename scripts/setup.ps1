# Install the Python package (with dev extras) and Playwright's browsers.
# Safe to re-run. Does not read or write API keys.
$ErrorActionPreference = "Stop"
$PSNativeCommandUseErrorActionPreference = $false

$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $root

$python = $null
foreach ($name in @("python", "python3")) {
    $cmd = Get-Command $name -ErrorAction SilentlyContinue
    if ($null -ne $cmd) {
        $python = $cmd.Source
        break
    }
}
if ($null -eq $python) {
    Write-Error "python is not on PATH"
    exit 1
}

$venvPython = Join-Path $root ".venv\Scripts\python.exe"
if (-not (Test-Path $venvPython)) {
    & $python -m venv .venv
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}

& $venvPython -m pip install -e ".[dev]"
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

& $venvPython -m playwright install
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
