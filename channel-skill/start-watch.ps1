# CHANNEL SKILL. Смена в Телеграме, один вход.
#
# Запуск, строка целиком:
#   powershell -ExecutionPolicy Bypass -File .\start-watch.ps1
#
# Проверить доступы:  powershell -ExecutionPolicy Bypass -File .\start-watch.ps1 doctor
# Войти заново:      powershell -ExecutionPolicy Bypass -File .\start-watch.ps1 login
#
# Сам находит Python, сам ставит telethon, сам спрашивает номер один раз и
# дальше держит смену. Второй запуск сразу выходит на смену: вход уже сохранён.

$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$tools = Join-Path $here "channel-skill\tools"
$secrets = Join-Path $here "secrets"

$env:PYTHONIOENCODING = "utf-8"
$env:PYTHONUTF8 = "1"
$env:CHANNEL_SECRETS = $secrets
try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch { }

function Stop-Here($text) {
    Write-Host ""
    Write-Host $text
    if ($Host.Name -eq "ConsoleHost") { Read-Host "Enter чтобы закрыть" | Out-Null }
    exit 1
}

# --- ключи из secrets\watch.env в окружение ---
$envFile = Join-Path $secrets "watch.env"
if (Test-Path -LiteralPath $envFile) {
    foreach ($line in Get-Content -LiteralPath $envFile -Encoding UTF8) {
        $row = ("" + $line).Trim()
        if ($row -eq "" -or $row.StartsWith("#")) { continue }
        $i = $row.IndexOf("=")
        if ($i -lt 1) { continue }
        $key = $row.Substring(0, $i).Trim()
        $value = $row.Substring($i + 1).Trim().Trim('"')
        if ($value -ne "") { [Environment]::SetEnvironmentVariable($key, $value, "Process") }
    }
}

# --- Python ---
$exe = $null
$pre = @()
foreach ($name in @("python", "py", "python3")) {
    $cmd = Get-Command $name -ErrorAction SilentlyContinue
    if (-not $cmd) { continue }
    $probeArgs = @()
    if ($name -eq "py") { $probeArgs = @("-3") }
    $probe = & $cmd.Source @probeArgs "-c" "import sys; print(sys.version_info[0])" 2>$null
    if ($LASTEXITCODE -eq 0 -and ("" + $probe).Trim() -eq "3") {
        $exe = $cmd.Source
        $pre = $probeArgs
        break
    }
}
if (-not $exe) {
    Stop-Here "Не нашёл Python 3. Поставь его с python.org и отметь галку Add Python to PATH, потом запусти этот файл снова."
}

# --- разбор слов после имени файла ---
$mode = "serve"
$rest = @()
foreach ($a in $args) {
    $key = ("" + $a).ToLower().TrimStart("-", "/")
    if ($key -eq "doctor") { $mode = "doctor" }
    elseif ($key -eq "login") { $mode = "login" }
    elseif ($key -eq "setup") { $mode = "setup" }
    else { $rest += $a }
}

$bridge = Join-Path $tools "tg.py"
$watch = Join-Path $tools "tg_watch.py"
if (-not (Test-Path -LiteralPath $bridge)) {
    Stop-Here "Рядом нет папки channel-skill\tools. Положи этот файл в корень поставки."
}

if ($mode -eq "doctor") {
    & $exe @pre $bridge "doctor"
    Write-Host ""
    & $exe @pre $watch "--doctor"
    exit $LASTEXITCODE
}

if ($mode -eq "login") {
    & $exe @pre $bridge "login" "--force"
    exit $LASTEXITCODE
}

& $exe @pre $bridge "setup"
if ($LASTEXITCODE -ne 0) {
    Stop-Here "Подключение не доведено до конца. В строках выше сказано, чего не хватает."
}
if ($mode -eq "setup") { exit 0 }

& $exe @pre $watch @rest
exit $LASTEXITCODE
