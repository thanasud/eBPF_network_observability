$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
Write-Host 'Open http://localhost:8765 after Network Lab starts. Keep this window open.'
wsl -d Ubuntu -u root -- python3 -u ./app.py
