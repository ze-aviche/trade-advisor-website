Windows commands: 

.\venv\Scripts\Activate.ps1

taskkill /PID XXXX /F

==================================================================================================================
Grep Logs:

Get-Content logs\gap_trade_backend_all.log | Select-String -Pattern "Polygon|API|timeout|connection"

Get-Content logs\gap_trade_backend_all.log | Select-String -Pattern "target profit|stop loss"

Get-Content logs\gap_trade_backend_all.log | Select-String -Pattern "Profit target updated"

Get-Content logs\gap_trade_backend_all.log | Select-String -Pattern "panic"

Connection|network|Network" | Select-Object -Last 20

Get-Content -Path "logs\gap_trade_backend_all.log" -Wait | Select-String -Pattern "Error"

=====================================================================================================================
Process:

Get-Process node -ErrorAction SilentlyContinue | Stop-Process -Force

Get-Process -Name "*chrome*", "*firefox*", "*edge*", "*safari*" -ErrorAction SilentlyContinue |Stop-Process -Force

wmic process where "name='python.exe'" get ProcessId,CommandLine

=====================================================================================================================
positions

price_check_interval: 1 second
position_discovery_interval: 30 seconds
config_check_interval: 300 seconds (5 minutes)

=====================================================================================================================