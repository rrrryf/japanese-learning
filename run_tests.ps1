# 启动服务 -> 跑 API 回归测试 -> 停服务
# 用法：
#   .\run_tests.ps1              # 基础 60+ 项
#   .\run_tests.ps1 -WithAi      # 额外测一次 Ollama 讲解（需本机模型）
#   .\run_tests.ps1 -Port 9100   # 指定端口

param(
    [int]$Port = 0,
    [switch]$WithAi,
    [switch]$KeepRunning,
    [string]$Python = ""
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Web = Join-Path $Root "web"
$VenvPython = Join-Path $Web ".venv\Scripts\python.exe"
$TestScript = Join-Path $Root "tests\test_api.py"

# 词典数据里有 ⓪ 之类的字符：控制台与 Python 都按 UTF-8 走，避免 GBK 编码异常
$prevOutEnc = [Console]::OutputEncoding
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$env:PYTHONIOENCODING = "utf-8"

# -Python 可指定别的解释器（例如 CI 里用系统 Python 并已装好依赖）
if ($Python) {
    if (-not (Test-Path $Python)) {
        Write-Host "指定的解释器不存在：$Python" -ForegroundColor Red
        exit 1
    }
    $VenvPython = $Python
}

function Write-Step($text) { Write-Host "`n=== $text ===" -ForegroundColor Cyan }

# --- 前置检查 -----------------------------------------------------------
if (-not (Test-Path $VenvPython)) {
    Write-Host "找不到 web\.venv\Scripts\python.exe" -ForegroundColor Yellow
    Write-Host "先运行一次 .\start.ps1 让它建好虚拟环境，或手动：" -ForegroundColor Yellow
    Write-Host "    cd web; python -m venv .venv; .\.venv\Scripts\pip install -r requirements.txt" -ForegroundColor Cyan
    exit 1
}

$Db = Join-Path $Root "jmdict.db"
if (-not (Test-Path $Db) -and -not (Test-Path (Join-Path $Web "jmdict.db"))) {
    Write-Host "找不到 jmdict.db，测试会大量失败。" -ForegroundColor Yellow
    Write-Host "先运行：python setup_data.py" -ForegroundColor Cyan
    exit 1
}

# --- 选一个空闲端口 -----------------------------------------------------
function Test-PortBusy([int]$p) {
    return [bool](Get-NetTCPConnection -LocalPort $p -State Listen -ErrorAction SilentlyContinue)
}
if ($Port -eq 0) {
    $Port = 8899
    while ($Port -lt 8950 -and (Test-PortBusy $Port)) { $Port++ }
}
if (Test-PortBusy $Port) {
    Write-Host "端口 $Port 已被占用，换一个 -Port 试试。" -ForegroundColor Yellow
    exit 1
}

Write-Step "启动服务（端口 $Port）"
$proc = Start-Process -FilePath $VenvPython `
    -ArgumentList "-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", "$Port" `
    -WorkingDirectory $Web -PassThru -WindowStyle Hidden

$base = "http://127.0.0.1:$Port"
$ready = $false
for ($i = 0; $i -lt 40; $i++) {
    Start-Sleep -Milliseconds 500
    if ($proc.HasExited) { break }
    try {
        $r = Invoke-WebRequest -UseBasicParsing -Uri "$base/api/jlpt/counts" -TimeoutSec 2
        if ($r.StatusCode -eq 200) { $ready = $true; break }
    } catch {
        # 服务还在启动，或被 503 挡（缺词库）——都继续等
        if ($_.Exception.Response -and $_.Exception.Response.StatusCode.value__ -eq 503) {
            $ready = $true; break
        }
    }
}

if (-not $ready) {
    Write-Host "服务没有在 20 秒内就绪（进程已退出？）" -ForegroundColor Red
    if (-not $proc.HasExited) { Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue }
    exit 1
}
Write-Host "服务已就绪：$base" -ForegroundColor Green

# --- 跑测试 -------------------------------------------------------------
Write-Step "运行测试"
$testArgs = @($TestScript, "--base", $base)
if ($WithAi) { $testArgs += "--with-ai" }
& $VenvPython @testArgs
$code = $LASTEXITCODE

# --- 收尾 ---------------------------------------------------------------
if (-not $KeepRunning) {
    Write-Step "停止服务"
    if (-not $proc.HasExited) {
        Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
        Write-Host "已停止 (pid $($proc.Id))" -ForegroundColor DarkGray
    }
} else {
    Write-Host "`n服务保留运行：$base（pid $($proc.Id)）" -ForegroundColor Yellow
}

if ($code -eq 0) {
    Write-Host "`n测试通过" -ForegroundColor Green
} else {
    Write-Host "`n有失败项，见上方 FAIL 列表" -ForegroundColor Red
}
exit $code
