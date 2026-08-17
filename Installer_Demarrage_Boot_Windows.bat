@echo off
title Installation - Demarrage au boot de Windows - Thermostat UAM
color 0A

echo ============================================================
echo   DEMARRAGE AUTOMATIQUE AU BOOT DE WINDOWS
echo   (avant meme la connexion a une session)
echo ============================================================
echo.

REM Ce script doit etre execute en tant qu'Administrateur.
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo XXX Ce script doit etre execute en tant qu'ADMINISTRATEUR.
    echo.
    echo     Clic droit sur ce fichier -^> "Executer en tant qu'administrateur"
    echo.
    pause
    exit /b 1
)

cd /d "%~dp0"
set "LAUNCHER=%~dp0Demarrer_Thermostat_UAM.bat"
set "TASK_NAME=ThermostatUAM_AutoStart"

if not exist "%LAUNCHER%" (
    echo XXX ERREUR : Demarrer_Thermostat_UAM.bat introuvable dans ce dossier.
    echo     Placez ce script dans le meme dossier que Demarrer_Thermostat_UAM.bat
    echo.
    pause
    exit /b 1
)

echo Suppression d'une ancienne tache existante ^(si presente^)...
schtasks /delete /tn "%TASK_NAME%" /f >nul 2>&1

echo Creation de la tache planifiee...
schtasks /create /tn "%TASK_NAME%" ^
    /tr "\"%LAUNCHER%\"" ^
    /sc onstart ^
    /delay 0000:05 ^
    /ru "SYSTEM" ^
    /rl highest ^
    /f

if errorlevel 1 (
    echo.
    echo XXX La creation de la tache a echoue. Voir le message ci-dessus.
    pause
    exit /b 1
)

echo.
echo ============================================================
echo   TERMINE !
echo   Thermostat UAM demarrera desormais automatiquement des
echo   l'allumage de l'ordinateur, meme sans connexion a une
echo   session Windows.
echo   ^(delai de 30 secondes apres le demarrage, pour laisser
echo    Windows et le reseau finir de s'initialiser^)
echo ============================================================
echo.
echo Pour VERIFIER que la tache existe : ouvrez le "Planificateur
echo de taches" Windows ^(tapez "planificateur" dans le menu
echo Demarrer^), rubrique "Bibliotheque du Planificateur de taches",
echo cherchez "%TASK_NAME%".
echo.
echo Pour ANNULER le demarrage automatique, executez la commande
echo suivante dans une invite de commandes en Administrateur :
echo   schtasks /delete /tn "%TASK_NAME%" /f
echo.
pause