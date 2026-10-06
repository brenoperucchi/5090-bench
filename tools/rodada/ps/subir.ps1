# Sobe o server.py da pasta da versão com a config dada e espera o modelo carregar (até 240 s).
param([string]$Cfg, [string]$Log)
$ProgressPreference = "SilentlyContinue"
$cj = Get-Content $Cfg -Raw | ConvertFrom-Json
$root = Split-Path (Split-Path $cj.exe)
$h = @{}; if ($cj.api_key) { $h = @{ Authorization = "Bearer " + $cj.api_key } }   # nunca impresso
$cmd = "cmd.exe /c `"cd /d $root && E:\strata-src\.venv\Scripts\python.exe serve\server.py --engine strata --config $Cfg --port 18199 > $Log 2>&1`""
Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{ CommandLine = $cmd; CurrentDirectory = $root } | Out-Null
$t0 = Get-Date
while (((Get-Date) - $t0).TotalSeconds -lt 240) {
  try { if ((Invoke-WebRequest -UseBasicParsing -TimeoutSec 3 -Headers $h http://127.0.0.1:18199/v1/models).Content -match 'loaded') { "pronto"; exit 0 } } catch {}
  Start-Sleep 5
}
"nao subiu"; exit 1
