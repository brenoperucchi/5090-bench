# Só leitura: qual strata.exe e qual server.py estão no ar (caminho, sha256, linha de comando, início). Não mexe em nada.
$ProgressPreference = "SilentlyContinue"
$eng = Get-CimInstance Win32_Process -Filter "Name='strata.exe'" | Select-Object -First 1
$srv = Get-CimInstance Win32_Process -Filter "Name='python.exe'" | Where-Object { $_.CommandLine -like '*server.py*' } | Select-Object -First 1
$cfg = $null
if ($srv -and $srv.CommandLine -match '--config\s+"?([^"\s]+)') { $cfg = $Matches[1] }
[ordered]@{
  engine_path = $eng.ExecutablePath
  engine_sha256 = if ($eng) { (Get-FileHash $eng.ExecutablePath).Hash.ToLower() } else { $null }
  engine_args = if ($eng) { ($eng.CommandLine -replace '^"?[^"\s]+"?\s*', '') } else { $null }
  engine_started = if ($eng) { $eng.CreationDate.ToString('o') } else { $null }
  config_path = $cfg
  config_sha256 = if ($cfg -and (Test-Path $cfg)) { (Get-FileHash $cfg).Hash.ToLower() } else { $null }
} | ConvertTo-Json -Compress
