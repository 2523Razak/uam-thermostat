# agent_local/agent_arduino.py
# ============================================================================
# AGENT LOCAL - Thermostat UAM
# ============================================================================
#
# Ce programme tourne EN LOCAL, sur la machine où les cartes Arduino sont
# branchées en USB (typiquement au laboratoire, à côté du matériel).
#
# Il détecte les cartes Arduino, ouvre/ferme les ports série sur demande du
# serveur, relaie les données série reçues, et transmet les commandes reçues
# du serveur vers l'Arduino. Le serveur hébergé (Render/Railway) fait tout
# le reste : logique métier, base de données, calcul PID, interface web.
#
# Configuration : copier config_agent.example.json en config_agent.json et
# renseigner SERVER_URL et AGENT_TOKEN (doit correspondre à AGENT_SHARED_SECRET
# côté serveur).
#
# Lancement :   python agent_arduino.py
# Arrêt        : Ctrl+C
# ============================================================================

import json
import os
import sys
import time
import threading
import logging
import socket as socket_module
from datetime import datetime

import serial
import serial.tools.list_ports
import socketio

# ----------------------------------------------------------------------------
# CONFIGURATION
# ----------------------------------------------------------------------------

CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config_agent.json')

CONFIG_PAR_DEFAUT = {
    "server_url": "https://uam-thermostat.onrender.com",
    "agent_token": "change-moi-en-production",
    "agent_id": None,   # None -> utilise le nom de la machine automatiquement
    "intervalle_scan_ports_s": 5,
    "intervalle_heartbeat_s": 10,
}


def charger_config():
    if not os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
            json.dump(CONFIG_PAR_DEFAUT, f, indent=2, ensure_ascii=False)
        print(f"⚠️ Fichier de configuration créé : {CONFIG_PATH}")
        print("   Merci de le compléter (server_url, agent_token) puis relancer l'agent.")
        sys.exit(1)

    with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
        config = json.load(f)

    for cle, valeur in CONFIG_PAR_DEFAUT.items():
        config.setdefault(cle, valeur)

    if not config.get('agent_id'):
        config['agent_id'] = socket_module.gethostname()

    return config


CONFIG = charger_config()

# ----------------------------------------------------------------------------
# LOGGING (console + fichier local, pour l'entretien sur place)
# ----------------------------------------------------------------------------

LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs')
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, f"agent_{datetime.now().strftime('%Y%m')}.log")

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - [AGENT] - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(LOG_FILE, encoding='utf-8'),
    ]
)
logger = logging.getLogger(__name__)

INDICATEURS_ARDUINO = [
    'ARDUINO', 'CH340', 'CH341', 'CP210', 'FT232', 'USB2.0-SERIAL',
    'ACM', 'TTYACM', '/DEV/TTYACM'
]

# ----------------------------------------------------------------------------
# ÉTAT LOCAL
# ----------------------------------------------------------------------------

sio = socketio.Client(reconnection=True, reconnection_delay=2, reconnection_delay_max=15)
connexions_locales = {}   # connection_id -> {'serial': Serial, 'port': str, 'lock': Lock, 'thread': Thread, 'actif': bool}
verrou_global = threading.Lock()


def log_vers_serveur(level, message):
    """Remonte aussi le message au serveur pour qu'il apparaisse sur /admin/logs"""
    try:
        if sio.connected:
            sio.emit('agent_log', {'agent_id': CONFIG['agent_id'], 'level': level, 'message': message}, namespace='/agent')
    except Exception:
        pass


def detecter_ports_arduino():
    """Identique à la détection d'origine (controllers/arduino_controller.py), mais côté agent"""
    ports_trouves = []

    ports_deja_ouverts = {c['port'] for c in connexions_locales.values() if c.get('actif')}

    for port in serial.tools.list_ports.comports():
        desc = port.description.upper()
        hwid = port.hwid.upper()
        est_arduino = any(ind in desc for ind in INDICATEURS_ARDUINO) or any(ind in hwid for ind in INDICATEURS_ARDUINO)

        if est_arduino:
            ports_trouves.append({
                'port': port.device,
                'description': port.description,
                'en_utilisation': port.device in ports_deja_ouverts,
            })

    return ports_trouves


