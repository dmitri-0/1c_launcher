# modules/GitFunctions.ps1

function Select-FilesToAdd {
    <#
    .SYNOPSIS
    Выбор файлов для добавления в коммит
    #>
    
    # Получаем список измененных файлов
    $statusLines = git status --porcelain
    
    if ([string]::IsNullOrEmpty($statusLines)) {
        return $null
    }
    
    # Парсим вывод git status --porcelain
    $files = @()
    foreach ($line in $statusLines) {
        if ($line.Length -gt 3) {
            $filename = $line.Substring(3).Trim()
            if ($filename) {
                $files += $filename
            }
        }
    }
    
    if ($files.Count -eq 0) {
        return $null
    }
    
    Write-Host "`nИзмененные файлы:" -ForegroundColor Cyan
    for ($i = 0; $i -lt $files.Count; $i++) {
        Write-Host "  $($i + 1). $($files[$i])" -ForegroundColor Yellow
    }
    
    Write-Host "`nВарианты:" -ForegroundColor Cyan
    Write-Host "1. Добавить все файлы (git add .)" -ForegroundColor Green
    Write-Host "2. Выбрать конкретные файлы" -ForegroundColor Green
    Write-Host "0. Отмена" -ForegroundColor Red
    
    $choice = Read-Host "`nВаш выбор"
    
    switch ($choice) {
        '1' {
            return @{
                Mode = 'all'
                Files = $files
            }
        }
        '2' {
            Write-Host "`nВведите номера файлов через запятую (например: 1,3,5) или диапазон (например: 1-3):" -ForegroundColor Cyan
            $selection = Read-Host "Номера"
            
            $selectedFiles = @()
            $parts = $selection -split ','
            
            foreach ($part in $parts) {
                $part = $part.Trim()
                if ($part -match '^(\d+)-(\d+)$') {
                    $start = [int]$matches[1] - 1
                    $end = [int]$matches[2] - 1
                    for ($i = $start; $i -le $end; $i++) {
                        if ($i -ge 0 -and $i -lt $files.Count) {
                            $selectedFiles += $files[$i]
                        }
                    }
                }
                elseif ($part -match '^\d+$') {
                    $index = [int]$part - 1
                    if ($index -ge 0 -and $index -lt $files.Count) {
                        $selectedFiles += $files[$index]
                    }
                }
            }
            
            if ($selectedFiles.Count -gt 0) {
                Write-Host "`nВыбраны файлы:" -ForegroundColor Green
                $selectedFiles | ForEach-Object { Write-Host "  $_" -ForegroundColor Yellow }
                return @{
                    Mode = 'selected'
                    Files = $selectedFiles
                }
            }
            else {
                Write-Host "Файлы не выбраны" -ForegroundColor Red
                return $null
            }
        }
        '0' {
            return $null
        }
        default {
            Write-Host "Неверный выбор" -ForegroundColor Red
            return $null
        }
    }
}

function Git-PushChanges {
    <#
    .SYNOPSIS
    Добавление, коммит и push изменений
    .PARAMETER CommitMessage
    Сообщение коммита
    #>
    param([string]$CommitMessage)
    
    try {
        # Проверка наличия изменений
        $status = git status --porcelain
        if ([string]::IsNullOrEmpty($status)) {
            Write-Host "Нет изменений для коммита (working tree clean)" -ForegroundColor Yellow
            return
        }

        # Выбор файлов для добавления
        $selection = Select-FilesToAdd
        
        if ($null -eq $selection) {
            Write-Host "Операция отменена" -ForegroundColor Yellow
            return
        }

        # Формирование сообщения по умолчанию с учетом файлов
        if ([string]::IsNullOrEmpty($CommitMessage)) {
            $date = Get-Date -Format "yyyy-MM-dd HH:mm"
            $user = $env:USERNAME
            $computer = $env:COMPUTERNAME
            $branch = git branch --show-current 2>$null
            
            # Создаем многострочное сообщение
            $titleLine = "Update from $user@$computer | $date | $branch"
            $filesList = ($selection.Files | ForEach-Object { "- $_" }) -join "`n"
            
            $CommitMessage = @($titleLine, "", "Измененные файлы:", $filesList)
        }

        Write-Host "`nДобавление изменений..." -ForegroundColor Cyan
        
        if ($selection.Mode -eq 'all') {
            git add .
        }
        else {
            foreach ($file in $selection.Files) {
                Write-Host "  Добавление: $file" -ForegroundColor Gray
                git add $file
                if ($LASTEXITCODE -ne 0) { 
                    throw "Ошибка при добавлении файла: $file"
                }
            }
        }
        
        if ($LASTEXITCODE -ne 0) { throw "Ошибка при выполнении git add" }

        Write-Host "Создание коммита..." -ForegroundColor Cyan
        
        # Если сообщение - массив, используем multiple -m
        if ($CommitMessage -is [Array]) {
            $commitArgs = @()
            foreach ($line in $CommitMessage) {
                $commitArgs += "-m"
                $commitArgs += $line
            }
            git commit @commitArgs
        }
        else {
            git commit -m $CommitMessage
        }
        
        if ($LASTEXITCODE -ne 0) { 
            throw "Ошибка при выполнении git commit" 
        }

        Write-Host "Отправка изменений..." -ForegroundColor Cyan
        $pushOutput = git push 2>&1
        
        if ($LASTEXITCODE -eq 0) {
            Write-Host "Успешно выполнено!" -ForegroundColor Green
        } elseif ($pushOutput -match "Everything up-to-date") {
            Write-Host "Всё актуально (Everything up-to-date)" -ForegroundColor Yellow
        } else {
            throw "Ошибка при выполнении git push: $pushOutput"
        }
    }
    catch {
        Write-Error $_.Exception.Message
    }
}

