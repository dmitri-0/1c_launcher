# modules/Config.ps1
# Настройка кодировки для правильного отображения кириллицы
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8
$env:LESSCHARSET = 'UTF-8'

# Настройка git для правильного отображения кириллицы
git config --global core.quotepath false 2>$null

Write-Verbose "Конфигурация загружена"
