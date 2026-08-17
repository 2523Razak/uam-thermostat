# tunnel_service.py - Service de tunnel HTTP intégré à Flask
import threading
import asyncio
import json
import time
import uuid
import logging
import socket
import requests
import os
import subprocess
import sys
from datetime import datetime
from functools import wraps
from flask import Flask, request, jsonify, Response, render_template_string
from typing import Dict, Optional, Callable

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - [TUNNEL] - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ============================================================================
# SERVEUR TUNNEL EMBARQUÉ (Tourne dans un thread séparé)
# ============================================================================

class EmbeddedTunnelServer:
    """Serveur tunnel intégré qui tourne dans un thread séparé"""
    
    def __init__(self, public_port=8080):
        self.public_port = public_port
        self.is_running = False
        self.tunnels = {}
        self.server_thread = None
        self.public_url = None
        
    def start(self):
        """Démarre le serveur tunnel dans un thread"""
        if self.is_running:
            return
        
        self.is_running = True
        self.server_thread = threading.Thread(target=self._run_server, daemon=True)
        self.server_thread.start()
        
        # Attendre que le serveur démarre
        time.sleep(2)
        
        # Obtenir l'URL publique
        self.public_url = self._get_public_url()
        
        logger.info(f"🚀 Serveur tunnel démarré sur le port {self.public_port}")
        logger.info(f"🌐 URL publique: {self.public_url}")
        
        return self.public_url
    
    def _run_server(self):
        """Exécute le serveur HTTP tunnel"""
        try:
            from http.server import HTTPServer, BaseHTTPRequestHandler
            import json as json_module
            
            class TunnelHandler(BaseHTTPRequestHandler):
                def log_message(self, format, *args):
                    pass  # Supprimer les logs par défaut
                
                def do_GET(self):
                    self._handle_request('GET')
                
                def do_POST(self):
                    self._handle_request('POST')
                
                def do_PUT(self):
                    self._handle_request('PUT')
                
                def do_DELETE(self):
                    self._handle_request('DELETE')
                
                def _handle_request(self, method):
                    """Gère les requêtes entrantes et les transmet au tunnel"""
                    try:
                        # Lire le corps de la requête
                        content_length = int(self.headers.get('Content-Length', 0))
                        body = self.rfile.read(content_length) if content_length > 0 else b''
                        
                        # Extraire le nom du projet de l'URL
                        path_parts = self.path.lstrip('/').split('/', 1)
                        project_name = path_parts[0] if path_parts else 'default'
                        remaining_path = path_parts[1] if len(path_parts) > 1 else ''
                        
                        # Trouver le tunnel correspondant
                        tunnel_server = self.server.tunnel_server
                        if project_name not in tunnel_server.tunnels:
                            self.send_response(404)
                            self.send_header('Content-Type', 'application/json')
                            self.end_headers()
                            self.wfile.write(json_module.dumps({
                                'error': f'Tunnel {project_name} non trouvé'
                            }).encode())
                            return
                        
                        tunnel_info = tunnel_server.tunnels[project_name]
                        flask_port = tunnel_info['flask_port']
                        
                        # Transférer la requête à Flask
                        url = f"http://localhost:{flask_port}/{remaining_path}"
                        headers = {k: v for k, v in self.headers.items() 
                                  if k.lower() not in ['host', 'content-length']}
                        
                        try:
                            if method == 'GET':
                                resp = requests.get(url, headers=headers, timeout=30)
                            elif method == 'POST':
                                resp = requests.post(url, data=body, headers=headers, timeout=30)
                            elif method == 'PUT':
                                resp = requests.put(url, data=body, headers=headers, timeout=30)
                            elif method == 'DELETE':
                                resp = requests.delete(url, headers=headers, timeout=30)
                            else:
                                resp = requests.request(method, url, data=body, headers=headers, timeout=30)
                            
                            # Retourner la réponse
                            self.send_response(resp.status_code)
                            for key, value in resp.headers.items():
                                if key.lower() not in ['content-encoding', 'transfer-encoding', 'content-length']:
                                    self.send_header(key, value)
                            self.end_headers()
                            self.wfile.write(resp.content)
                            
                            tunnel_info['stats']['requests_forwarded'] += 1
                            
                        except requests.exceptions.RequestException as e:
                            self.send_response(502)
                            self.send_header('Content-Type', 'application/json')
                            self.end_headers()
                            self.wfile.write(json_module.dumps({
                                'error': f'Erreur de connexion à Flask: {str(e)}'
                            }).encode())
                            
                    except Exception as e:
                        self.send_response(500)
                        self.send_header('Content-Type', 'application/json')
                        self.end_headers()
                        self.wfile.write(json_module.dumps({
                            'error': f'Erreur interne: {str(e)}'
                        }).encode())
            
            # Configurer et démarrer le serveur
            handler = TunnelHandler
            handler.tunnel_server = self
            
            with HTTPServer(('0.0.0.0', self.public_port), handler) as httpd:
                logger.info(f"✅ Serveur tunnel HTTP actif sur le port {self.public_port}")
                while self.is_running:
                    httpd.handle_request()
                    
        except Exception as e:
            logger.error(f"❌ Erreur du serveur tunnel: {e}")
    
    def _get_public_url(self):
        """Récupère l'URL publique du tunnel"""
        try:
            # Obtenir l'IP publique
            response = requests.get('https://api.ipify.org?format=json', timeout=5)
            public_ip = response.json()['ip']
            return f"http://{public_ip}:{self.public_port}"
        except:
            # Fallback: IP locale
            hostname = socket.gethostname()
            local_ip = socket.gethostbyname(hostname)
            return f"http://{local_ip}:{self.public_port}"
    
    def register_tunnel(self, project_name: str, flask_port: int):
        """Enregistre un nouveau tunnel"""
        self.tunnels[project_name] = {
            'flask_port': flask_port,
            'registered_at': datetime.now().isoformat(),
            'stats': {
                'requests_forwarded': 0,
                'last_activity': None
            }
        }
        logger.info(f"📝 Tunnel enregistré: {project_name} -> port {flask_port}")
    
    def unregister_tunnel(self, project_name: str):
        """Supprime un tunnel"""
        if project_name in self.tunnels:
            del self.tunnels[project_name]
            logger.info(f"🔌 Tunnel supprimé: {project_name}")
    
    def get_status(self):
        """Retourne le statut du serveur"""
        return {
            'is_running': self.is_running,
            'port': self.public_port,
            'public_url': self.public_url,
            'active_tunnels': len(self.tunnels),
            'tunnels': self.tunnels
        }
    
    def stop(self):
        """Arrête le serveur"""
        self.is_running = False

