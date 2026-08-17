# utils/audit_logger.py
import threading
import json
import time
import os
from datetime import datetime
from flask import request

class AuditLogger:
    """Gestionnaire des logs d'audit avec écriture fichier + mémoire"""
    
    def __init__(self, log_dir='logs'):
        self.logs = []
        self.lock = threading.Lock()
        self.max_logs = 1000
        
        # Configuration des fichiers
        self.log_dir = log_dir
        self._ensure_log_directory()
    
    def _ensure_log_directory(self):
        """Crée le dossier de logs s'il n'existe pas"""
        try:
            if not os.path.exists(self.log_dir):
                os.makedirs(self.log_dir, exist_ok=True)
                print(f"Dossier de logs créé: {self.log_dir}")
        except Exception as e:
            print(f"❌ Erreur création dossier logs: {e}")
    
    def _get_current_log_file(self):
        """Retourne le nom du fichier de log du mois courant"""
        mois_courant = datetime.now().strftime("%Y%m")
        return os.path.join(self.log_dir, f'historique_changements_{mois_courant}.log')
    
    def _write_to_file(self, log_entry):
        """Écrit un log dans le fichier"""
        try:
            log_file = self._get_current_log_file()
            
            # Format JSON pour une ligne par entrée
            with open(log_file, 'a', encoding='utf-8') as f:
                f.write(json.dumps(log_entry, ensure_ascii=False) + '\n')
                
        except Exception as e:
            print(f"❌ Erreur écriture fichier log: {e}")
    
    def log(self, event_type, user_id, connection_id, details, ip_address=None):
        """Enregistre un événement d'audit (mémoire + fichier)"""
        try:
            timestamp = datetime.now()
            
            log_entry = {
                'timestamp': timestamp.strftime('%Y-%m-%d %H:%M:%S'),
                'timestamp_raw': timestamp.isoformat(),
                'event_type': event_type,
                'user_id': user_id,
                'connection_id': connection_id,
                'details': details,
                'ip_address': ip_address or self._get_client_ip()
            }
            
            # STOCKAGE EN MÉMOIRE
            with self.lock:
                self.logs.append(log_entry)
                if len(self.logs) > self.max_logs:
                    self.logs = self.logs[-self.max_logs:]
            
            # ÉCRITURE SUR DISQUE (NOUVEAU)
            self._write_to_file(log_entry)
            
            print(f" AUDIT: {event_type} - User:{user_id} - {details}")
            
        except Exception as e:
            print(f"❌ Erreur log audit: {e}")
    
    def _get_client_ip(self):
        """Récupère l'adresse IP du client"""
        try:
            if request:
                return request.remote_addr
        except:
            pass
        return "N/A"
    
    def get_user_logs(self, user_id, limit=50):
        """Récupère les logs d'un utilisateur (depuis mémoire)"""
        with self.lock:
            user_logs = [log for log in self.logs if log['user_id'] == user_id]
            return user_logs[-limit:] if user_logs else []
        
    # Lecture des logs depuis le fichier
    def read_logs_from_file(self, mois=None, limit=1000):
        """Lit les logs depuis le fichier"""
        try:
            if mois is None:
                mois = datetime.now().strftime("%Y%m")
            
            log_file = os.path.join(self.log_dir, f'historique_changements_{mois}.log')
            
            if not os.path.exists(log_file):
                return []
            
            logs = []
            with open(log_file, 'r', encoding='utf-8') as f:
                for i, line in enumerate(f):
                    if i >= limit:
                        break
                    try:
                        logs.append(json.loads(line.strip()))
                    except:
                        continue
            
            return logs
            
        except Exception as e:
            print(f"❌ Erreur lecture fichier log: {e}")
            return []
    
    def get_logs_by_date(self, date_str, mois=None):
        """Récupère les logs d'une date spécifique"""
        try:
            logs = self.read_logs_from_file(mois)
            return [log for log in logs if log['timestamp'].startswith(date_str)]
        except:
            return []
    
    def get_recent_errors(self, minutes=60):
        """Récupère les erreurs récentes"""
        try:
            limite = datetime.now().timestamp() - (minutes * 60)
            logs = self.read_logs_from_file()
            
            errors = []
            for log in logs:
                if log['event_type'] in ['ERROR', 'PORT_FORCE_RELEASE']:
                    log_time = datetime.fromisoformat(log['timestamp_raw']).timestamp()
                    if log_time > limite:
                        errors.append(log)
            
            return errors
        except:
            return []

audit_logger = AuditLogger()