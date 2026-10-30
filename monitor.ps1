Set-Location -LiteralPath $PSScriptRoot
wsl -d Ubuntu -u root -- python3 -u ./monitor.py
