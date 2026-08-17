@echo off
title Client Tunnel - Thermostat UAM
color 0B

REM Se placer dans le dossier ngrok-tunnel (la ou se trouve client.py)
cd /d "%~dp0"

set TUNNEL_SERVER_URL=wss://uam-thermostat.dspcentric.com
set FLASK_URL=http://localhost:5000

echo ============================================================
echo   CLIENT TUNNEL - Demarrage avec redemarrage automatique
echo ============================================================
echo.

:boucle
python client.py

echo.
echo ============================================================
echo Le client tunnel s'est arrete (code %errorlevel%).
echo Redemarrage automatique dans 5 secondes...
echo ============================================================
timeout /t 5 /nobreak
goto boucle
