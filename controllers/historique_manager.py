import os
import glob
import re
from datetime import datetime, timedelta
from pathlib import Path

class HistoriqueManager:
    """Gestionnaire des fichiers d'historique"""
    
    @staticmethod
    def nettoyer_vieux_fichiers(retention_hours=24):

        # Patterns de fichiers à nettoyer
        patterns = [
            "historique_changements_*.log",
            "user_codes_*.json",
            "user_codes_user_*.json"  # Capture tous les fichiers commençant par user_codes_user_
        ]
        
        # Pattern plus spécifique avec regex pour le format exact
        pattern_regex = re.compile(r'user_codes_user_\d+_user_\d+_\d+_COM\d+\.json$')
        
        supprimes = []
        for pattern in patterns:
            fichiers = glob.glob(pattern)
            
            for fichier in fichiers:
                try:
                    if HistoriqueManager._fichier_a_supprimer(fichier, retention_hours):
                        os.remove(fichier)
                        supprimes.append(fichier)
                        print(f" Supprimé: {fichier}")
                        
                except Exception as e:
                    print(f"⚠️ Erreur avec {fichier}: {e}")
        try:
            tous_fichiers = os.listdir('.')
            for fichier in tous_fichiers:
                # Vérifier si c'est un fichier JSON qui correspond au pattern
                if fichier.endswith('.json') and 'user_codes_' in fichier:
                    chemin_complet = fichier
                    if chemin_complet not in supprimes:  # Éviter les doublons
                        try:
                            if HistoriqueManager._fichier_a_supprimer(chemin_complet, retention_hours):
                                os.remove(chemin_complet)
                                supprimes.append(chemin_complet)
                                print(f" Supprimé: {chemin_complet}")
                        except Exception as e:
                            print(f"⚠️ Erreur avec {chemin_complet}: {e}")
        except Exception as e:
            print(f"⚠️ Erreur scan complet: {e}")
        
        return supprimes
    
    @staticmethod
    def _fichier_a_supprimer(fichier, retention_hours):
        """Vérifie si un fichier doit être supprimé basé sur sa date"""
        try:
            # Essayer d'extraire un timestamp du nom
            nom = Path(fichier).stem
            timestamp_extrait = HistoriqueManager._extraire_timestamp(nom)
            
            if timestamp_extrait:
                date_fichier = datetime.fromtimestamp(timestamp_extrait)
            else:
                # Fallback: date de modification
                date_fichier = datetime.fromtimestamp(os.path.getmtime(fichier))
            
            # Calculer l'âge en heures
            age_heures = (datetime.now() - date_fichier).total_seconds() / 3600
            
            # Supprimer si trop vieux
            return age_heures > retention_hours
            
        except Exception as e:
            print(f"⚠️ Erreur analyse {fichier}: {e}")
            return False
    
    @staticmethod
    def _extraire_timestamp(nom_fichier):
        """Extrait le timestamp du nom du fichier"""
        parties = nom_fichier.split('_')
        for partie in parties:
            if partie.isdigit() and len(partie) == 10:
                try:
                    return int(partie)
                except:
                    pass
        match = re.search(r'_(\d{10})_', nom_fichier)
        if match:
            try:
                return int(match.group(1))
            except:
                pass
        
        return None
    
    @staticmethod
    def nettoyer_par_age(repertoire=".", jours_max=30):
        """
        Nettoie les fichiers de code utilisateur plus vieux que X jours
        """
        try:
            fichiers = glob.glob(os.path.join(repertoire, "user_codes_*.json"))
            supprimes = []
            date_limite = datetime.now() - timedelta(days=jours_max)
            
            for fichier in fichiers:
                try:
                    date_modif = datetime.fromtimestamp(os.path.getmtime(fichier))
                    
                    if date_modif < date_limite:
                        os.remove(fichier)
                        supprimes.append(fichier)
                        print(f" Supprimé (>{jours_max} jours): {fichier}")
                        
                except Exception as e:
                    print(f"⚠️ Erreur avec {fichier}: {e}")
            
            return supprimes
            
        except Exception as e:
            print(f"⚠️ Erreur nettoyage par âge: {e}")
            return []
    
    @staticmethod
    def nettoyer_automatique(app=None):
        """
        Nettoie automatiquement, peut être appelé depuis Flask
        """
        try:
            print("\n Début du nettoyage automatique...")
            
            # Nettoyage standard (24h) - fichiers temporaires
            supprimes_temp = HistoriqueManager.nettoyer_vieux_fichiers(24)
            
            # Nettoyage supplémentaire pour les vieux fichiers (30 jours)
            supprimes_vieux = HistoriqueManager.nettoyer_par_age(jours_max=30)
            
            tous_supprimes = supprimes_temp + supprimes_vieux
            
            if tous_supprimes:
                msg = f" {len(tous_supprimes)} fichiers nettoyés"
                if app:
                    app.logger.info(msg)
                else:
                    print(msg)
                
                # Afficher le détail
                for fichier in tous_supprimes:
                    print(f"   - {fichier}")
            else:
                print("✅ Aucun fichier à nettoyer")
            
            return tous_supprimes
                    
        except Exception as e:
            error_msg = f"❌ Erreur nettoyage automatique: {e}"
            if app:
                app.logger.error(error_msg)
            else:
                print(error_msg)
            return []
    
    @staticmethod
    def get_statistiques():
        """Retourne des stats sur les fichiers présents"""
        stats = {
            'historique': [],
            'user_codes': [],
            'total': 0,
            'espace_total': 0
        }
        
        # Chercher tous les fichiers concernés
        fichiers = glob.glob("user_codes_*.json") + glob.glob("historique_changements_*.log")
        
        for fichier in fichiers:
            try:
                taille = os.path.getsize(fichier)
                date_modif = datetime.fromtimestamp(os.path.getmtime(fichier))
                
                # Essayer d'extraire le timestamp du nom
                nom = Path(fichier).stem
                timestamp = HistoriqueManager._extraire_timestamp(nom)
                date_fichier = datetime.fromtimestamp(timestamp) if timestamp else date_modif
                
                file_info = {
                    'nom': fichier,
                    'taille': taille,
                    'taille_ko': taille / 1024,
                    'date_modification': date_modif.strftime('%Y-%m-%d %H:%M:%S'),
                    'date_contenu': date_fichier.strftime('%Y-%m-%d %H:%M:%S') if timestamp else 'N/A',
                    'age_jours': (datetime.now() - date_modif).days,
                    'timestamp': timestamp
                }
                
                if 'historique' in fichier:
                    stats['historique'].append(file_info)
                else:
                    stats['user_codes'].append(file_info)
                    
                stats['total'] += 1
                stats['espace_total'] += taille
                
            except Exception as e:
                print(f"⚠️ Erreur stats {fichier}: {e}")
        
        stats['espace_total_ko'] = stats['espace_total'] / 1024
        return stats