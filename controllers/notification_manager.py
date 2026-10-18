# controllers/notification_manager.py
import json
from datetime import datetime, date, timedelta
from db import db, Notification, EtudiantTP, Utilisateur, TP
from typing import List, Dict, Any, Optional

def envoyer_notifications_tp_creer(tp: TP, professeur: Utilisateur, db_session) -> int:
    """Envoyer des notifications à tous les étudiants inscrits à un TP"""
    try:
        # Vérifications préliminaires
        if not tp or not professeur:
            print("Erreur: TP ou professeur manquant")
            return 0
        
        # Récupérer tous les étudiants inscrits au TP
        inscriptions = EtudiantTP.query.filter_by(tp_id=tp.id).all()
        
        if not inscriptions:
            print(f"Information: Aucun étudiant inscrit au TP {tp.titre}")
            return 0
        
        notifications_crees = []
        for inscription in inscriptions:
            etudiant = db_session.session.get(Utilisateur, inscription.etudiant_id)
            
            if etudiant:
                # Préparer les données de la notification
                donnees_notification = {
                    'tp_id': tp.id,
                    'tp_titre': tp.titre,
                    'professeur_id': professeur.id,
                    'professeur_nom': f"{professeur.prenom} {professeur.nom}",
                    'module': tp.module,
                    'date_limite': tp.date_limite.isoformat() if tp.date_limite else None,
                    'nombre_questions': tp.nombre_questions,
                    'date_creation': tp.date_creation.isoformat() if tp.date_creation else datetime.now().isoformat()
                }
                
                # Message académique et professionnel
                date_limite_str = f"Date limite de soumission: {tp.date_limite.strftime('%d/%m/%Y à %H:%M')}" if tp.date_limite else "Aucune date limite spécifiée"
                
                message = f"""NOUVEAU TRAVAIL PRATIQUE DISPONIBLE

Objet: {tp.titre}
Module: {tp.module or 'Non spécifié'}
Enseignant: {professeur.prenom} {professeur.nom}
Nombre de questions: {tp.nombre_questions}
{date_limite_str}

Vous êtes inscrit à ce travail pratique. Veuillez accéder à la section "Travaux Pratiques" de la plateforme pour consulter les consignes et commencer votre travail.

Ce travail fait partie de votre évaluation continue. Nous vous recommandons de le commencer dès que possible pour anticiper d'éventuelles difficultés.

Cordialement,
L'équipe pédagogique"""
                
                # Créer la notification
                notification = Notification(
                    user_id=etudiant.id,
                    type_notification='nouveau_tp',
                    titre=f'Nouveau travail pratique disponible: {tp.titre}',
                    message=message,
                    donnees=json.dumps(donnees_notification, ensure_ascii=False)
                )
                
                db_session.session.add(notification)
                notifications_crees.append({
                    'etudiant': f"{etudiant.prenom} {etudiant.nom}",
                    'email': etudiant.email,
                    'etudiant_id': etudiant.id
                })
        
        db_session.session.commit()
        print(f"Succès: {len(notifications_crees)} notification(s) envoyée(s) pour le TP '{tp.titre}'")
        return len(notifications_crees)
        
    except Exception as e:
        print(f"Erreur lors de l'envoi des notifications: {str(e)}")
        db_session.session.rollback()
        return 0

