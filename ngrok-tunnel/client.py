# client.py
import asyncio
import json
import websockets
import httpx
import os
import time
import uuid
import logging
import ssl
import sys
import mimetypes
from datetime import datetime
from typing import Optional

# Configuration des types MIME
mimetypes.add_type('text/css', '.css')
mimetypes.add_type('application/javascript', '.js')
mimetypes.add_type('image/jpeg', '.jpg')
mimetypes.add_type('image/png', '.png')
mimetypes.add_type('image/gif', '.gif')
mimetypes.add_type('image/webp', '.webp')

# Configuration du logging (console + fichier tournant)
# Le fichier permet de retrouver la trace d'un crash même si la fenêtre
# cmd a été fermée ou a planté avant qu'on puisse la lire.
from logging.handlers import RotatingFileHandler

LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
os.makedirs(LOG_DIR, exist_ok=True)

_formatter = logging.Formatter(
    '%(asctime)s - [%(levelname)s] - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

_file_handler = RotatingFileHandler(
    os.path.join(LOG_DIR, "tunnel_client.log"),
    maxBytes=5 * 1024 * 1024,  # 5 Mo
    backupCount=5,
    encoding="utf-8"
)
_file_handler.setFormatter(_formatter)

_console_handler = logging.StreamHandler()
_console_handler.setFormatter(_formatter)

logging.basicConfig(level=logging.INFO, handlers=[_console_handler, _file_handler])
logger = logging.getLogger(__name__)

# Variables d'environnement
TUNNEL_SERVER_URL = os.environ.get("TUNNEL_SERVER_URL", "wss://uam-thermostat.dspcentric.com").strip()
FLASK_URL = os.environ.get("FLASK_URL", "http://localhost:5000").strip()

TUNNEL_NAME = "default" 
PROJECT_NAME = "default"

logger.info(f"🔗 Configuration FORCÉE:")
logger.info(f"   TUNNEL_NAME: {TUNNEL_NAME}")
logger.info(f"   PROJECT_NAME: {PROJECT_NAME}")
logger.info(f"   TUNNEL_SERVER_URL: {TUNNEL_SERVER_URL}")
logger.info(f"   FLASK_URL: {FLASK_URL}")

# Client HTTP
client = httpx.AsyncClient(
    timeout=httpx.Timeout(60.0, connect=10.0),
    follow_redirects=True
)

# Verrou partagé pour protéger les envois concurrents sur le même websocket
ws_send_lock = asyncio.Lock()

# Statistiques
stats = {
    'requests_received': 0,
    'requests_forwarded': 0,
    'responses_sent': 0,
    'errors': 0,
    'reconnections': 0,
    'start_time': time.time()
}

def create_ssl_context():
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE
    return ssl_context

async def handle_request(request_data: dict) -> dict:
    """Traite une requête et la transmet à Flask"""
    try:
        request_id = request_data.get('request_id')
        method = request_data.get('method', 'GET')
        original_path = request_data.get('path', '/')
        headers = request_data.get('headers', {})
        body_hex = request_data.get('body', '')
        
        body = bytes.fromhex(body_hex) if body_hex else b''
        
        # Le serveur transmet maintenant le chemin tel quel (sans préfixe
        # /default/), on le renvoie donc directement à Flask.
        path = original_path if original_path else '/'
        if not path.startswith('/'):
            path = '/' + path
        
        url = f"{FLASK_URL}{path}"
        
        stats['requests_received'] += 1
        stats['requests_forwarded'] += 1
        
        is_static = path.startswith('/static/')
        
        logger.info(f"📤 {method} {original_path} -> {path}" + (" (static)" if is_static else ""))
        
        timeout_value = 60.0 if is_static else 30.0
        
        try:
            response = await client.request(
                method=method,
                url=url,
                headers=headers,
                content=body,
                follow_redirects=True,
                timeout=httpx.Timeout(timeout_value, connect=10.0)
            )
        except httpx.ConnectError as e:
            logger.error(f" Erreur de connexion à Flask: {e}")
            logger.error(f"   Vérifiez que Flask tourne sur {FLASK_URL}")
            return {
                'type': 'response',
                'request_id': request_id,
                'status_code': 503,
                'headers': {},
                'body': b'Flask server not available'.hex()
            }
        except Exception as e:
            logger.error(f" Erreur requête HTTP: {e}")
            return {
                'type': 'response',
                'request_id': request_id,
                'status_code': 502,
                'headers': {},
                'body': str(e).encode().hex()
            }
        
        content = response.content
        status_code = response.status_code
        response_headers = dict(response.headers)
        
        if is_static:
            ext = path.split('.')[-1].lower() if '.' in path else ''
            if ext:
                mime_type, _ = mimetypes.guess_type(f'file.{ext}')
                if mime_type:
                    response_headers['Content-Type'] = mime_type
            
            logger.info(f" Static: {path} ({len(content)} bytes, {response_headers.get('Content-Type', 'unknown')})")
        
        response_data = {
            'type': 'response',
            'request_id': request_id,
            'status_code': status_code,
            'headers': response_headers,
            'body': content.hex()
        }
        
        stats['responses_sent'] += 1
        logger.info(f" Réponse {status_code} pour {request_id}")
        
        return response_data
        
    except Exception as e:
        logger.error(f" Erreur handle_request: {e}")
        stats['errors'] += 1
        return {
            'type': 'response',
            'request_id': request_id,
            'status_code': 500,
            'headers': {},
            'body': str(e).encode().hex()
        }

def https_base_url() -> str:
    """Convertit l'URL wss://... du tunnel en https://... pour les requêtes HTTP simples."""
    if TUNNEL_SERVER_URL.startswith("wss://"):
        return "https://" + TUNNEL_SERVER_URL[len("wss://"):]
    if TUNNEL_SERVER_URL.startswith("ws://"):
        return "http://" + TUNNEL_SERVER_URL[len("ws://"):]
    return TUNNEL_SERVER_URL

async def fetch_server_start_time() -> Optional[float]:
    try:
        resp = await client.get(f"{https_base_url()}/health", timeout=10.0)
        if resp.status_code == 200:
            return resp.json().get('server_start_time')
    except Exception as e:
        logger.warning(f"⚠️ Impossible de vérifier l'état du serveur: {e}")
    return None

async def watchdog_server_restart(websocket, server_start_time_connu):
    """
    Render peut redémarrer/redéployer server.py sans que notre websocket
    ne remarque immédiatement la coupure (connexion "zombie"). On compare
    périodiquement l'heure de démarrage annoncée par le serveur ; si elle
    change, le serveur a redémarré et a donc perdu notre tunnel -> on force
    la reconnexion.
    """
    try:
        while True:
            await asyncio.sleep(30)
            current = await fetch_server_start_time()
            if current is not None and server_start_time_connu is not None and current != server_start_time_connu:
                logger.warning(" Redémarrage du serveur détecté (le tunnel a été perdu côté Render) - reconnexion forcée...")
                await websocket.close()
                return
    except asyncio.CancelledError:
        pass
    except Exception as e:
        logger.error(f"❌ Erreur watchdog: {e}")

async def tunnel_client():
    """Client principal du tunnel"""
    ws_url = f"{TUNNEL_SERVER_URL}/tunnel/{TUNNEL_NAME}"
    
    logger.info(f" Lancement du tunnel: {TUNNEL_NAME}")
    logger.info(f" Serveur: {ws_url}")
    logger.info(f" Flask: {FLASK_URL}")
    logger.info(f" Projet: {PROJECT_NAME}")
    
    while True:
        try:
            connect_kwargs = {
                "ping_interval": 20,
                "ping_timeout": 10,
                "close_timeout": 10,
                "max_size": 10 * 1024 * 1024,
                "user_agent_header": f"TunnelClient/{TUNNEL_NAME}"
            }
            
            if ws_url.startswith("wss://"):
                connect_kwargs["ssl"] = create_ssl_context()
            
            logger.info(f" Connexion à {ws_url}...")
            
            try:
                websocket = await asyncio.wait_for(
                    websockets.connect(ws_url, **connect_kwargs),
                    timeout=15
                )
            except asyncio.TimeoutError:
                logger.warning(" Timeout de connexion, nouvelle tentative dans 5s...")
                await asyncio.sleep(5)
                continue
            except Exception as e:
                logger.error(f" Erreur de connexion: {e}")
                await asyncio.sleep(5)
                continue
            
            logger.info(" Connecté au serveur!")
            
            try:
                auth_msg = json.dumps({
                    'type': 'auth',
                    'project_name': PROJECT_NAME
                })
                
                await websocket.send(auth_msg)
                logger.info(" Authentification envoyée")
                
                response = await asyncio.wait_for(websocket.recv(), timeout=10)
                data = json.loads(response)
                logger.info(f" {data.get('message', 'Authentifié')}")
                
            except asyncio.TimeoutError:
                logger.error(" Timeout d'authentification")
                await websocket.close()
                await asyncio.sleep(5)
                continue
            except Exception as e:
                logger.error(f" Erreur d'authentification: {e}")
                await websocket.close()
                await asyncio.sleep(5)
                continue
            
            receive_task = asyncio.create_task(receive_messages(websocket))
            keepalive_task = asyncio.create_task(send_keepalive(websocket))
            server_start_time_connu = await fetch_server_start_time()
            watchdog_task = asyncio.create_task(watchdog_server_restart(websocket, server_start_time_connu))
            
            await receive_task
            
            keepalive_task.cancel()
            watchdog_task.cancel()
            
        except websockets.ConnectionClosed as e:
            stats['reconnections'] += 1
            logger.warning(f" Connexion perdue (code: {e.code}), reconnexion dans 5s...")
            await asyncio.sleep(5)
            
        except Exception as e:
            stats['errors'] += 1
            stats['reconnections'] += 1
            logger.error(f" Erreur: {e}")
            await asyncio.sleep(5)

async def receive_messages(websocket):
    async def process_request(data: dict):
        """Traite une requête sans bloquer la réception des suivantes."""
        response = await handle_request(data)
        try:
            async with ws_send_lock:
                await websocket.send(json.dumps(response))
        except Exception as e:
            logger.error(f"❌ Erreur envoi réponse: {e}")

    try:
        async for message in websocket:
            try:
                data = json.loads(message)
                
                if data.get('type') == 'request':
                    logger.info(f" Requête reçue: {data.get('method')} {data.get('path')}")
                    # Lancée en tâche de fond : les requêtes suivantes ne sont
                    # plus bloquées en attendant la réponse de celle-ci
                    # (ce qui provoquait des timeouts/déconnexions côté
                    # navigateur quand plusieurs requêtes arrivaient rapprochées,
                    # par ex. le polling /api/data toutes les secondes).
                    asyncio.create_task(process_request(data))
                    
                elif data.get('type') == 'ping':
                    async with ws_send_lock:
                        await websocket.send(json.dumps({
                            'type': 'pong',
                            'timestamp': time.time()
                        }))
                    
                elif data.get('type') == 'connected':
                    logger.info(f" {data.get('message', 'Connecté')}")
                    
            except json.JSONDecodeError:
                logger.warning("⚠️ Message JSON invalide")
            except Exception as e:
                logger.error(f"❌ Erreur traitement message: {e}")
                
    except websockets.ConnectionClosed:
        logger.warning("⚠️ Connexion fermée")
    except Exception as e:
        logger.error(f"❌ Erreur receive_messages: {e}")

async def send_keepalive(websocket):
    try:
        while True:
            await asyncio.sleep(25)
            try:
                async with ws_send_lock:
                    await websocket.send(json.dumps({
                        'type': 'ping',
                        'timestamp': time.time()
                    }))
            except:
                break
    except:
        pass

async def display_stats():
    while True:
        await asyncio.sleep(30)
        uptime = int(time.time() - stats['start_time'])
        hours = uptime // 3600
        minutes = (uptime % 3600) // 60
        
        logger.info(f"""
 STATISTIQUES:
   Uptime: {hours}h {minutes}m
   Requêtes reçues: {stats['requests_received']}
   Requêtes transmises: {stats['requests_forwarded']}
   Réponses envoyées: {stats['responses_sent']}
   Reconnexions: {stats['reconnections']}
   Erreurs: {stats['errors']}
""")

async def keep_render_awake():
    """
    Ping régulier de /health pour empêcher Render (plan gratuit) de mettre
    le service en veille après ~15 min sans trafic HTTP. Tourne en continu,
    indépendamment de l'état du tunnel websocket (utile même pendant une
    reconnexion). Remplace le script séparé keep_alive.py : plus qu'un
    seul processus à lancer, donc plus de risque d'oublier de démarrer
    le keep-alive.
    """
    url = f"{https_base_url()}/health"
    interval = 300  # 5 min, marge de sécurité sous le seuil de 15 min de Render
    logger.info(f"🌙 Anti-veille activé — ping de {url} toutes les {interval // 60} min")
    while True:
        try:
            resp = await client.get(url, timeout=15.0)
            logger.info(f"🌙 Ping anti-veille OK ({resp.status_code})")
        except Exception as e:
            logger.warning(f"🌙 Ping anti-veille échoué : {e}")
        await asyncio.sleep(interval)

def signal_handler(sig, frame):
    logger.info("🛑 Arrêt du client...")
    sys.exit(0)

async def main():
    import signal
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    print("""
    ╔══════════════════════════════════════════════════════════════╗
    ║              TUNNEL CLIENT - Render Compatible               ║
    ╠══════════════════════════════════════════════════════════════╣
    ║  Client pour serveur Render avec chemin /tunnel/{name}      ║
    ║  Support des fichiers statiques (CSS, JS, images)          ║
    ║  Timeouts augmentés pour les gros fichiers                 ║
    ╚══════════════════════════════════════════════════════════════╝
    """)
    
    logger.info(f"🔗 Tunnel: {TUNNEL_NAME}")
    logger.info(f" Projet: {PROJECT_NAME}")
    logger.info(f" Serveur: {TUNNEL_SERVER_URL}/tunnel/{TUNNEL_NAME}")
    logger.info(f" Application: {FLASK_URL}")
    
    tasks = [
        asyncio.create_task(tunnel_client()),
        asyncio.create_task(display_stats()),
        asyncio.create_task(keep_render_awake())
    ]

    try:
        # return_exceptions=True : si une tâche plante, on récupère
        # l'exception au lieu de la laisser remonter et tuer tout le
        # process. On logue et on relance (voir run_forever ci-dessous).
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for t, result in zip(tasks, results):
            if isinstance(result, Exception):
                logger.error(f"❌ Tâche {t.get_name()} terminée en erreur: {result}", exc_info=result)
    finally:
        await client.aclose()


def run_forever():
    """
    Superviseur de processus : si main() se termine pour une raison
    quelconque (exception non prévue, crash d'une tâche, etc.), on logue
    la trace complète dans le fichier et on relance après un court délai
    au lieu de laisser le process (et donc le tunnel) mourir pour de bon.
    """
    backoff = 5
    while True:
        try:
            asyncio.run(main())
            logger.warning("⚠️ main() s'est terminé sans exception, relance dans 5s...")
            time.sleep(5)
            backoff = 5
        except KeyboardInterrupt:
            logger.info("🛑 Arrêt demandé par l'utilisateur")
            break
        except Exception:
            logger.error("❌ Crash du client tunnel, relance automatique dans "
                         f"{backoff}s...", exc_info=True)
            time.sleep(backoff)
            backoff = min(backoff * 2, 60)  # backoff exponentiel, plafonné à 60s


if __name__ == "__main__":
    run_forever()