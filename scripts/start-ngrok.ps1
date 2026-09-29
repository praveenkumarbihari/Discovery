# Public URL for Discovery Engine (http://127.0.0.1:8765)
# 1. Sign up: https://dashboard.ngrok.com/signup
# 2. Copy authtoken: https://dashboard.ngrok.com/get-started/your-authtoken
# 3. Set once:  $env:NGROK_AUTHTOKEN = "your-token"
#    Or add NGROK_AUTHTOKEN=... to project .env and run from repo root.

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$ngrok = Join-Path $root "tools\ngrok\ngrok.exe"

if (-not (Test-Path $ngrok)) {
    Write-Host "Run from repo after ngrok binary is installed at tools\ngrok\ngrok.exe"
    exit 1
}

$envFile = Join-Path $root ".env"
if (Test-Path $envFile) {
    Get-Content $envFile | ForEach-Object {
        if ($_ -match '^\s*NGROK_AUTHTOKEN\s*=\s*(.+)\s*$') {
            $env:NGROK_AUTHTOKEN = $matches[1].Trim().Trim('"').Trim("'")
        }
    }
}

if (-not $env:NGROK_AUTHTOKEN) {
    Write-Host "Missing NGROK_AUTHTOKEN. Add it to .env or `$env:NGROK_AUTHTOKEN, then re-run."
    exit 1
}

& $ngrok config add-authtoken $env:NGROK_AUTHTOKEN 2>$null
Write-Host "Tunneling http://127.0.0.1:8765 — public URL at http://127.0.0.1:4040"
& $ngrok http 8765
