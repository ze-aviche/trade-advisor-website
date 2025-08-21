@echo off
echo Starting Trade Populator...
cd /d "C:\Users\avina\OneDrive\Documents\Projects\trade-advisor-website\gap-trade-bot\backend"
call "C:\Users\avina\OneDrive\Documents\Projects\trade-advisor-website\gap-trade-bot\venv\Scripts\activate.bat"
python populate_trades.py
pause