function Show-GitLog {
    Write-Host "`nПоследние 20 коммитов:" -ForegroundColor Cyan
    $commits = git log --oneline -20
    
    for ($i = 0; $i -lt $commits.Count; $i++) {
        $commitLine = $commits[$i]
        
        # Парсим строку коммита
        if ($commitLine -match '^([a-f0-9]+)\s+(.+)$') {
            $hash = $matches[1]
            $message = $matches[2]
            
            # Номер - Cyan, Хеш - Yellow, Сообщение - White
            Write-Host "$($i + 1). " -ForegroundColor Cyan -NoNewline
            Write-Host "$hash " -ForegroundColor Yellow -NoNewline
            Write-Host "$message" -ForegroundColor White
        }
        else {
            Write-Host "$($i + 1). $commitLine"
        }
    }
    Write-Host ""
}

function Show-CommitDetails {
    Write-Host "`nПоследние 10 коммитов:" -ForegroundColor Cyan
    $commits = git log --oneline -10
    
    # Выводим пронумерованный и раскрашенный список
    for ($i = 0; $i -lt $commits.Count; $i++) {
        $commitLine = $commits[$i]
        
        # Парсим строку коммита: "хеш сообщение"
        if ($commitLine -match '^([a-f0-9]+)\s+(.+)$') {
            $hash = $matches[1]
            $message = $matches[2]
            
            # Номер коммита - Cyan
            Write-Host "$($i + 1). " -ForegroundColor Cyan -NoNewline
            
            # Хеш - Yellow
            Write-Host "$hash " -ForegroundColor Yellow -NoNewline
            
            # Парсим сообщение на части
            if ($message -match '^(Update from .+ \| .+ \| .+)(\s+Измененные файлы:)?(.*)$') {
                $header = $matches[1]
                $files = $matches[3]
                
                # Заголовок Update - Green
                Write-Host "$header" -ForegroundColor Green -NoNewline
                
                # Файлы - Gray
                if ($files) {
                    Write-Host "$files" -ForegroundColor DarkGray
                }
                else {
                    Write-Host ""
                }
            }
            else {
                # Обычное сообщение - White
                Write-Host "$message" -ForegroundColor White
            }
        }
        else {
            # Если не удалось распарсить, выводим как есть
            Write-Host "$($i + 1). $commitLine" -ForegroundColor Yellow
        }
    }
    
    Write-Host "`nВведите номер коммита (1-$($commits.Count)) или хеш коммита:" -ForegroundColor Cyan
    $choice = Read-Host "Выбор"
    
    if ($choice -match '^\d+$') {
        $index = [int]$choice - 1
        if ($index -ge 0 -and $index -lt $commits.Count) {
            $commitLine = $commits[$index]
            # Извлекаем хеш (первое слово до пробела)
            if ($commitLine -match '^[^\s]+') {
                $commitHash = $matches[0]
                Write-Host "`n=== Детали коммита $commitHash ===" -ForegroundColor Cyan
                git show --stat $commitHash
            }
        }
        else {
            Write-Host "Неверный номер" -ForegroundColor Red
        }
    }
    else {
        # Предполагаем, что введен хеш
        Write-Host "`n=== Детали коммита $choice ===" -ForegroundColor Cyan
        git show --stat $choice
    }
    Write-Host ""
}
