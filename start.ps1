# Start the Japanese dictionary site (FastAPI + uvicorn)
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Web = Join-Path $Root "web"
$VenvUvicorn = Join-Path $Web ".venv\Scripts\uvicorn.exe"
$VenvPython = Join-Path $Web ".venv\Scripts\python.exe"

# --- 词典库检查 ---------------------------------------------------------
$Db = Join-Path $Root "jmdict.db"
if (-not (Test-Path $Db)) {
  if (Test-Path (Join-Path $Web "jmdict.db")) {
    $Db = Join-Path $Web "jmdict.db"
  } else {
    Write-Host ""
    Write-Host "找不到 jmdict.db —— 查词和语法会显示「加载失败」。" -ForegroundColor Yellow
    Write-Host "先运行一次数据准备（会自动下载词库，约 30MB）：" -ForegroundColor Yellow
    Write-Host "    python setup_data.py" -ForegroundColor Cyan
    Write-Host ""
    $ans = Read-Host "仍然启动？[y/N]"
    if ($ans -notmatch '^[yY]') { exit 1 }
  }
}

Set-Location $Web

if (-not (Test-Path $VenvUvicorn)) {
  Write-Host "首次启动：创建虚拟环境并安装依赖（约 1-2 分钟，请稍候）…" -ForegroundColor Cyan
  if (-not (Test-Path $VenvPython)) {
    python -m venv .venv
  }
  & (Join-Path $Web ".venv\Scripts\pip.exe") install -r requirements.txt
}

# --- 端口检测 -----------------------------------------------------------
$Port = 8765
function Test-PortBusy([int]$p) {
  return [bool](Get-NetTCPConnection -LocalPort $p -State Listen -ErrorAction SilentlyContinue)
}
if (Test-PortBusy $Port) {
  $alt = 8766
  while ($alt -lt 8800 -and (Test-PortBusy $alt)) { $alt++ }
  Write-Host ""
  Write-Host "端口 $Port 已被占用（可能是上一次没关掉的实例）。" -ForegroundColor Yellow
  if ($alt -lt 8800) {
    Write-Host "改用端口 $alt 启动。" -ForegroundColor Yellow
    $Port = $alt
  } else {
    Write-Host "8766-8799 也都占用了。请关掉占用端口的程序，或手动指定端口：" -ForegroundColor Yellow
    Write-Host "    .\.venv\Scripts\uvicorn.exe main:app --port 9000" -ForegroundColor Cyan
    exit 1
  }
}

Write-Host ""
Write-Host "打开 http://127.0.0.1:$Port/   （Ctrl+C 停止）" -ForegroundColor Green
Write-Host "本地讲解需要 Ollama：ollama list 应能看到 qwen2.5:7b" -ForegroundColor DarkGray
Write-Host ""

& $VenvUvicorn main:app --host 127.0.0.1 --port $Port --reload
