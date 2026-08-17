@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"

REM Attendre un peu que le service (lance au demarrage par le
REM Planificateur de taches) ait le temps de repondre
timeout /t 5 /nobreak >nul

set "STATUT=EN LIGNE"
set "COULEUR=#1ea95e"
set "MESSAGE=Thermostat UAM fonctionne normalement."

REM Verifie si Flask repond sur le port local
powershell -Command "try { $r = Invoke-WebRequest -Uri http://localhost:5000/api/health -UseBasicParsing -TimeoutSec 5; exit 0 } catch { exit 1 }" >nul 2>&1

if errorlevel 1 (
    set "STATUT=HORS LIGNE"
    set "COULEUR=#e53935"
    set "MESSAGE=L'application ne repond pas. Verifiez demarrage_log.txt et ngrok-tunnel\tunnel_log.txt pour comprendre pourquoi, ou double-cliquez sur Demarrer_Thermostat_UAM.bat pour la lancer manuellement."
)

set "PAGE=%TEMP%\thermostat_statut.html"

(
echo ^<!DOCTYPE html^>
echo ^<html lang="fr"^>
echo ^<head^>
echo ^<meta charset="UTF-8"^>
echo ^<title^>Thermostat UAM - Statut^</title^>
echo ^<style^>
echo   body { font-family: Segoe UI, Arial, sans-serif; background: #f4f6f8; margin:0; padding:40px; text-align:center; }
echo   .carte { background: white; max-width: 480px; margin: 0 auto; padding: 32px; border-radius: 16px; box-shadow: 0 4px 20px rgba^(0,0,0,0.1^); }
echo   .logos { display:flex; justify-content:center; gap:16px; margin-bottom:20px; }
echo   .logos img { height:64px; width:64px; border-radius:50%%; object-fit:cover; box-shadow: 0 2px 8px rgba^(0,0,0,0.15^); }
echo   h1 { font-size: 20px; color:#222; margin: 8px 0; }
echo   .badge { display:inline-block; padding:8px 20px; border-radius:20px; color:white; font-weight:bold; background: !COULEUR!; margin: 12px 0; }
echo   p { color:#555; font-size:14px; line-height:1.5; }
echo   .heure { color:#999; font-size:12px; margin-top:20px; }
echo ^</style^>
echo ^</head^>
echo ^<body^>
echo   ^<div class="carte"^>
echo     ^<div class="logos"^>
echo       ^<img src="file:///%~dp0static/image/thermostat.png" onerror="this.style.display='none'"^>
echo       ^<img src="file:///%~dp0static/image/uam.jpg" onerror="this.style.display='none'"^>
echo       ^<img src="file:///%~dp0static/image/fast.jpg" onerror="this.style.display='none'"^>
echo     ^</div^>
echo     ^<h1^>Thermostat UAM^</h1^>
echo     ^<div class="badge"^>!STATUT!^</div^>
echo     ^<p^>!MESSAGE!^</p^>
echo     ^<div class="heure"^>Verifie le %date% a %time%^</div^>
echo   ^</div^>
echo ^</body^>
echo ^</html^>
) > "%PAGE%"

start "" "%PAGE%"
