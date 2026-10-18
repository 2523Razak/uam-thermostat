# sockets/agent_hub.py - Point d'entrée Socket.IO pour les agents locaux
#
# C'est ici que le serveur central (hébergé) parle avec agent_arduino.py
# (qui tourne sur la machine locale, à côté des cartes Arduino branchées en USB).
#
# Canal : namespace Socket.IO "/agent"
#
# Événements envoyés par l'agent -> serveur :
#   connect (avec auth={'token', 'agent_id'})
#   'agent:heartbeat'  {agent_id}
#   'agent:ports'      {agent_id, ports: [{port, description, en_utilisation}]}
#   'agent:status'     {connection_id, connected, error}
#   'agent:data'       {connection_id, line}
#
# Événements envoyés par le serveur -> agent :
#   'server:hello'      {message}
#   'server:open_port'  {connection_id, port}
#   'server:close_port' {connection_id}
#   'server:command'    {connection_id, command}

import time
from flask import request
from flask_socketio import Namespace, emit, join_room
from utils.log_bus import log_bus


class AgentNamespace(Namespace):
    def __init__(self, namespace, arduino_controller, agent_token):
        super().__init__(namespace)
        self.controller = arduino_controller
        self.agent_token = agent_token

    def on_connect(self, auth):
        auth = auth or {}
        token = auth.get('token')

        if self.agent_token and token != self.agent_token:
            log_bus.warning('agent', f"Connexion agent refusée (jeton invalide), sid={request.sid}")
            return False  # refuse la connexion Socket.IO

        agent_id = auth.get('agent_id') or 'agent-defaut'

        self.controller.register_agent(agent_id, request.sid)
        join_room(agent_id)

        emit('server:hello', {
            'message': f"Connecté au serveur central en tant que '{agent_id}'",
            'ts': time.time()
        })

    def on_disconnect(self):
        self.controller.unregister_agent_by_sid(request.sid)

    def on_heartbeat(self, data):
        data = data or {}
        agent_id = data.get('agent_id', 'agent-defaut')
        self.controller.touch_agent(agent_id)

    def on_ports(self, data):
        data = data or {}
        agent_id = data.get('agent_id', 'agent-defaut')
        ports = data.get('ports', [])
        self.controller.set_agent_ports(agent_id, ports)

    def on_status(self, data):
        data = data or {}
        self.controller.mettre_a_jour_statut_connexion(
            id_connexion=data.get('connection_id'),
            connecte=bool(data.get('connected')),
            erreur=data.get('error')
        )

    def on_data(self, data):
        data = data or {}
        self.controller.traiter_ligne_arduino(
            id_connexion=data.get('connection_id'),
            ligne=data.get('line', '')
        )

    def on_agent_log(self, data):
        """L'agent peut remonter ses propres messages (erreurs série, etc.) pour la page d'entretien"""
        data = data or {}
        level = data.get('level', 'info')
        message = data.get('message', '')
        agent_id = data.get('agent_id', 'agent-defaut')
        log_bus.log(level, 'agent', f"[{agent_id}] {message}")


def register_agent_namespace(socketio, arduino_controller, agent_token):
    """À appeler depuis app.py juste après avoir créé l'objet SocketIO."""
    socketio.on_namespace(AgentNamespace('/agent', arduino_controller, agent_token))
    log_bus.info('system', "Namespace Socket.IO /agent enregistré")
