# Cria, ao lado da config dada, a variante determinística (--pcie-frac 0 --prompt-cache 0 --adapt-swaps 0,
# STRATA_IQ_MT_MIN=1) e devolve o caminho. Não altera a config original.
param([string]$Cfg)
$c = Get-Content $Cfg -Raw | ConvertFrom-Json
$l = [System.Collections.ArrayList]@($c.args)
$i = $l.IndexOf('--pcie-frac'); if ($i -ge 0) { $l[$i+1] = '0' } else { $l.AddRange(@('--pcie-frac','0')) }
foreach ($k in '--prompt-cache','--adapt-swaps') { $j = $l.IndexOf($k); if ($j -ge 0) { $l[$j+1] = '0' } else { $l.AddRange(@($k,'0')) } }
$c.args = $l.ToArray()
if (-not $c.env) { $c | Add-Member env ([pscustomobject]@{}) -Force }
$c.env | Add-Member STRATA_IQ_MT_MIN '1' -Force
$out = $Cfg -replace '\.json$', '-det.json'
$c.log = $out -replace '\.json$', '.log'
$c | ConvertTo-Json -Depth 5 | Set-Content $out -Encoding UTF8
$out
