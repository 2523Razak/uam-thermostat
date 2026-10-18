# controllers/connection_cleaner.py
import threading
import time
from datetime import datetime

class ConnectionCleaner:
    """Nettoie périodiquement les connexions inactives"""
    
    def __init__(self, connexions_dict):
        self.connexions_arduino = connexions_dict
        self.running = False
        self.thread = None
    
    def start(self):
        """Démarre le nettoyage périodique"""
        if self.running:
            return
        
        self.running = True
        self.thread = threading.Thread(target=self._cleanup_loop, daemon=True)
        self.thread.start()
        print("✅ Nettoyage périodique démarré")
    
    def stop(self):
        """Arrête le nettoyage"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=5)
        print("🛑 Nettoyage périodique arrêté")
    
    def _cleanup_loop(self):
        """Boucle de nettoyage"""
        while self.running:
            try:
                self._cleanup_inactive_connections()
                time.sleep(300)  # Toutes les 5 minutes
            except Exception as e:
                print(f"❌ Erreur nettoyage périodique: {e}")
                time.sleep(60)
    
    def _cleanup_inactive_connections(self):
        """Nettoie les connexions inactives"""
        current_time = time.time()
        to_remove = []
        
        for id_connexion, connexion in self.connexions_arduino.items():
            last_activity = connexion.get('last_activity', 0)
            inactive_duration = current_time - last_activity
            
            # Nettoyer après 1 heure d'inactivité
            if inactive_duration > 3600:
                to_remove.append(id_connexion)
        
        for id_connexion in to_remove:
            try:
                print(f"🧹 Nettoyage automatique connexion {id_connexion}")
                
                # Fermer la connexion
                if self.connexions_arduino[id_connexion].get('connecte'):
                    self.connexions_arduino[id_connexion]['connecte'] = False
                
                # Fermer le port série si ouvert
                if 'serial' in self.connexions_arduino[id_connexion]:
                    try:
                        serial_port = self.connexions_arduino[id_connexion]['serial']
                        if serial_port and serial_port.is_open:
                            serial_port.close()
                    except:
                        pass
                
            except Exception as e:
                print(f"⚠️ Erreur nettoyage automatique: {e}")
        
        if to_remove:
            print(f"✅ Nettoyage terminé: {len(to_remove)} connexion(s) nettoyée(s)")