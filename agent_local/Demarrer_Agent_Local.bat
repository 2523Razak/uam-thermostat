@echo off
title Thermostat UAM - Agent Local (cartes Arduino)
color 0B

echo ============================================================
echo   THERMOSTAT UAM - Agent local (gestion des cartes Arduino)
echo ============================================================
echo.

REM Se placer dans le dossier ou se trouve ce fichier .bat
cd /d "%~dp0"

echo Dossier de l'agent : %cd%
echo.

if not exist config_agent.json (
    echo Aucun config_agent.json trouve, copie du modele...
    copy config_agent.example.json config_agent.json
    echo.
    echo IMPORTANT : ouvrez config_agent.json et renseignez :
    echo   - server_url  : l'URL de votre site hebergee sur Render/Railway
    echo   - agent_token : le meme jeton que AGENT_SHARED_SECRET cote serveur
    echo.
    pause
)

echo Verification des dependances Python...
pip install -r requirements_agent.txt >nul 2>&1

echo.
echo Lancement de l'agent (Ctrl+C pour arreter)...
echo Cette fenetre doit rester ouverte pour que les cartes Arduino
echo restent utilisables sur le site.
echo ============================================================
echo.

:boucle
python agent_arduino.py

echo.
echo ============================================================
echo L'agent s'est arrete (code %errorlevel%). Redemarrage dans 5s...
echo (Fermez cette fenetre pour arreter definitivement)
echo ============================================================
timeout /t 5 /nobreak >nul
goto boucle
