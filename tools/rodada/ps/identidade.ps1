# Identidade da config no ar: sha do motor e da config, args/env literais, VRAM livre.
param([string]$Cfg)
$ProgressPreference = "SilentlyContinue"
$c = Get-Content $Cfg -Raw | ConvertFrom-Json
[ordered]@{
  engine_sha256 = (Get-FileHash $c.exe).Hash.ToLower()
  config_sha256 = (Get-FileHash $Cfg).Hash.ToLower()
  args = @($c.args); env = $c.env
  gpu = (nvidia-smi --query-gpu=name,driver_version --format=csv,noheader)
  vram_free_mib = [int](nvidia-smi --query-gpu=memory.free --format=csv,noheader,nounits)
} | ConvertTo-Json -Depth 4 -Compress
