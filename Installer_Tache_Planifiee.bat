@echo off
REM ============================================================
REM Installe une tache planifiee Windows qui lance
REM Demarrer_Thermostat_UAM.bat au demarrage de Windows,
REM totalement independante de VS Code.
REM A executer UNE FOIS, en tant qu'administrateur
REM (clic droit -> Executer en tant qu'administrateur)
REM ============================================================

set SCRIPT_DIR=%~dp0
set BAT_PATH=%SCRIPT_DIR%Demarrer_Thermostat_UAM.bat

echo Creation de la tache planifiee "ThermostatUAM"...
echo Script cible : %BAT_PATH%
echo.

schtasks /create /tn "ThermostatUAM" ^
  /tr "\"%BAT_PATH%\"" ^
  /sc onstart ^
  /ru "%USERNAME%" ^
  /rl highest ^
  /f

if %errorlevel% equ 0 (
    echo.
    echo ============================================================
    echo Tache creee avec succes !
    echo Elle se lancera automatiquement a chaque demarrage de Windows,
    echo independamment de VS Code ou de toute session ouverte.
    echo ============================================================
) else (
    echo.
    echo ERREUR : la creation a echoue. Avez-vous lance ce script
    echo en tant qu'administrateur ? (clic droit -^> Executer en tant
    echo qu'administrateur)
)

pause
