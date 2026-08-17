@echo off
title Installation - Verification visible a la connexion
color 0A

echo ============================================================
echo   AJOUT DE LA VERIFICATION VISIBLE A LA CONNEXION
echo ============================================================
echo.

cd /d "%~dp0"

set "SCRIPT=%~dp0Verifier_Statut_Connexion.bat"
set "STARTUP_FOLDER=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"
set "SHORTCUT=%STARTUP_FOLDER%\Statut Thermostat UAM.lnk"

if not exist "%SCRIPT%" (
    echo XXX ERREUR : Verifier_Statut_Connexion.bat introuvable dans ce dossier.
    pause
    exit /b 1
)

set "VBS_TEMP=%TEMP%\creer_raccourci_statut.vbs"
(
echo Set objShell = CreateObject^("WScript.Shell"^)
echo Set objShortcut = objShell.CreateShortcut^("%SHORTCUT%"^)
echo objShortcut.TargetPath = "%SCRIPT%"
echo objShortcut.WorkingDirectory = "%~dp0"
echo objShortcut.WindowStyle = 7
echo objShortcut.Description = "Verification du statut de Thermostat UAM"
echo objShortcut.Save
) > "%VBS_TEMP%"

cscript //nologo "%VBS_TEMP%"
del "%VBS_TEMP%"

if exist "%SHORTCUT%" (
    echo.
    echo ============================================================
    echo   TERMINE !
    echo   A chaque connexion a Windows, une page s'ouvrira dans
    echo   votre navigateur pour confirmer si Thermostat UAM
    echo   fonctionne bien ^(avec les logos^), ou vous prevenir
    echo   si ce n'est pas le cas.
    echo ============================================================
) else (
    echo XXX Le raccourci n'a pas pu etre cree.
)

echo.
pause
