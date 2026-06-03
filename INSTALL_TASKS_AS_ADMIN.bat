@echo off
echo Installing Investment Simulation scheduled tasks...
echo.

set PYTHON=C:\Python310\python.exe
set RUNNER=C:\Users\jack\investment_sim\runner.py
set LOGS=C:\Users\jack\investment_sim\data

:: Morning — all 6 agents, Mon-Fri 09:00
schtasks /delete /tn "InvestmentSim_Morning" /f >nul 2>&1
schtasks /create /tn "InvestmentSim_Morning" ^
  /tr "\"%PYTHON%\" \"%RUNNER%\" --mode morning >> \"%LOGS%\morning.log\" 2>&1" ^
  /sc WEEKLY /d MON,TUE,WED,THU,FRI /st 09:00 /rl HIGHEST /f
if %errorlevel%==0 (echo   OK  InvestmentSim_Morning  [Mon-Fri 09:00]) else (echo   FAIL InvestmentSim_Morning)

:: Afternoon — Speculator + Emotional, Mon-Fri 15:45
schtasks /delete /tn "InvestmentSim_Afternoon" /f >nul 2>&1
schtasks /create /tn "InvestmentSim_Afternoon" ^
  /tr "\"%PYTHON%\" \"%RUNNER%\" --mode afternoon >> \"%LOGS%\afternoon.log\" 2>&1" ^
  /sc WEEKLY /d MON,TUE,WED,THU,FRI /st 15:45 /rl HIGHEST /f
if %errorlevel%==0 (echo   OK  InvestmentSim_Afternoon [Mon-Fri 15:45]) else (echo   FAIL InvestmentSim_Afternoon)

:: Crypto — Speculator crypto-only, every 4 hours 24/7
schtasks /delete /tn "InvestmentSim_Crypto" /f >nul 2>&1
schtasks /create /tn "InvestmentSim_Crypto" ^
  /tr "\"%PYTHON%\" \"%RUNNER%\" --mode crypto >> \"%LOGS%\crypto.log\" 2>&1" ^
  /sc HOURLY /mo 4 /st 00:00 /rl HIGHEST /f
if %errorlevel%==0 (echo   OK  InvestmentSim_Crypto   [every 4h 24/7]) else (echo   FAIL InvestmentSim_Crypto)

echo.
echo Done. Tasks installed:
echo   09:00 Mon-Fri  - All 6 agents (morning)
echo   15:45 Mon-Fri  - Speculator + Emotional (pre-close)
echo   every 4 hours  - Speculator crypto-only (24/7)
echo.
pause
