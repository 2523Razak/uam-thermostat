# api/users.py - Routes API pour la gestion des utilisateurs
from flask import jsonify, request, session, flash, redirect, url_for
from utils.decorators import login_required, admin_required
from utils.email_utils import envoyer_email, envoyer_notification_statut, envoyer_confirmation_changement_mdp
from utils.security import hash_password, verify_password
from db import db, Utilisateur
from datetime import datetime
import re

def register_user_routes(app):
    """Enregistre toutes les routes API pour les utilisateurs"""
    
    #---------------------------------------------
    # Routes api pour la gestion des utilisateurs
    #---------------------------------------------
    @app.route('/api/current_user_info')
    @login_required
    def get_current_user_info():
        """API pour obtenir les informations de l'utilisateur connecté"""
        try:
            user_id = session.get('user_id')
            utilisateur = Utilisateur.query.get(user_id)
            
            if not utilisateur:
                return jsonify({'success': False, 'message': 'Utilisateur non trouvé'})
            
            return jsonify({
                'success': True,
                'utilisateur': {
                    'id': utilisateur.id,
                    'nom': utilisateur.nom,
                    'prenom': utilisateur.prenom,
                    'email': utilisateur.email,
                    'organisation': utilisateur.organisation,
                    'matricule': utilisateur.matricule,
                    'statut': utilisateur.statut,
                    'date_naissance': utilisateur.date_naissance.strftime('%d/%m/%Y') if utilisateur.date_naissance else None,
                    'lieu_naissance': utilisateur.lieu_naissance,
                    'date_inscription': utilisateur.date_inscription.strftime('%d/%m/%Y à %H:%M')
                }
            })
            
        except Exception as e:
            print(f"Erreur récupération info utilisateur: {e}")
            return jsonify({'success': False, 'message': f'Erreur: {str(e)}'})
    
    #----------------------------------------------------
    # Routes api pour la gestion du mot de passe et de l'email
    #----------------------------------------------------
    @app.route('/api/changer_mot_de_passe', methods=['POST'])
    @login_required
    def changer_mot_de_passe():
        """API pour changer le mot de passe de l'utilisateur connecté"""
        try:
            donnees = request.json
            ancien_mot_de_passe = donnees.get('ancien_mot_de_passe')
            nouveau_mot_de_passe = donnees.get('nouveau_mot_de_passe')
            
            if not ancien_mot_de_passe or not nouveau_mot_de_passe:
                return jsonify({'success': False, 'message': 'Tous les champs sont obligatoires'})
            
            if len(nouveau_mot_de_passe) < 6:
                return jsonify({'success': False, 'message': 'Le mot de passe doit contenir au moins 6 caractères'})
            
            user_id = session.get('user_id')
            utilisateur = Utilisateur.query.get(user_id)
            
            if not utilisateur:
                return jsonify({'success': False, 'message': 'Utilisateur non trouvé'})
            
            # Vérifier l'ancien mot de passe
            mot_de_passe_valide, _ = verify_password(utilisateur.password, ancien_mot_de_passe)
            if not mot_de_passe_valide:
                return jsonify({'success': False, 'message': 'Ancien mot de passe incorrect'})
            
            # Vérifier si le nouveau mot de passe est différent de l'ancien
            if ancien_mot_de_passe == nouveau_mot_de_passe:
                return jsonify({'success': False, 'message': 'Le nouveau mot de passe doit être différent de l\'ancien'})
            
            # Mettre à jour le mot de passe
            utilisateur.password = hash_password(nouveau_mot_de_passe)
            db.session.commit()
            
            print(f"Mot de passe changé pour l'utilisateur {utilisateur.email}")
            
            # Envoyer un email de confirmation
            sujet_confirmation = "Confirmation de changement de mot de passe"
            contenu_confirmation = f"""
            <!DOCTYPE html>
            <html>
            <head><meta charset="UTF-8"></head>
            <body>
                <h2>Changement de mot de passe réussi</h2>
                <p>Bonjour {utilisateur.prenom} {utilisateur.nom},</p>
                <p>Votre mot de passe sur la plateforme Thermostat_UAM a été changé avec succès.</p>
                <p><strong>Détails :</strong></p>
                <ul>
                    <li>Date du changement : {datetime.now().strftime('%d/%m/%Y à %H:%M')}</li>
                    <li>Adresse IP : {request.remote_addr}</li>
                </ul>
                <p>Si vous n'êtes pas à l'origine de ce changement, veuillez contacter immédiatement l'administrateur.</p>
                <p>Cordialement,<br>L'équipe Thermostat_UAM</p>
            </body>
            </html>
            """
            
            envoyer_email(utilisateur.email, sujet_confirmation, contenu_confirmation)
            
            return jsonify({
                'success': True, 
                'message': 'Mot de passe changé avec succès'
            })
            
        except Exception as e:
            db.session.rollback()
            print(f"Erreur changement mot de passe: {e}")
            return jsonify({'success': False, 'message': f'Erreur: {str(e)}'})
    
    #----------------------------------------------------
    # Routes api pour la gestion de l'email
    #----------------------------------------------------
    @app.route('/api/changer_email', methods=['POST'])
    @login_required
    def changer_email():
        """API pour changer l'email de l'utilisateur connecté"""
        try:
            donnees = request.json
            mot_de_passe = donnees.get('mot_de_passe')
            nouvel_email = donnees.get('nouvel_email')
            
            if not mot_de_passe or not nouvel_email:
                return jsonify({'success': False, 'message': 'Tous les champs sont obligatoires'})
            
            # Validation de l'email
            if not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', nouvel_email):
                return jsonify({'success': False, 'message': 'Format d\'email invalide'})
            
            user_id = session.get('user_id')
            utilisateur = Utilisateur.query.get(user_id)
            
            if not utilisateur:
                return jsonify({'success': False, 'message': 'Utilisateur non trouvé'})
            
            # Vérifier le mot de passe
            mot_de_passe_valide, doit_rehasher = verify_password(utilisateur.password, mot_de_passe)
            if not mot_de_passe_valide:
                return jsonify({'success': False, 'message': 'Mot de passe incorrect'})
            if doit_rehasher:
                utilisateur.password = hash_password(mot_de_passe)
            
            # Vérifier si l'email existe déjà
            email_existe = Utilisateur.query.filter_by(email=nouvel_email).first()
            if email_existe and email_existe.id != user_id:
                return jsonify({'success': False, 'message': 'Cet email est déjà utilisé par un autre utilisateur'})
            
            # Vérifier si l'email est le même que l'actuel
            if utilisateur.email == nouvel_email:
                return jsonify({'success': False, 'message': 'Le nouvel email doit être différent de l\'actuel'})
            
            # Sauvegarder l'ancien email
            ancien_email = utilisateur.email
            
            # Mettre à jour l'email
            utilisateur.email = nouvel_email
            db.session.commit()
            
            # Mettre à jour la session
            session['user_email'] = nouvel_email
            
            print(f"Email changé pour l'utilisateur {ancien_email} -> {nouvel_email}")
            
            # Envoyer un email de confirmation
            sujet_confirmation = "Notification de changement d'email"
            contenu_confirmation = f"""
            <!DOCTYPE html>
            <html>
            <head><meta charset="UTF-8"></head>
            <body>
                <h2>Changement d'adresse email</h2>
                <p>Bonjour {utilisateur.prenom} {utilisateur.nom},</p>
                <p>Votre adresse email sur la plateforme Thermostat_UAM a été changée.</p>
                <p><strong>Détails :</strong></p>
                <ul>
                    <li>Ancien email : {ancien_email}</li>
                    <li>Nouvel email : {nouvel_email}</li>
                    <li>Date du changement : {datetime.now().strftime('%d/%m/%Y à %H:%M')}</li>
                    <li>Adresse IP : {request.remote_addr}</li>
                </ul>
                <p>Si vous n'êtes pas à l'origine de ce changement, veuillez contacter immédiatement l'administrateur.</p>
                <p>Cordialement,<br>L'équipe Thermostat_UAM</p>
            </body>
            </html>
            """
            
            envoyer_email(ancien_email, sujet_confirmation, contenu_confirmation)
            
            return jsonify({
                'success': True, 
                'message': 'Email changé avec succès',
                'nouvel_email': nouvel_email
            })
            
        except Exception as e:
            db.session.rollback()
            print(f"Erreur changement email: {e}")
            return jsonify({'success': False, 'message': f'Erreur: {str(e)}'})
    
    #------------------------------------------------------------
    # Routes api pour la gestion des utilisateurs par les admins
    #------------------------------------------------------------
    @app.route('/api/changer_statut', methods=['POST'])
    @login_required
    @admin_required
    def changer_statut():
        """API pour changer le statut d'un utilisateur"""
        try:
            donnees = request.json
            id_utilisateur = donnees.get('id_utilisateur')
            nouveau_statut = donnees.get('statut')
            raison = donnees.get('raison')
            
            if not id_utilisateur or not nouveau_statut:
                return jsonify({'success': False, 'message': 'Données manquantes'})
            
            if nouveau_statut not in ['user', 'admin', 'bloque']:
                return jsonify({'success': False, 'message': 'Statut invalide'})
            
            utilisateur = Utilisateur.query.get(id_utilisateur)
            
            if not utilisateur:
                return jsonify({'success': False, 'message': 'Utilisateur non trouvé'})
            
            ancien_statut = utilisateur.statut
            
            if utilisateur.id == session.get('user_id') and nouveau_statut == 'bloque':
                return jsonify({'success': False, 'message': 'Vous ne pouvez pas bloquer votre propre compte'})
            
            utilisateur.statut = nouveau_statut
            db.session.commit()
            
            print(f"Statut utilisateur {id_utilisateur} changé: {ancien_statut} -> {nouveau_statut}")
            
            email_envoye = envoyer_notification_statut(utilisateur, ancien_statut, nouveau_statut, raison)
            
            return jsonify({
                'success': True, 
                'message': f'Statut changé en {nouveau_statut}',
                'nouveau_statut': nouveau_statut,
                'email_envoye': email_envoye
            })
            
        except Exception as e:
            db.session.rollback()
            print(f"Erreur changement statut: {e}")
            return jsonify({'success': False, 'message': f'Erreur: {str(e)}'})
    
    #-------------------------------------------------------------------
    #Routes api pour la suppression et la récupération des utilisateurs
    #-------------------------------------------------------------------
    @app.route('/api/supprimer_utilisateur', methods=['POST'])
    @login_required
    @admin_required
    def supprimer_utilisateur():
        """API pour supprimer un utilisateur"""
        try:
            donnees = request.json
            id_utilisateur = donnees.get('id_utilisateur')
            
            if not id_utilisateur:
                return jsonify({'success': False, 'message': 'ID utilisateur manquant'})
            
            utilisateur = Utilisateur.query.get(id_utilisateur)
            
            if not utilisateur:
                return jsonify({'success': False, 'message': 'Utilisateur non trouvé'})
            
            if utilisateur.id == session.get('user_id'):
                return jsonify({'success': False, 'message': 'Vous ne pouvez pas supprimer votre propre compte'})
            
            nom_utilisateur = f"{utilisateur.prenom} {utilisateur.nom}"
            email_utilisateur = utilisateur.email
            
            sujet_suppression = "Votre compte Thermostat_UAM a été supprimé"
            contenu_suppression = f"""
            <!DOCTYPE html>
            <html>
            <head><meta charset="UTF-8"></head>
            <body>
                <h2>Notification de suppression de compte</h2>
                <p>Bonjour {utilisateur.prenom} {utilisateur.nom},</p>
                <p>Votre compte sur la plateforme Thermostat_UAM a été supprimé par un administrateur.</p>
                <p><strong>Détails :</strong></p>
                <ul>
                    <li>Nom : {utilisateur.nom}</li>
                    <li>Prénom : {utilisateur.prenom}</li>
                    <li>Email : {utilisateur.email}</li>
                    <li>Date de suppression : {datetime.now().strftime('%d/%m/%Y à %H:%M')}</li>
                </ul>
                <p>Si vous pensez qu'il s'agit d'une erreur, veuillez contacter l'administrateur du système.</p>
                <p>Cordialement,<br>L'équipe Thermostat_UAM</p>
            </body>
            </html>
            """
            
            email_envoye = envoyer_email(email_utilisateur, sujet_suppression, contenu_suppression)
            
            db.session.delete(utilisateur)
            db.session.commit()
            
            print(f"Utilisateur supprimé: {nom_utilisateur} ({email_utilisateur})")
            
            return jsonify({
                'success': True, 
                'message': f'Utilisateur {nom_utilisateur} supprimé avec succès',
                'email_envoye': email_envoye
            })
            
        except Exception as e:
            db.session.rollback()
            print(f"Erreur suppression utilisateur: {e}")
            return jsonify({'success': False, 'message': f'Erreur: {str(e)}'})
    
    #----------------------------------------------------
    # Routes api pour la gestion des utilisateurs
    #----------------------------------------------------
    @app.route('/api/utilisateur/<int:id_utilisateur>')
    @login_required
    def get_utilisateur(id_utilisateur):
        """API pour obtenir les détails d'un utilisateur"""
        try:
            utilisateur = Utilisateur.query.get(id_utilisateur)
            
            if not utilisateur:
                return jsonify({'success': False, 'message': 'Utilisateur non trouvé'})
            
            return jsonify({
                'success': True,
                'utilisateur': {
                    'id': utilisateur.id,
                    'nom': utilisateur.nom,
                    'prenom': utilisateur.prenom,
                    'email': utilisateur.email,
                    'organisation': utilisateur.organisation,
                    'matricule': utilisateur.matricule,
                    'statut': utilisateur.statut,
                    'date_inscription': utilisateur.date_inscription.strftime('%d/%m/%Y à %H:%M')
                }
            })
            
        except Exception as e:
            print(f"Erreur récupération utilisateur: {e}")
            return jsonify({'success': False, 'message': f'Erreur: {str(e)}'})
    
    # ----------------------------------------------------
    # NOUVELLES ROUTES AJOUTÉES
    # ----------------------------------------------------
    
    @app.route('/api/users', methods=['GET'])
    @login_required
    @admin_required
    def get_users():
        """API pour récupérer tous les utilisateurs"""
        try:
            users = Utilisateur.query.order_by(Utilisateur.date_inscription.desc()).all()
            
            users_data = []
            for user in users:
                users_data.append({
                    'id': user.id,
                    'nom': user.nom,
                    'prenom': user.prenom,
                    'email': user.email,
                    'matricule': user.matricule,
                    'statut': user.statut,
                    'email_verifie': user.email_verifie if hasattr(user, 'email_verifie') else False,
                    'organisation': user.organisation,
                    'date_inscription': user.date_inscription.isoformat() if user.date_inscription else None,
                    'date_verification': user.date_verification.isoformat() if hasattr(user, 'date_verification') and user.date_verification else None
                })
            
            return jsonify({
                'success': True,
                'users': users_data,
                'count': len(users_data)
            })
            
        except Exception as e:
            print(f"Erreur récupération utilisateurs: {e}")
            return jsonify({'success': False, 'message': str(e)}), 500
    
    @app.route('/api/users/<int:user_id>', methods=['GET', 'PUT', 'DELETE'])
    @login_required
    @admin_required
    def manage_user(user_id):
        """API pour gérer un utilisateur spécifique"""
        try:
            user = db.session.get(Utilisateur, user_id)
            
            if not user:
                return jsonify({'success': False, 'message': 'Utilisateur non trouvé'}), 404
            
            if request.method == 'GET':
                return jsonify({
                    'success': True,
                    'user': {
                        'id': user.id,
                        'nom': user.nom,
                        'prenom': user.prenom,
                        'email': user.email,
                        'matricule': user.matricule,
                        'statut': user.statut,
                        'email_verifie': user.email_verifie if hasattr(user, 'email_verifie') else False,
                        'organisation': user.organisation,
                        'date_naissance': user.date_naissance.isoformat() if user.date_naissance else None,
                        'lieu_naissance': user.lieu_naissance,
                        'date_inscription': user.date_inscription.isoformat() if user.date_inscription else None,
                        'date_verification': user.date_verification.isoformat() if hasattr(user, 'date_verification') and user.date_verification else None
                    }
                })
            
            elif request.method == 'PUT':
                data = request.get_json()
                
                if not data:
                    return jsonify({'success': False, 'message': 'Aucune donnée reçue'}), 400
                
                # Mettre à jour les champs autorisés
                if 'nom' in data:
                    user.nom = data['nom']
                if 'prenom' in data:
                    user.prenom = data['prenom']
                if 'email' in data:
                    user.email = data['email']
                if 'matricule' in data:
                    user.matricule = data['matricule']
                if 'statut' in data:
                    user.statut = data['statut']
                if 'organisation' in data:
                    user.organisation = data['organisation']
                
                db.session.commit()
                
                return jsonify({
                    'success': True,
                    'message': 'Utilisateur mis à jour avec succès'
                })
            
            elif request.method == 'DELETE':
                # Vérifier qu'on ne supprime pas son propre compte
                if user.id == session.get('user_id'):
                    return jsonify({'success': False, 'message': 'Vous ne pouvez pas supprimer votre propre compte'}), 400
                
                db.session.delete(user)
                db.session.commit()
                
                return jsonify({
                    'success': True,
                    'message': 'Utilisateur supprimé avec succès'
                })
                
        except Exception as e:
            db.session.rollback()
            print(f"Erreur gestion utilisateur: {e}")
            return jsonify({'success': False, 'message': str(e)}), 500
    
    @app.route('/api/users/search', methods=['GET'])
    @login_required
    def search_users():
        """API pour rechercher des utilisateurs"""
        try:
            query = request.args.get('q', '').strip()
            
            if not query or len(query) < 2:
                return jsonify({'success': False, 'message': 'Requête trop courte'}), 400
            
            users = Utilisateur.query.filter(
                (Utilisateur.nom.ilike(f'%{query}%')) |
                (Utilisateur.prenom.ilike(f'%{query}%')) |
                (Utilisateur.email.ilike(f'%{query}%')) |
                (Utilisateur.matricule.ilike(f'%{query}%'))
            ).limit(10).all()
            
            users_data = []
            for user in users:
                users_data.append({
                    'id': user.id,
                    'nom': user.nom,
                    'prenom': user.prenom,
                    'email': user.email,
                    'matricule': user.matricule,
                    'statut': user.statut,
                    'organisation': user.organisation
                })
            
            return jsonify({
                'success': True,
                'users': users_data,
                'count': len(users_data)
            })
            
        except Exception as e:
            print(f"Erreur recherche utilisateurs: {e}")
            return jsonify({'success': False, 'message': str(e)}), 500

    # ============================================================================
    # ACTIVATION MANUELLE DE COMPTE (ADMIN)
    # ============================================================================

    @app.route('/api/activer_compte_manuel', methods=['POST'])
    @login_required
    @admin_required
    def activer_compte_manuel():
        """API pour activer manuellement un compte en attente de vérification"""
        try:
            data = request.json
            user_id = data.get('user_id')
            
            if not user_id:
                return jsonify({'success': False, 'message': 'ID utilisateur manquant'}), 400
            
            utilisateur = Utilisateur.query.get(user_id)
            
            if not utilisateur:
                return jsonify({'success': False, 'message': 'Utilisateur non trouvé'}), 404
            
            # Vérifier si le compte est déjà actif
            if utilisateur.email_verifie:
                return jsonify({
                    'success': False, 
                    'message': f'Le compte de {utilisateur.prenom} {utilisateur.nom} est déjà actif'
                }), 400
            
            # Vérifier si le compte est en attente
            if utilisateur.statut != 'pending' and not utilisateur.email_verifie:
                # Cas où le compte a un autre statut mais email non vérifié
                pass
            
            # Sauvegarder l'ancien statut
            ancien_statut = utilisateur.statut
            
            # Activer le compte
            utilisateur.email_verifie = True
            
            # Si le statut est 'pending', le passer à 'user'
            if utilisateur.statut == 'pending':
                utilisateur.statut = 'user'
            
            utilisateur.date_verification = datetime.now()
            utilisateur.token_verification = None
            utilisateur.token_expiration = None
            
            db.session.commit()
            
            print(f"✅ Compte activé manuellement par l'admin: {utilisateur.email} (ancien statut: {ancien_statut})")
            
            # Envoyer un email de confirmation d'activation (optionnel mais recommandé)
            email_envoye = False
            try:
                from utils.email_utils import envoyer_email_bienvenue
                email_envoye = envoyer_email_bienvenue(utilisateur)
                if email_envoye:
                    print(f"📧 Email de bienvenue envoyé à {utilisateur.email}")
            except Exception as e:
                print(f"⚠️ Erreur envoi email bienvenue: {e}")
            
            return jsonify({
                'success': True,
                'message': f'Compte de {utilisateur.prenom} {utilisateur.nom} activé avec succès',
                'email_envoye': email_envoye,
                'nouveau_statut': utilisateur.statut
            })
            
        except Exception as e:
            db.session.rollback()
            print(f"Erreur activation compte: {e}")
            import traceback
            traceback.print_exc()
            return jsonify({'success': False, 'message': str(e)}), 500