def boucle_scan_ports():
    while True:
        try:
            ports = detecter_ports_arduino()
            if sio.connected:
                sio.emit('ports', {'agent_id': CONFIG['agent_id'], 'ports': ports}, namespace='/agent')
        except Exception as e:
            logger.error(f"Erreur scan ports : {e}")
        time.sleep(CONFIG['intervalle_scan_ports_s'])


def boucle_heartbeat():
    while True:
        try:
            if sio.connected:
                sio.emit('heartbeat', {'agent_id': CONFIG['agent_id']}, namespace='/agent')
        except Exception as e:
            logger.error(f"Erreur heartbeat : {e}")
        time.sleep(CONFIG['intervalle_heartbeat_s'])


# ----------------------------------------------------------------------------
# GESTION D'UNE CONNEXION SÉRIE (ouverte à la demande du serveur)
# ----------------------------------------------------------------------------

def ouvrir_connexion(connection_id, port):
    if connection_id in connexions_locales:
        logger.warning(f"Connexion {connection_id} déjà ouverte, on ignore la demande")
        return

    try:
        logger.info(f"Ouverture du port {port} pour {connection_id}...")
        port_serie = serial.Serial(
            port=port,
            baudrate=115200,
            timeout=1,
            write_timeout=1,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE
        )
        time.sleep(2)
        port_serie.reset_input_buffer()
        port_serie.reset_output_buffer()

        connexions_locales[connection_id] = {
            'serial': port_serie,
            'port': port,
            'lock': threading.Lock(),
            'actif': True,
        }

        thread = threading.Thread(target=boucle_lecture_arduino, args=(connection_id,), daemon=True)
        thread.start()
        connexions_locales[connection_id]['thread'] = thread

        logger.info(f"✅ Port {port} ouvert avec succès ({connection_id})")
        sio.emit('status', {'connection_id': connection_id, 'connected': True}, namespace='/agent')

    except Exception as e:
        logger.error(f"❌ Impossible d'ouvrir {port} pour {connection_id} : {e}")
        sio.emit('status', {'connection_id': connection_id, 'connected': False, 'error': str(e)}, namespace='/agent')
        log_vers_serveur('error', f"Échec ouverture {port} : {e}")


def fermer_connexion(connection_id):
    connexion = connexions_locales.get(connection_id)
    if not connexion:
        return

    connexion['actif'] = False
    try:
        with connexion['lock']:
            if connexion['serial'].is_open:
                connexion['serial'].write(b"STOP\n")
                time.sleep(0.3)
                connexion['serial'].close()
    except Exception as e:
        logger.warning(f"Erreur fermeture {connection_id} : {e}")

    connexions_locales.pop(connection_id, None)
    logger.info(f"🔌 Connexion {connection_id} fermée")
    sio.emit('status', {'connection_id': connection_id, 'connected': False}, namespace='/agent')


def envoyer_commande(connection_id, commande):
    connexion = connexions_locales.get(connection_id)
    if not connexion or not connexion.get('actif'):
        return
    try:
        with connexion['lock']:
            connexion['serial'].write(commande.encode('utf-8'))
    except Exception as e:
        logger.error(f"Erreur envoi commande '{commande.strip()}' vers {connection_id} : {e}")


