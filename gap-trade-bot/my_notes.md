Windows commands: 

.\venv\Scripts\Activate.ps1

taskkill /PID XXXX /F

Get-Content logs\gap_trade_backend_all.log | Select-String -Pattern "Polygon|API|timeout|connection|

Connection|network|Network" | Select-Object -Last 20

Get-Process node -ErrorAction SilentlyContinue | Stop-Process -Force

Get-Process -Name "*chrome*", "*firefox*", "*edge*", "*safari*" -ErrorAction SilentlyContinue |Stop-Process -Force

=====================================================================================================================
positions

price_check_interval: 1 second
position_discovery_interval: 30 seconds
config_check_interval: 300 seconds (5 minutes)

=====================================================================================================================