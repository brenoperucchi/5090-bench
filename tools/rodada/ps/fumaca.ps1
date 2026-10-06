# Teste de fumaça da produção: status, model_path e uma geração curta.
param([string]$Cfg = "E:\strata-0139\strata-swift-iq3_xxs.json")
$ProgressPreference = "SilentlyContinue"
$h = @{}; $k = (Get-Content $Cfg -Raw | ConvertFrom-Json).api_key; if ($k) { $h = @{ Authorization = "Bearer " + $k } }   # nunca impresso
try {
  $s = (Invoke-WebRequest -UseBasicParsing -TimeoutSec 5 -Headers $h http://127.0.0.1:18199/v1/status).Content | ConvertFrom-Json
  $b = '{"messages":[{"role":"user","content":"Responda so: ok"}],"max_tokens":8,"temperature":0,"chat_template_kwargs":{"enable_thinking":false}}'
  $r = Invoke-WebRequest -UseBasicParsing -Headers $h -Method Post -ContentType 'application/json' -Body $b -TimeoutSec 60 http://127.0.0.1:18199/v1/chat/completions
  $j = $r.Content | ConvertFrom-Json
  "OK engine=$($s.engine) http=$($r.StatusCode) finish=$($j.choices[0].finish_reason)"
} catch { "FALHA $($_.Exception.Message)" }