# ============================================================================
# SERVICE DE TUNNEL POUR FLASK
# ============================================================================

class FlaskTunnelService:
    """Service de tunnel pour application Flask"""
    
    def __init__(self, app: Flask = None):
        self.app = app
        self.embedded_server = None
        self.tunnel_active = False
        self.public_url = None
        self.tunnel_thread = None
        
        if app:
            self.init_app(app)
    
    def init_app(self, app: Flask):
        """Initialise le service avec l'application Flask"""
        self.app = app
        
        # Configuration par défaut
        app.config.setdefault('TUNNEL_PUBLIC_PORT', 8080)
        app.config.setdefault('TUNNEL_PROJECT_NAME', 'thermostat_uam')
        app.config.setdefault('TUNNEL_AUTO_START', True)
        
        # Ajouter les routes
        self._register_routes()
        
        logger.info("✅ Service de tunnel initialisé")
    
    def _register_routes(self):
        """Enregistre les routes pour la gestion du tunnel"""
        
        @self.app.route('/tunnel/info')
        def tunnel_info():
            """Page d'information du tunnel"""
            status = self.get_status()
            
            html = """
            <!DOCTYPE html>
            <html lang="fr">
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>Tunnel HTTP - Thermostat UAM</title>
                <style>
                    body {
                        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                        min-height: 100vh;
                        display: flex;
                        justify-content: center;
                        align-items: center;
                        margin: 0;
                        padding: 20px;
                    }
                    .card {
                        background: white;
                        border-radius: 20px;
                        padding: 40px;
                        max-width: 600px;
                        width: 100%;
                        box-shadow: 0 20px 60px rgba(0,0,0,0.3);
                        text-align: center;
                    }
                    .logo {
                        font-size: 64px;
                        margin-bottom: 20px;
                    }
                    h1 {
                        color: #333;
                        margin-bottom: 10px;
                    }
                    .url-box {
                        background: #f0f0f0;
                        padding: 20px;
                        border-radius: 10px;
                        margin: 20px 0;
                        word-break: break-all;
                    }
                    .url {
                        font-size: 18px;
                        font-weight: bold;
                        color: #667eea;
                        text-decoration: none;
                    }
                    .status {
                        display: inline-block;
                        padding: 5px 15px;
                        border-radius: 20px;
                        font-size: 14px;
                        margin: 10px 0;
                    }
                    .status-active {
                        background: #d4edda;
                        color: #155724;
                    }
                    .copy-btn {
                        background: #667eea;
                        color: white;
                        border: none;
                        padding: 10px 20px;
                        border-radius: 5px;
                        cursor: pointer;
                        font-size: 16px;
                        margin-top: 10px;
                    }
                    .copy-btn:hover {
                        background: #5a67d8;
                    }
                    .stats {
                        text-align: left;
                        margin-top: 20px;
                        padding: 20px;
                        background: #f8f9fa;
                        border-radius: 10px;
                    }
                    .stats h3 {
                        margin-top: 0;
                    }
                    .footer {
                        margin-top: 20px;
                        font-size: 12px;
                        color: #888;
                    }
                </style>
            </head>
            <body>
                <div class="card">
                    <div class="logo">🚇</div>
                    <h1>Thermostat UAM</h1>
                    <p>Accès public via tunnel HTTP</p>
                    
                    <div class="url-box">
                        <strong>🔗 Lien public partageable :</strong><br>
                        <a href="{{ url }}" class="url" id="publicUrl" target="_blank">{{ url }}</a>
                        <br>
                        <button class="copy-btn" onclick="copyUrl()">📋 Copier le lien</button>
                    </div>
                    
                    <div class="stats">
                        <h3>📊 Statistiques du tunnel</h3>
                        <p><strong>Statut :</strong> 
                            <span class="status status-active">✅ Actif</span>
                        </p>
                        <p><strong>URL publique :</strong> <span id="urlDisplay">{{ url }}</span></p>
                        <p><strong>Nombre de tunnels :</strong> {{ active_tunnels }}</p>
                        <p><strong>Démarré depuis :</strong> {{ started_since }}</p>
                    </div>
                    
                    <div class="footer">
                        <p>🔒 Tunnel sécurisé - Accès direct à l'application</p>
                        <p>⚡ Le lien reste actif tant que l'application tourne</p>
                    </div>
                </div>
                
                <script>
                    function copyUrl() {
                        const url = document.getElementById('publicUrl').href;
                        navigator.clipboard.writeText(url).then(() => {
                            alert('Lien copié dans le presse-papier !');
                        });
                    }
                    
                    // Mettre à jour l'affichage toutes les 10 secondes
                    setInterval(() => {
                        fetch('/api/tunnel/status')
                            .then(r => r.json())
                            .then(data => {
                                if (data.public_url) {
                                    document.getElementById('publicUrl').href = data.public_url;
                                    document.getElementById('publicUrl').textContent = data.public_url;
                                    document.getElementById('urlDisplay').textContent = data.public_url;
                                }
                            });
                    }, 10000);
                </script>
            </body>
            </html>
            """
            
            return render_template_string(html, **status)
        
        @self.app.route('/api/tunnel/status')
        def api_tunnel_status():
            """API pour obtenir le statut du tunnel"""
            return jsonify(self.get_status())
        
        @self.app.route('/api/tunnel/start', methods=['POST'])
        def api_tunnel_start():
            """API pour démarrer le tunnel"""
            success = self.start()
            return jsonify({'success': success, 'public_url': self.public_url})
        
        @self.app.route('/api/tunnel/stop', methods=['POST'])
        def api_tunnel_stop():
            """API pour arrêter le tunnel"""
            success = self.stop()
            return jsonify({'success': success})
        
        @self.app.route('/tunnel/link')
        def tunnel_link():
            """Redirection vers le lien public"""
            if self.public_url:
                import webbrowser
                webbrowser.open(self.public_url)
                return f'<script>window.location.href="{self.public_url}";</script>'
            return "Tunnel non actif", 503
    
    def start(self):
        """Démarre le tunnel"""
        if self.tunnel_active:
            logger.info("Tunnel déjà actif")
            return True
        
        try:
            # Créer et démarrer le serveur tunnel embarqué
            public_port = self.app.config['TUNNEL_PUBLIC_PORT']
            project_name = self.app.config['TUNNEL_PROJECT_NAME']
            flask_port = self.app.config.get('PORT', 5000)
            
            self.embedded_server = EmbeddedTunnelServer(public_port=public_port)
            self.public_url = self.embedded_server.start()
            
            # Enregistrer le tunnel Flask
            self.embedded_server.register_tunnel(project_name, flask_port)
            
            self.tunnel_active = True
            
            logger.info(f"✅ Tunnel démarré avec succès!")
            logger.info(f"🌐 URL publique: {self.public_url}")
            logger.info(f"📝 Projet: {project_name}")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Erreur au démarrage du tunnel: {e}")
            return False
    
    def stop(self):
        """Arrête le tunnel"""
        if self.embedded_server:
            self.embedded_server.stop()
        self.tunnel_active = False
        self.public_url = None
        logger.info("Tunnel arrêté")
        return True
    
    def get_status(self):
        """Retourne le statut du tunnel"""
        uptime = ""
        if hasattr(self, 'start_time'):
            elapsed = time.time() - self.start_time
            hours = int(elapsed // 3600)
            minutes = int((elapsed % 3600) // 60)
            uptime = f"{hours}h {minutes}min"
        
        return {
            'active': self.tunnel_active,
            'public_url': self.public_url or "Non disponible",
            'port': self.app.config.get('TUNNEL_PUBLIC_PORT', 8080) if self.tunnel_active else None,
            'project_name': self.app.config.get('TUNNEL_PROJECT_NAME', 'thermostat_uam'),
            'started_since': uptime or "Non démarré",
            'active_tunnels': len(self.embedded_server.tunnels) if self.embedded_server else 0
        }
    
    def get_shareable_link(self):
        """Retourne le lien partageable"""
        return self.public_url if self.tunnel_active else None

# ============================================================================
# DÉCORATEUR POUR INTÉGRATION FACILE
# ============================================================================

def enable_tunnel(app: Flask, auto_start: bool = True, public_port: int = 8080, 
                   project_name: str = None):
    """
    Active le tunnel HTTP pour l'application Flask
    
    Args:
        app: Application Flask
        auto_start: Démarrer automatiquement le tunnel
        public_port: Port public du tunnel (défaut: 8080)
        project_name: Nom du projet (défaut: nom de l'app)
    
    Returns:
        FlaskTunnelService: Service de tunnel
    """
    app.config['TUNNEL_PUBLIC_PORT'] = public_port
    app.config['TUNNEL_PROJECT_NAME'] = project_name or app.name
    app.config['TUNNEL_AUTO_START'] = auto_start
    
    tunnel_service = FlaskTunnelService(app)
    
    if auto_start:
        # Démarrer dans un thread séparé pour ne pas bloquer
        def start_tunnel():
            time.sleep(2)  # Attendre que Flask soit démarré
            tunnel_service.start()
        
        thread = threading.Thread(target=start_tunnel, daemon=True)
        thread.start()
    
    return tunnel_service

# ============================================================================
# FONCTION PRINCIPALE POUR TEST
# ============================================================================

def create_test_app():
    """Crée une application de test"""
    app = Flask(__name__)
    app.secret_key = 'test_secret_key'
    
    @app.route('/')
    def home():
        return """
        <!DOCTYPE html>
        <html>
        <head><title>Thermostat UAM</title></head>
        <body>
            <h1>🌡️ Thermostat UAM</h1>
            <p>Application de contrôle de température</p>
            <p>Le tunnel HTTP est actif !</p>
            <a href="/tunnel/info">🔗 Voir le lien public</a>
        </body>
        </html>
        """
    
    @app.route('/api/status')
    def status():
        return {'status': 'ok', 'timestamp': time.time()}
    
    return app

if __name__ == '__main__':
    # Test du tunnel seul
    app = create_test_app()
    
    # Activer le tunnel
    tunnel = enable_tunnel(app, auto_start=True, public_port=8080, project_name='thermostat_test')
    
    print("\n" + "="*60)
    print("🚇 TUNNEL HTTP DÉMARRÉ")
    print("="*60)
    print(f"📱 Application: http://localhost:5000")
    print(f"🔗 Lien public: {tunnel.get_shareable_link()}")
    print(f"📊 Dashboard tunnel: http://localhost:5000/tunnel/info")
    print("="*60 + "\n")
    
    app.run(host='0.0.0.0', port=5000, debug=True, threaded=True)