# utils/serial_utils.py - Fonctions utilitaires pour la gestion des ports série
import serial
import serial.tools.list_ports
import time
import sys
import os

def verifier_port_disponible(nom_port):
    """Vérifie si un port série est disponible"""
    try:
        port_serie = serial.Serial(nom_port, timeout=1)
        port_serie.close()
        return True
    except Exception:
        return False

def verifier_port_existe(nom_port):
    """Vérifie si un port physique existe toujours"""
    try:
        ports = serial.tools.list_ports.comports()
        ports_existants = [port.device for port in ports]
        return nom_port in ports_existants
    except Exception as e:
        print(f"Erreur vérification ports: {e}")
        return False

def obtenir_ports_disponibles():
    """Récupère les ports Arduino disponibles (version robuste)"""
    ports_trouves = []
    
    try:
        # Tentative 1: Utiliser la méthode standard
        for port in serial.tools.list_ports.comports():
            description_majuscules = port.description.upper() if port.description else ""
            identifiant_materiel_majuscules = port.hwid.upper() if port.hwid else ""
            
            indicateurs_arduino = [
                'ARDUINO', 'CH340', 'CH341', 'CP210', 'FT232', 'USB2.0-SERIAL', 
                'ACM', 'TTYACM', '/DEV/TTYACM', 'SERIAL', 'UART', 'USB'
            ]
            
            # Détection spécifique pour /dev/ttyACM sous Linux
            est_tty_acm = 'ACM' in port.device.upper() or 'TTYACM' in port.device.upper()
            
            est_arduino = any(indicateur in description_majuscules for indicateur in indicateurs_arduino)
            est_arduino_hwid = any(indicateur in identifiant_materiel_majuscules for indicateur in indicateurs_arduino)
            
            if est_arduino or est_arduino_hwid or est_tty_acm:
                port_disponible = verifier_port_disponible(port.device)
                ports_trouves.append({
                    'port': port.device,
                    'description': port.description or f"Port {port.device}",
                    'en_utilisation': not port_disponible
                })
                print(f"Port Arduino détecté: {port.device} - {port.description} (Disponible: {port_disponible})")
        
        # Tentative 2: Recherche directe des ports COM (Windows) / tty (Linux)
        if sys.platform == 'win32':
            import re
            import winreg
            
            try:
                # Lire les ports COM depuis le registre Windows
                key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\DEVICEMAP\SERIALCOMM")
                index = 0
                while True:
                    try:
                        value = winreg.EnumValue(key, index)
                        if value[0].startswith("\\Device\\"):
                            port_com = value[1]
                            if not any(p['port'] == port_com for p in ports_trouves):
                                port_disponible = verifier_port_disponible(port_com)
                                ports_trouves.append({
                                    'port': port_com,
                                    'description': f"Port série {port_com}",
                                    'en_utilisation': not port_disponible
                                })
                                print(f"Port COM détecté via registre: {port_com}")
                        index += 1
                    except OSError:
                        break
                    except Exception:
                        break
                winreg.CloseKey(key)
            except Exception as e:
                print(f"Lecture registre Windows: {e}")
        
        else:
            # Linux/Mac: chercher les ports /dev/tty*
            import glob
            patterns = ['/dev/ttyUSB*', '/dev/ttyACM*', '/dev/ttyS*', '/dev/cu.*']
            for pattern in patterns:
                for port_path in glob.glob(pattern):
                    if not any(p['port'] == port_path for p in ports_trouves):
                        port_disponible = verifier_port_disponible(port_path)
                        ports_trouves.append({
                            'port': port_path,
                            'description': f"Port série {os.path.basename(port_path)}",
                            'en_utilisation': not port_disponible
                        })
                        print(f"Port série détecté: {port_path} (Disponible: {port_disponible})")
    
    except Exception as e:
        print(f"Erreur détection ports: {e}")
        import traceback
        traceback.print_exc()
    
    if not ports_trouves:
        print("Aucun Arduino détecté. Vérifiez la connexion USB.")
        # Afficher tous les ports disponibles pour debug
        try:
            all_ports = serial.tools.list_ports.comports()
            if all_ports:
                print("Ports détectés (non-Arduino):")
                for port in all_ports:
                    print(f"  - {port.device}: {port.description}")
        except:
            pass
    
    return ports_trouves