# git-push.ps1
param(
    [Alias("m")]
    [string]$Message
)

# Загрузка модулей через dot sourcing
$scriptPath = Split-Path -Parent $MyInvocation.MyCommand.Path
. "$scriptPath\modules\Config.ps1"
. "$scriptPath\modules\GitFunctions.ps1"
. "$scriptPath\modules\MenuFunctions.ps1"

# Проверка наличия Git
if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    Write-Error "Git не найден в системе"
    exit 1
}

# Если передан параметр -m, сразу выполнить push (все файлы)
if (-not [string]::IsNullOrEmpty($Message)) {
    $status = git status --porcelain
    if ([string]::IsNullOrEmpty($status)) {
        Write-Host "Нет изменений для коммита" -ForegroundColor Yellow
        exit 0
    }
    
    git add .
    git commit -m $Message
    git push
    exit 0
}

# Интерактивное меню
do {
    Show-Menu
    $choice = Read-Host "Выберите действие"
    
    switch ($choice) {
        '1' {
            $customMessage = Read-Host "Введите сообщение коммита (Enter для автоматического)"
            Git-PushChanges -CommitMessage $customMessage
            Write-Host "`nНажмите Enter для продолжения..."
            Read-Host
        }
        '2' {
            Show-GitLog
            Write-Host "Нажмите Enter для продолжения..."
            Read-Host
        }
        '3' {
            Show-CommitDetails
            Write-Host "Нажмите Enter для продолжения..."
            Read-Host
        }
        'Q' {
            Write-Host "Выход..." -ForegroundColor Cyan
            return
        }
        default {
            Write-Host "Неверный выбор. Попробуйте снова." -ForegroundColor Red
            Start-Sleep -Seconds 1
        }
    }
} until ($choice -eq 'Q')
