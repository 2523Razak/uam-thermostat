@echo off
title Thermostat UAM - Serveur
color 0A

echo ============================================================
echo   THERMOSTAT UAM - Demarrage
echo ============================================================
echo.

REM Se placer dans le dossier ou se trouve ce fichier .bat
REM (donc le dossier racine du projet, la ou se trouve app.py)
cd /d "%~dp0"

echo Dossier du projet : %cd%
echo.
echo Lancement de l'application (Flask + tunnel)...
echo Le tunnel s'ouvrira automatiquement dans une seconde fenetre
echo apres quelques secondes.
echo.
echo NE FERMEZ PAS cette fenetre tant que vous voulez que
echo l'application reste accessible.
echo ============================================================
echo.

:boucle
python app.py

echo.
echo ============================================================
echo L'application s'est arretee (code %errorlevel%).
echo Redemarrage automatique dans 5 secondes...
echo ============================================================
timeout /t 5 /nobreak
goto boucle
