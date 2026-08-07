# Установка Apache24-8327 как службы Windows (выполняется от администратора)
$ErrorActionPreference = 'Continue'
$log = 'C:\Apache24-8327\service_install_result.txt'

# 1. Останавливаем скрытые консольные httpd этого экземпляра (если есть)
Get-Process httpd -ErrorAction SilentlyContinue |
    Where-Object { $_.Path -like '*Apache24-8327*' } |
    Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 1

# 2. Устанавливаем службу (имя Apache24-8327, конфиг нового инстанса)
& 'C:\Apache24-8327\bin\httpd.exe' -k install -n 'Apache24-8327' -d 'C:\Apache24-8327' -f 'C:\Apache24-8327\conf\httpd.conf' 2>&1 | Out-File -FilePath $log -Encoding utf8
"install_exit=$LASTEXITCODE" | Out-File -FilePath $log -Append -Encoding utf8

# 3. Автозапуск + старт
sc.exe config Apache24-8327 start= auto | Out-File -FilePath $log -Append -Encoding utf8
sc.exe start Apache24-8327 | Out-File -FilePath $log -Append -Encoding utf8
"done" | Out-File -FilePath $log -Append -Encoding utf8
