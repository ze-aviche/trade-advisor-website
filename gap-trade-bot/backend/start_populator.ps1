# PowerShell script to start the trade populator
Write-Host "Starting Trade Populator..." -ForegroundColor Green

# Change to the correct directory
Set-Location -Path "C:\Users\avina\OneDrive\Documents\Projects\trade-advisor-website\gap-trade-bot\backend"

# Activate virtual environment
& "C:\Users\avina\OneDrive\Documents\Projects\trade-advisor-website\gap-trade-bot\venv\Scripts\Activate.ps1"

# Start the trade populator
Write-Host "Running populate_trades.py..." -ForegroundColor Yellow
python populate_trades.py
