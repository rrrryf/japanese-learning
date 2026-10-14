# Start Rao Japanese dict site (FastAPI + uvicorn)
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Web = Join-Path $Root "web"
$VenvUvicorn = Join-Path $Web ".venv\Scripts\uvicorn.exe"
$VenvPython = Join-Path $Web ".venv\Scripts\python.exe"

Set-Location $Web

if (-not (Test-Path $VenvUvicorn)) {
  Write-Host "Creating venv and installing deps..."
  if (-not (Test-Path $VenvPython)) {
    python -m venv .venv
  }
  & (Join-Path $Web ".venv\Scripts\pip.exe") install -r requirements.txt
}

Write-Host "Opening http://127.0.0.1:8765/  (Ctrl+C to stop)"
Write-Host "Tip: ollama list  should show tinyswallow for local explain"
& $VenvUvicorn main:app --host 127.0.0.1 --port 8765 --reload