def envoyer_notifications_tp_modifie(tp: TP, professeur: Utilisateur, db_session) -> int:
    """Envoyer des notifications lorsqu'un TP est modifié"""
    try:
        if not tp or not professeur:
            print("Erreur: TP ou professeur manquant")
            return 0
        
        inscriptions = EtudiantTP.query.filter_by(tp_id=tp.id).all()
        
        if not inscriptions:
            print(f"Information: Aucun étudiant inscrit au TP {tp.titre}")
            return 0
        
        notifications_envoyees = 0
        for inscription in inscriptions:
            etudiant = db_session.session.get(Utilisateur, inscription.etudiant_id)
            
            if etudiant:
                # Message académique avec informations claires
                message = f"""MODIFICATION D'UN TRAVAIL PRATIQUE

Objet: {tp.titre}
Enseignant responsable: {professeur.prenom} {professeur.nom}
Date de modification: {datetime.now().strftime('%d/%m/%Y à %H:%M')}
Nombre total de questions: {tp.nombre_questions}
Module: {tp.module or 'Non spécifié'}

Des modifications ont été apportées à ce travail pratique. Nous vous invitons à consulter la version mise à jour dans la section "Travaux Pratiques" de la plateforme.

Veuillez prendre en compte ces modifications dans votre travail. Si vous avez déjà commencé, vérifiez que vos réponses correspondent toujours aux nouvelles consignes.

Pour toute question concernant ces modifications, vous pouvez contacter votre enseignant.

Cordialement,
L'équipe pédagogique"""
                
                donnees_notification = {
                    'tp_id': tp.id,
                    'tp_titre': tp.titre,
                    'professeur': f"{professeur.prenom} {professeur.nom}",
                    'professeur_id': professeur.id,
                    'modification_date': datetime.now().isoformat(),
                    'nombre_questions': tp.nombre_questions,
                    'date_limite': tp.date_limite.isoformat() if tp.date_limite else None
                }
                
                notification = Notification(
                    user_id=etudiant.id,
                    type_notification='tp_modifie',
                    titre=f'Travail pratique modifié: {tp.titre}',
                    message=message,
                    donnees=json.dumps(donnees_notification, ensure_ascii=False)
                )
                
                db_session.session.add(notification)
                notifications_envoyees += 1
        
        db_session.session.commit()
        print(f"Succès: {notifications_envoyees} notification(s) de modification envoyée(s) pour le TP '{tp.titre}'")
        return notifications_envoyees
        
    except Exception as e:
        print(f"Erreur lors de l'envoi des notifications de modification: {str(e)}")
        db_session.session.rollback()
        return 0

def envoyer_notification_rappel_tp(tp: TP, etudiant: Utilisateur, db_session) -> bool:
    """Envoyer un rappel pour un TP"""
    try:
        if not tp or not etudiant:
            return False
        
        if not tp.date_limite:
            return False
        
        maintenant = datetime.now()
        jours_restants = (tp.date_limite - maintenant).days
        
        # Rappel si 1 à 3 jours restants
        if 1 <= jours_restants <= 3:
            # Vérifier si l'étudiant a déjà reçu un rappel aujourd'hui
            aujourd_hui = date.today()
            rappel_existant = Notification.query.filter(
                Notification.user_id == etudiant.id,
                Notification.type_notification == 'rappel_tp',
                db.func.date(Notification.date_creation) == aujourd_hui,
                Notification.donnees.like(f'%"tp_id":{tp.id}%')
            ).first()
            
            if rappel_existant:
                return False  # Déjà notifié aujourd'hui
            
            # Message adapté selon l'urgence
            if jours_restants == 1:
                sujet = "RAPPEL URGENT - TRAVAIL PRATIQUE À RENDRE DEMAIN"
                introduction = "Ceci est un rappel urgent concernant un travail pratique dont la date limite est demain."
            elif jours_restants == 2:
                sujet = "RAPPEL IMPORTANT - TRAVAIL PRATIQUE À RENDRE APRÈS-DEMAIN"
                introduction = "Ceci est un rappel important concernant un travail pratique dont la date limite approche."
            else:
                sujet = "RAPPEL - TRAVAIL PRATIQUE À RENDRE DANS 3 JOURS"
                introduction = "Ceci est un rappel concernant un travail pratique dont la date limite approche."
            
            message = f"""{sujet}

Cher(e) étudiant(e),

{introduction}

Détails du travail:
- Titre: {tp.titre}
- Module: {tp.module or 'Non spécifié'}
- Date limite: {tp.date_limite.strftime("%A %d %B %Y à %H:%M")}
- Jours restants: {jours_restants} jour(s)

Nous vous rappelons l'importance de respecter les délais de soumission pour une évaluation optimale. Si vous rencontrez des difficultés techniques ou pédagogiques, n'hésitez pas à contacter votre enseignant ou le support technique.

Veuillez soumettre votre travail avant la date limite indiquée.

Cordialement,
L'équipe pédagogique"""
            
            donnees_notification = {
                'tp_id': tp.id,
                'tp_titre': tp.titre,
                'date_limite': tp.date_limite.isoformat(),
                'jours_restants': jours_restants,
                'etudiant_id': etudiant.id,
                'notification_date': maintenant.isoformat()
            }
            
            notification = Notification(
                user_id=etudiant.id,
                type_notification='rappel_tp',
                titre=f'Rappel: {tp.titre}',
                message=message,
                donnees=json.dumps(donnees_notification, ensure_ascii=False)
            )
            
            db_session.session.add(notification)
            db_session.session.commit()
            print(f"Rappel envoyé à {etudiant.prenom} {etudiant.nom} pour le TP '{tp.titre}' ({jours_restants} jour(s) restant(s))")
            return True
        
        return False
                
    except Exception as e:
        print(f"Erreur lors de l'envoi du rappel TP: {str(e)}")
        db_session.session.rollback()
        return False

