# Принимаем параметры из Python (или командной строки)
param(
    [Parameter(Mandatory=$true)]
    [string]$Ver,          # Например: "8.3.25.1234"

    [Parameter(Mandatory=$true)]
    [string]$IsX64String   # "true" или "false" (строкой надежнее при вызове извне)
)

# Преобразуем строку в boolean
$IsX64 = [System.Convert]::ToBoolean($IsX64String)

# --- Блок авто-повышения прав (Self-Elevation) ---
$Id = [Security.Principal.WindowsIdentity]::GetCurrent()
$Pr = [Security.Principal.WindowsPrincipal]$Id
if (-not $Pr.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    # Формируем строку аргументов, чтобы передать их в новую админскую сессию
    $NewArgs = "-NoProfile -ExecutionPolicy Bypass -File `"$($MyInvocation.MyCommand.Definition)`" -Ver `"$Ver`" -IsX64String `"$IsX64String`""
    
    Start-Process powershell -Verb RunAs -ArgumentList $NewArgs
    Exit
}

# --- Основная логика ---
try {
    # 1. Определяем корневой путь и имя оснастки
    if ($IsX64) {
        $Root = $env:ProgramFiles
        $MscName = "1CV8 Servers (x86-64).msc"
        $ArchName = "x64"
    } else {
        $Root = ${env:ProgramFiles(x86)}
        # Если запущено на 32-битной Windows, переменная (x86) пуста, берем просто ProgramFiles
        if ([string]::IsNullOrEmpty($Root)) { $Root = $env:ProgramFiles }
        $MscName = "1CV8 Servers.msc"
        $ArchName = "x86"
    }

    $Dll = Join-Path $Root "1cv8\$Ver\bin\radmin.dll"

    # 2. Ищем файл .msc (проверяем оба места, т.к. Common общий)
    $MscPath1 = Join-Path $env:ProgramFiles "1cv8\common\$MscName"
    $MscPath2 = Join-Path ${env:ProgramFiles(x86)} "1cv8\common\$MscName"

    if (Test-Path $MscPath1) { $Msc = $MscPath1 }
    elseif (Test-Path $MscPath2) { $Msc = $MscPath2 }
    else { throw "Файл консоли '$MscName' не найден в папках common!" }

    # 3. Регистрация
    if (-not (Test-Path $Dll)) { throw "DLL не найдена: $Dll" }
    
    Write-Host "Версия: $Ver ($ArchName)" -ForegroundColor Yellow
    Write-Host "Регистрация: $Dll" -ForegroundColor Cyan
    Start-Process "regsvr32.exe" -ArgumentList "/s `"$Dll`"" -Wait

    # 4. Запуск
    Write-Host "Запуск: $Msc" -ForegroundColor Green
    Start-Process "mmc.exe" -ArgumentList "`"$Msc`""

} catch {
    Write-Error $_.Exception.Message
    Read-Host "Нажмите Enter для выхода..."
}
