# Mesa Guardian v3-compact (4 cenários × 3 respostas, t=0,3, seeds 53–55) contra o servidor no ar.
# Raciocinio=true pede enable_thinking; o teto de raciocínio vem da config do servidor (reasoning_budget_tokens).
param([string]$Tag, [string]$Raciocinio = 'false', [string]$Cfg = '')
Set-Location E:\strata-bench
# chave do servidor (se a config tiver): só em variável de ambiente deste processo, nunca impressa
if ($Cfg) { $k = (Get-Content $Cfg -Raw | ConvertFrom-Json).api_key; if ($k) { $env:STRATA_API_KEY = $k } else { Remove-Item Env:STRATA_API_KEY -ErrorAction SilentlyContinue } }
$kw = if ($Raciocinio -eq 'true') { '{\"enable_thinking\": true}' } else { '{\"enable_thinking\": false}' }
$snaps = 'mfc-exec~container~36e2a6ef93dc','mfc-exec~Ryzen9~ff6b18a9aaf6','mfc-exec~MT5~d77e0f52583f','mfc-exec~Ryzen9+container~10a626094215'
foreach ($s in $snaps) {
  & E:\strata-src\.venv\Scripts\python.exe -u tools\guardian_synthesis_bench.py run --arm v3-compact --snapshot $s --endpoint http://127.0.0.1:18199/v1/chat/completions --model $Tag --temperature 0.3 --seed 53 --repeats 3 --max-tokens 12000 --timeout 900 --chat-template-kwargs $kw --confirm-inference 2>&1 | Select-String 'http=|rror' | ForEach-Object { $_.Line }
}