def envoyer_notifications_tp_complete(tp: TP, professeur: Utilisateur, db_session) -> int:
    """Envoyer des notifications quand un TP est complet (questions créées)"""
    try:
        if not tp or not professeur:
            print("Erreur: TP ou professeur manquant")
            return 0
        
        inscriptions = EtudiantTP.query.filter_by(tp_id=tp.id).all()
        
        if not inscriptions:
            print(f"Information: Aucun étudiant inscrit au TP {tp.titre}")
            return 0
        
        notifications_envoyees = 0
        for inscription in inscriptions:
            etudiant = db_session.session.get(Utilisateur, inscription.etudiant_id)
            
            if etudiant:
                date_limite_info = f"Date limite de soumission: {tp.date_limite.strftime('%d/%m/%Y à %H:%M')}" if tp.date_limite else "Aucune date limite spécifiée"
                
                message = f"""TRAVAIL PRATIQUE DISPONIBLE - VERSION FINALE

Objet: {tp.titre}
Statut: Complet et prêt pour réalisation
Enseignant: {professeur.prenom} {professeur.nom}
Module: {tp.module or 'Non spécifié'}
Nombre de questions: {tp.nombre_questions}
{date_limite_info}
Date de publication: {datetime.now().strftime('%d/%m/%Y à %H:%M')}

Vous pouvez désormais accéder à l'intégralité du "{tp.titre}" et commencer à répondre aux questions dans la section "Travaux Pratiques" de la plateforme.

Conseils pédagogiques:
1. Prenez le temps de lire attentivement toutes les consignes
2. Planifiez votre travail sur la durée disponible
3. Conservez une copie de vos réponses avant soumission
4. Contactez votre enseignant en cas de difficulté de compréhension

Bonne réalisation de ce travail.

Cordialement,
L'équipe pédagogique"""
                
                donnees_notification = {
                    'tp_id': tp.id,
                    'tp_titre': tp.titre,
                    'professeur': f"{professeur.prenom} {professeur.nom}",
                    'nombre_questions': tp.nombre_questions,
                    'date_completion': datetime.now().isoformat(),
                    'module': tp.module,
                    'date_limite': tp.date_limite.isoformat() if tp.date_limite else None
                }
                
                notification = Notification(
                    user_id=etudiant.id,
                    type_notification='tp_complet',
                    titre=f'Travail pratique disponible: {tp.titre}',
                    message=message,
                    donnees=json.dumps(donnees_notification, ensure_ascii=False)
                )
                
                db_session.session.add(notification)
                notifications_envoyees += 1
        
        db_session.session.commit()
        print(f"Succès: {notifications_envoyees} notification(s) de complétion envoyée(s) pour le TP '{tp.titre}'")
        return notifications_envoyees
        
    except Exception as e:
        print(f"Erreur lors de l'envoi des notifications de complétion: {str(e)}")
        db_session.session.rollback()
        return 0

