# utils/log_bus.py - Bus de logs centralisé (pour la page d'administration /admin/logs)
#
# Chaque composant du système (hub d'agents, contrôleur Arduino virtuel, etc.)
# pousse ses événements ici. La page /admin/logs les affiche et les rafraîchit
# automatiquement, ce qui sert de tableau de bord d'entretien en cas de problème
# (déconnexions d'agent, cartes qui décrochent, erreurs de commande, etc.)

import time
from collections import deque
from threading import Lock

NIVEAUX_VALIDES = {'info', 'warning', 'error'}


class LogBus:
    def __init__(self, maxlen=3000):
        self._buffer = deque(maxlen=maxlen)
        self._lock = Lock()

    def log(self, level, source, message, **extra):
        """Enregistre un événement. level: info|warning|error, source: libre (ex: 'agent', 'arduino', 'socket')"""
        if level not in NIVEAUX_VALIDES:
            level = 'info'

        entree = {
            'timestamp': time.time(),
            'level': level,
            'source': source,
            'message': message,
        }
        if extra:
            entree['extra'] = extra

        with self._lock:
            self._buffer.append(entree)

        prefixe = {'info': 'ℹ️', 'warning': '⚠️', 'error': '❌'}.get(level, 'ℹ️')
        print(f"{prefixe} [{source}] {message}")

        return entree

    def info(self, source, message, **extra):
        return self.log('info', source, message, **extra)

    def warning(self, source, message, **extra):
        return self.log('warning', source, message, **extra)

    def error(self, source, message, **extra):
        return self.log('error', source, message, **extra)

    def recent(self, limit=200, level=None, source=None, since=None):
        """Retourne les événements les plus récents, du plus ancien au plus récent."""
        with self._lock:
            items = list(self._buffer)

        if level:
            items = [i for i in items if i['level'] == level]
        if source:
            items = [i for i in items if i['source'] == source]
        if since:
            items = [i for i in items if i['timestamp'] > since]

        return items[-limit:]

    def clear(self):
        with self._lock:
            self._buffer.clear()


# Instance unique partagée par toute l'application
log_bus = LogBus()
