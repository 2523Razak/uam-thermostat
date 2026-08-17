# utils/decorators.py - VERSION COMPLÈTE
from functools import wraps
from flask import jsonify, request, session, current_app, redirect, url_for, flash
import time

# ============================================================================
# DÉCORATEURS POUR PAGES WEB (HTML)
# ============================================================================

def login_required(f):
    """Vérifie que l'utilisateur est connecté - POUR PAGES HTML"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Veuillez vous connecter pour accéder à cette page', 'error')
            return redirect(url_for('connections'))
        return f(*args, **kwargs)
    return decorated_function


def admin_required(f):
    """Vérifie que l'utilisateur est admin - POUR PAGES HTML"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get('user_statut') != 'admin':
            flash('Accès réservé aux administrateurs', 'error')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function


# ============================================================================
# DÉCORATEURS POUR API (JSON)
# ============================================================================

def api_login_required(f):
    """Vérifie que l'utilisateur est connecté - POUR API JSON"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({
                'success': False, 
                'message': 'Authentification requise'
            }), 401
        return f(*args, **kwargs)
    return decorated_function


def api_admin_required(f):
    """Vérifie que l'utilisateur est admin - POUR API JSON"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get('user_statut') != 'admin':
            return jsonify({
                'success': False, 
                'message': 'Accès réservé aux administrateurs'
            }), 403
        return f(*args, **kwargs)
    return decorated_function


# ============================================================================
# DÉCORATEUR POUR PROPRIÉTÉ DES CONNEXIONS (COMMUN AUX DEUX)
# ============================================================================

def connection_ownership_required(f):
    """Vérifie que l'utilisateur possède la connexion Arduino"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            # Récupérer l'ID de connexion
            if request.method == 'GET':
                connection_id = request.args.get('connection_id')
            else:
                donnees = request.json if request.is_json else {}
                connection_id = donnees.get('connection_id')
            
            if not connection_id:
                return jsonify({
                    'success': False, 
                    'message': 'ID de connexion manquant'
                }), 400
            
            # Récupérer arduino_controller depuis app.py via current_app
            arduino_controller = current_app.config.get('arduino_controller')
            
            if not arduino_controller:
                print("❌ ERREUR: arduino_controller non trouvé dans app.config")
                return jsonify({
                    'success': False, 
                    'message': 'Contrôleur Arduino non disponible'
                }), 500
            
            if not hasattr(arduino_controller, 'connexions_arduino'):
                return jsonify({
                    'success': False, 
                    'message': 'Système de connexions non initialisé'
                }), 500
            
            if connection_id not in arduino_controller.connexions_arduino:
                return jsonify({
                    'success': False, 
                    'message': 'Connexion non trouvée'
                }), 404
            
            current_user_id = session.get('user_id')
            connection_user_id = arduino_controller.connexions_arduino[connection_id].get('user_id')
            
            # Si user_id n'est pas stocké (anciennes connexions), autoriser l'accès
            if connection_user_id is None:
                print(f"⚠️  Connexion {connection_id} sans user_id, accès autorisé pour rétrocompatibilité")
                # On autorise mais on stocke le user_id pour la prochaine fois
                arduino_controller.connexions_arduino[connection_id]['user_id'] = current_user_id
                arduino_controller.connexions_arduino[connection_id]['last_activity'] = time.time()
                return f(*args, **kwargs)
            
            if current_user_id != connection_user_id:
                # Log d'accès non autorisé
                print(f"🚨 ACCÈS NON AUTORISÉ: "
                      f"User {current_user_id} tente d'accéder à {connection_id} "
                      f"(propriétaire: {connection_user_id})")
                
                return jsonify({
                    'success': False,
                    'message': 'Accès non autorisé à cette connexion'
                }), 403
            
            # Mettre à jour le timestamp d'activité
            arduino_controller.connexions_arduino[connection_id]['last_activity'] = time.time()
            
            return f(*args, **kwargs)
            
        except Exception as e:
            print(f"❌ Erreur vérification propriété: {e}")
            import traceback
            traceback.print_exc()
            return jsonify({
                'success': False, 
                'message': f'Erreur de vérification: {str(e)}'
            }), 500
    
    return decorated_function


# ============================================================================
# DÉCORATEUR POUR VÉRIFIER SI C'EST UNE REQUÊTE API
# ============================================================================

def requires_api_or_html(f):
    """
    Détecte automatiquement si c'est une requête API ou web
    et applique la vérification appropriée
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Détecter si c'est une requête API (basé sur le header ou le chemin)
        is_api_request = (
            request.path.startswith('/api/') or
            request.path.startswith('/arduino/') or
            request.accept_mimetypes.best == 'application/json' or
            request.is_json
        )
        
        if is_api_request:
            # Utiliser la vérification API
            if 'user_id' not in session:
                return jsonify({
                    'success': False, 
                    'message': 'Authentification requise'
                }), 401
        else:
            # Utiliser la vérification web
            if 'user_id' not in session:
                flash('Veuillez vous connecter pour accéder à cette page', 'error')
                return redirect(url_for('connections'))
        
        return f(*args, **kwargs)
    return decorated_function