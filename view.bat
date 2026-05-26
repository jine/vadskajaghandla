@echo off
REM Regenererar prices.html fran prices.json och oppnar i webblasaren.
REM Anvand efter en kornining for att titta pa resultatet.
setlocal
cd /d "%~dp0"
python view_prices.py --open