def boucle_lecture_arduino(connection_id):
    """
    Reprend la mécanique de l'ancienne boucle de controllers/arduino_controller.py :
    lecture des lignes série, ping périodique, demande de température si inactif,
    vérification que le port existe toujours physiquement.
    """
    connexion = connexions_locales.get(connection_id)
    if not connexion:
        return

    port_serie = connexion['serial']
    port = connexion['port']

    derniere_donnee = time.time()
    dernier_test_connexion = time.time()
    erreurs_consecutives = 0
    max_erreurs_consecutives = 3
    timeout_sans_donnee = 8

    while connexion.get('actif'):
        try:
            # Vérifier périodiquement que le port existe encore physiquement
            if time.time() - dernier_test_connexion > 3:
                ports_existants = [p.device for p in serial.tools.list_ports.comports()]
                if port not in ports_existants:
                    logger.warning(f"❌ Port physique {port} n'existe plus ({connection_id})")
                    break

                try:
                    with connexion['lock']:
                        port_serie.write(b"PING\n")
                    dernier_test_connexion = time.time()
                    erreurs_consecutives = 0
                except Exception as e:
                    erreurs_consecutives += 1
                    logger.warning(f"Erreur ping {port} : {e}")
                    if erreurs_consecutives >= max_erreurs_consecutives:
                        logger.error(f"Trop d'erreurs consécutives sur {port}, abandon")
                        break

            if time.time() - derniere_donnee > timeout_sans_donnee:
                logger.warning(f"Timeout : aucune donnée valide reçue depuis {timeout_sans_donnee}s sur {port}")
                break

            while port_serie.in_waiting > 0:
                try:
                    with connexion['lock']:
                        ligne = port_serie.readline().decode('utf-8', errors='ignore').strip()
                except Exception as e:
                    logger.error(f"Erreur lecture ligne {port} : {e}")
                    continue

                if not ligne:
                    continue

                if ligne.startswith("DATA:"):
                    derniere_donnee = time.time()

                # On relaie au serveur toutes les lignes utiles (DATA/STATUS/ALERTE).
                # Les simples accusés de réception (PONG, "PWM recue:", etc.)
                # restent locaux pour ne pas saturer la liaison Internet.
                if ligne.startswith("DATA:") or ligne.startswith("STATUS:") or "ALERTE" in ligne:
                    if sio.connected:
                        sio.emit('data', {'connection_id': connection_id, 'line': ligne}, namespace='/agent')

            # Si pas de donnée récente, redemander la température
            if time.time() - derniere_donnee > 2:
                try:
                    with connexion['lock']:
                        port_serie.write(b"TEMP\n")
                except Exception as e:
                    logger.error(f"Erreur demande TEMP {port} : {e}")

            time.sleep(0.2)

        except Exception as e:
            logger.error(f"Erreur boucle lecture {connection_id} : {e}")
            break

    # Nettoyage
    try:
        with connexion['lock']:
            if port_serie.is_open:
                port_serie.write(b"STOP\n")
                time.sleep(0.3)
                port_serie.close()
    except Exception:
        pass

    connexions_locales.pop(connection_id, None)
    logger.info(f"Connexion {connection_id} nettoyée (boucle terminée)")
    if sio.connected:
        sio.emit('status', {'connection_id': connection_id, 'connected': False, 'error': 'liaison série interrompue'}, namespace='/agent')


# ----------------------------------------------------------------------------
# ÉVÉNEMENTS SOCKET.IO (namespace /agent)
# ----------------------------------------------------------------------------

@sio.event(namespace='/agent')
def connect():
    logger.info(f"✅ Connecté au serveur central en tant que '{CONFIG['agent_id']}'")


@sio.event(namespace='/agent')
def connect_error(data):
    logger.error(f"❌ Échec de connexion au serveur : {data}")


@sio.event(namespace='/agent')
def disconnect():
    logger.warning("⚠️ Déconnecté du serveur central, tentative de reconnexion automatique...")


@sio.on('server:hello', namespace='/agent')
def on_hello(data):
    logger.info(f"Serveur : {data.get('message')}")


@sio.on('server:open_port', namespace='/agent')
def on_open_port(data):
    ouvrir_connexion(data['connection_id'], data['port'])


@sio.on('server:close_port', namespace='/agent')
def on_close_port(data):
    fermer_connexion(data['connection_id'])


@sio.on('server:command', namespace='/agent')
def on_command(data):
    envoyer_commande(data['connection_id'], data['command'])


# ----------------------------------------------------------------------------
# POINT D'ENTRÉE
# ----------------------------------------------------------------------------

def main():
    logger.info("=" * 60)
    logger.info("AGENT LOCAL - Thermostat UAM")
    logger.info("=" * 60)
    logger.info(f"Identifiant agent : {CONFIG['agent_id']}")
    logger.info(f"Serveur           : {CONFIG['server_url']}")
    logger.info("=" * 60)

    threading.Thread(target=boucle_scan_ports, daemon=True).start()
    threading.Thread(target=boucle_heartbeat, daemon=True).start()

    while True:
        try:
            sio.connect(
                CONFIG['server_url'],
                namespaces=['/agent'],
                auth={'token': CONFIG['agent_token'], 'agent_id': CONFIG['agent_id']},
                wait_timeout=10,
            )
            sio.wait()
        except KeyboardInterrupt:
            logger.info("Arrêt demandé (Ctrl+C)")
            break
        except Exception as e:
            logger.error(f"Connexion au serveur impossible : {e}. Nouvelle tentative dans 5s...")
            time.sleep(5)


if __name__ == '__main__':
    main()
