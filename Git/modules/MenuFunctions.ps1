# modules/MenuFunctions.ps1

function Show-Menu {
    <#
    .SYNOPSIS
    Отображение главного меню
    #>
    Clear-Host
    Write-Host "=== Git Menu ===" -ForegroundColor Cyan
    Write-Host "1. Добавить, закоммитить и отправить изменения (add, commit, push)" -ForegroundColor Green
    Write-Host "2. Показать историю коммитов (git log)" -ForegroundColor Green
    Write-Host "3. Показать детали коммита (git show)" -ForegroundColor Green
    Write-Host "Q. Выход" -ForegroundColor Yellow
    Write-Host ""
}