def envoyer_rappels_tp_automatique(app) -> int:
    """Envoyer automatiquement des rappels pour les TP"""
    try:
        with app.app_context():
            # Récupérer tous les TPs actifs avec date limite approchant
            maintenant = datetime.now()
            date_futur = maintenant.replace(hour=23, minute=59, second=59)
            
            tps = TP.query.filter(
                TP.date_limite.isnot(None),
                TP.actif == True,
                TP.date_limite > maintenant,  # Non expirés
                TP.date_limite <= date_futur + timedelta(days=3)  # Dans les 3 prochains jours
            ).all()
            
            if not tps:
                print("Information: Aucun TP nécessitant un rappel")
                return 0
            
            total_rappels = 0
            total_tps = 0
            
            for tp in tps:
                # Récupérer tous les étudiants inscrits
                inscriptions = EtudiantTP.query.filter_by(tp_id=tp.id).all()
                
                if not inscriptions:
                    continue
                
                tp_rappels = 0
                for inscription in inscriptions:
                    etudiant = db.session.get(Utilisateur, inscription.etudiant_id)
                    if etudiant and envoyer_notification_rappel_tp(tp, etudiant, db):
                        tp_rappels += 1
                        total_rappels += 1
                
                if tp_rappels > 0:
                    total_tps += 1
                    print(f"  Rappels envoyés: {tp_rappels} pour le TP '{tp.titre}'")
            
            print(f"Succès: {total_rappels} rappel(s) envoyé(s) pour {total_tps} TP(s)")
            return total_rappels
            
    except Exception as e:
        print(f"Erreur lors de l'envoi des rappels automatiques: {str(e)}")
        return 0

def verifier_badges_nouveaux() -> Dict[str, Any]:
    """Vérifier et mettre à jour les badges Nouveau"""
    try:
        # Récupérer tous les TPs avec date de création
        tps = TP.query.filter(TP.date_creation.isnot(None)).all()
        
        if not tps:
            print("Information: Aucun TP à vérifier")
            return {'total': 0, 'nouveaux': 0, 'anciens': 0}
        
        compteur = {
            'total': len(tps),
            'nouveaux': 0,
            'anciens': 0,
            'tps_nouveaux': [],
            'tps_anciens': []
        }
        
        maintenant = datetime.now()
        
        for tp in tps:
            if tp.date_creation:
                delta = maintenant - tp.date_creation
                
                # TP considéré comme "nouveau" pendant 3 jours
                if delta.days < 3:
                    compteur['nouveaux'] += 1
                    compteur['tps_nouveaux'].append({
                        'id': tp.id,
                        'titre': tp.titre,
                        'jours': delta.days,
                        'date_creation': tp.date_creation.strftime('%d/%m/%Y')
                    })
                else:
                    compteur['anciens'] += 1
                    compteur['tps_anciens'].append({
                        'id': tp.id,
                        'titre': tp.titre,
                        'jours': delta.days,
                        'date_creation': tp.date_creation.strftime('%d/%m/%Y')
                    })
        
        # Rapport de vérification
        print(f"Vérification des badges 'Nouveau' terminée")
        print(f"Total TPs analysés: {compteur['total']}")
        print(f"TPs marqués comme 'Nouveau': {compteur['nouveaux']}")
        print(f"TPs non marqués comme 'Nouveau': {compteur['anciens']}")
        
        # Affichage détaillé des TPs nouveaux si existants
        if compteur['nouveaux'] > 0:
            print("\nTPs actuellement marqués comme 'Nouveau':")
            for tp_info in compteur['tps_nouveaux']:
                print(f"  - {tp_info['titre']} (créé le {tp_info['date_creation']}, il y a {tp_info['jours']} jour(s))")
        
        return compteur
        
    except Exception as e:
        print(f"Erreur lors de la vérification des badges: {str(e)}")
        return {'error': str(e), 'total': 0, 'nouveaux': 0, 'anciens': 0}