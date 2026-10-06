# Para todo servidor Strata (strata.exe e serve\server.py) no host Windows.
$ProgressPreference = "SilentlyContinue"
Get-CimInstance Win32_Process | Where-Object { $_.Name -eq 'strata.exe' -or ($_.Name -eq 'python.exe' -and $_.CommandLine -match 'serve[/\\]server\.py') } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
Start-Sleep 5
