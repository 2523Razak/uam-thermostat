# app.py - Version hébergée directement (le site tourne sur le serveur distant,
# les cartes Arduino restent branchées en local et sont gérées par
# agent_local/agent_arduino.py, relié ici via Socket.IO)
#
# IMPORTANT : eventlet.monkey_patch() DOIT être appelé avant tout autre import
# (avant même Flask), sinon Flask-SocketIO + eventlet peuvent se comporter de
# façon incohérente (blocages, threads non coopératifs).
import eventlet
eventlet.monkey_patch()

from flask import Flask, render_template, jsonify, request, redirect, url_for, flash, session, send_from_directory, send_file
from flask_socketio import SocketIO
from flask_migrate import Migrate
import sys
import os
import time
import json
import csv
import atexit
import secrets
import string
import random
import socket
import webbrowser
import subprocess
import threading
from datetime import datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
from werkzeug.utils import secure_filename
from werkzeug.middleware.proxy_fix import ProxyFix
from io import StringIO, BytesIO
from functools import wraps

# Configuration des chemins
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Import des modules
from db import db, Utilisateur, TP, Question, ReponseEtudiant, EtudiantTP, Notification
from controllers.code_personnalise import custom_code_manager
from utils.email_utils import envoyer_email, envoyer_email_bienvenue, envoyer_email_verification, envoyer_email_creation_admin
from controllers.historique_manager import HistoriqueManager
from utils.audit_logger import audit_logger
from controllers.connection_cleaner import ConnectionCleaner
from utils.decorators import login_required, admin_required, connection_ownership_required

# ============================================================================
# CONFIGURATION
# ============================================================================

app = Flask(__name__)

app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_port=1)

# ============================================================================
# HÉBERGEMENT DIRECT (le site tourne sur ce serveur, plus de tunnel HTTP)
# ============================================================================
#
# L'URL publique du site (utilisée par utils/email_utils.py pour construire
# les liens de vérification/emails). À définir dans les variables
# d'environnement du service Render/Railway, ex: https://uam-thermostat.onrender.com
PUBLIC_BASE_URL = os.environ.get('PUBLIC_BASE_URL', 'http://localhost:5000')
app.config['PUBLIC_TUNNEL_URL'] = PUBLIC_BASE_URL

# Jeton partagé que l'agent local (agent_local/agent_arduino.py) doit
# présenter pour pouvoir se connecter et piloter les cartes Arduino.
# À définir aussi dans les variables d'environnement en production.
AGENT_SHARED_SECRET = os.environ.get('AGENT_SHARED_SECRET', 'change-moi-en-production')
app.config['AGENT_SHARED_SECRET'] = AGENT_SHARED_SECRET

print(f"""
╔══════════════════════════════════════════════════════════════╗
║  🌐 MODE HÉBERGEMENT DIRECT                                  ║
╠══════════════════════════════════════════════════════════════╣
║  URL publique   : {PUBLIC_BASE_URL}
║  Canal agents   : wss://<ce-serveur>/socket.io (namespace /agent)
╚══════════════════════════════════════════════════════════════╝
""")

# Instance Socket.IO partagée par toute l'application (agents locaux +
# éventuelles futures notifications temps réel côté navigateur).
# async_mode="eventlet" est requis pour tenir des connexions WebSocket
# persistantes sous gunicorn sur Render/Railway.
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="gevent")

# Configuration Flask db
app.config['SECRET_KEY'] = 'votre_cle_secrete_tres_longue_ici'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///UAM_database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Configuration email
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'razakboureimaissaadamou@gmail.com'
app.config['MAIL_PASSWORD'] = 'hgwd ukac dshd kitu'
app.config['MAIL_DEFAULT_SENDER'] = 'Thermostat_UAM <razakboureimaissaadamou@gmail.com>'

# Configuration upload
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'bmp', 'pdf'}

# Créer le dossier uploads s'il n'existe pas
if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'tp_responses'), exist_ok=True)

# Initialisation
db.init_app(app)
migrate = Migrate(app, db)

# ----------------------------------------------------------------------------
# Réglages SQLite pour mieux supporter les accès concurrents.
# - WAL (Write-Ahead Logging) : les lectures ne bloquent plus les écritures
#   et inversement (au lieu du mode par défaut où une écriture bloque tout).
# - busy_timeout : si la base est momentanément verrouillée par une autre
#   requête, on attend jusqu'à 10s au lieu de renvoyer immédiatement une
#   erreur "database is locked".
# Utile si plusieurs étudiants soumettent/consultent des TP en même temps.
# ----------------------------------------------------------------------------
from sqlalchemy import event
from sqlalchemy.engine import Engine

@event.listens_for(Engine, "connect")
def _regler_sqlite_pour_concurrence(dbapi_connection, connection_record):
    if app.config['SQLALCHEMY_DATABASE_URI'].startswith('sqlite'):
        curseur = dbapi_connection.cursor()
        curseur.execute("PRAGMA journal_mode=WAL")
        curseur.execute("PRAGMA synchronous=NORMAL")
        curseur.execute("PRAGMA busy_timeout=10000")
        curseur.close()

# ============================================================================
# INITIALISATION DU CONTRÔLEUR ARDUINO
# ============================================================================

from controllers.arduino_controller import ArduinoController
arduino_controller = ArduinoController(app, socketio)
app.config['arduino_controller'] = arduino_controller

# Hub Socket.IO : c'est le point d'entrée par lequel l'agent local
# (agent_local/agent_arduino.py, sur la machine où sont branchées les
# cartes Arduino) se connecte au serveur hébergé.
from sockets.agent_hub import register_agent_namespace
register_agent_namespace(socketio, arduino_controller, AGENT_SHARED_SECRET)

# ============================================================================
# IMPORT DES ROUTES API
# ============================================================================
from api.custom_code import register_custom_code_routes
from api.arduino import register_arduino_routes
from api.user import register_user_routes
from api.tp import register_tp_routes
from api.notifications import register_notification_routes
from api.questions import register_question_routes
from api.soumissions import register_soumission_routes
from api.admin_logs import register_admin_logs_routes

# Enregistrer les routes API
register_custom_code_routes(app, arduino_controller)
register_arduino_routes(app, arduino_controller)
register_user_routes(app)
register_tp_routes(app)
register_notification_routes(app)
register_question_routes(app)
register_soumission_routes(app)
register_admin_logs_routes(app, arduino_controller)

# Nettoie au démarrage historiques
HistoriqueManager.nettoyer_automatique(app)

# ============================================================================
# FONCTIONS UTILITAIRES
# ============================================================================

def generate_token(length=32):
    """Générer un token aléatoire pour la vérification email"""
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))

def generate_verification_token(utilisateur, expiration_hours=24):
    """Génère un token de vérification avec date d'expiration"""
    token = generate_token()
    utilisateur.token_verification = token
    utilisateur.token_expiration = datetime.now() + timedelta(hours=expiration_hours)
    db.session.commit()
    return token

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def save_uploaded_file(file, tp_id, etudiant_id, question_id):
    """Sauvegarder un fichier uploadé avec nom de fichier unique"""
    if file and allowed_file(file.filename):
        upload_dir = os.path.join(app.config['UPLOAD_FOLDER'], 'tp_responses')
        if not os.path.exists(upload_dir):
            os.makedirs(upload_dir, exist_ok=True)
        
        timestamp = int(time.time())
        original_filename = secure_filename(file.filename)
        file_extension = os.path.splitext(original_filename)[1].lower()
        
        filename = f"tp_{tp_id}_etudiant_{etudiant_id}_q{question_id}_{timestamp}{file_extension}"
        filepath = os.path.join(upload_dir, filename)
        
        file.save(filepath)
        
        print(f"✅ Fichier sauvegardé: {filename}")
        print(f"📁 Chemin: {filepath}")
        print(f"📁 Taille: {os.path.getsize(filepath)} bytes")
        
        return os.path.join('tp_responses', filename)
    
    return None

# ============================================================================
# DICTIONNAIRE POUR LES TOKENS DE RÉINITIALISATION
# ============================================================================

reset_tokens = {}

# ============================================================================
# CONFIGURATION DU SCHEDULER
# ============================================================================

from controllers.notification_manager import (
    envoyer_rappels_tp_automatique,
    verifier_badges_nouveaux
)

def setup_nettoyage_automatique():
    scheduler = BackgroundScheduler()
    
    scheduler.add_job(
        func=lambda: HistoriqueManager.nettoyer_automatique(app),
        trigger='cron',
        hour=3,
        minute=0,
        id='nettoyage_historique',
        name='Nettoyage fichiers historique'
    )
    
    scheduler.add_job(
        func=lambda: envoyer_rappels_tp_automatique(app),
        trigger='cron',
        hour=8,
        minute=0,
        id='rappels_tp',
        name='Envoi des rappels de TP'
    )
    
    scheduler.add_job(
        func=lambda: verifier_badges_nouveaux(),
        trigger='cron',
        hour=4,
        minute=0,
        id='verification_badges',
        name='Vérification badges Nouveau'
    )
    
    scheduler.start()
    atexit.register(lambda: scheduler.shutdown())

setup_nettoyage_automatique()

# ============================================================================
# ROUTES PAGES PRINCIPALES (HTML)
# ============================================================================

@app.route('/')
@login_required
def index():
    return render_template('index.html', 
                         user_nom=session.get('user_nom'),
                         user_prenom=session.get('user_prenom'),
                         user_statut=session.get('user_statut'))

@app.route('/connections', methods=['GET', 'POST'])
def connections():
    if request.method == 'POST':
        try:
            identifiant = request.form.get('identifiant')
            password = request.form.get('password')
            
            if not all([identifiant, password]):
                flash('Tous les champs sont obligatoires', 'error')
                return redirect(url_for('connections'))
            
            utilisateur = Utilisateur.query.filter(
                (Utilisateur.email == identifiant) | (Utilisateur.matricule == identifiant)
            ).first()
            
            if not utilisateur:
                flash('Identifiant ou mot de passe incorrect', 'error')
                return redirect(url_for('connections'))
            
            if utilisateur.statut == 'bloque':
                flash('Votre compte a été bloqué. Contactez l\'administrateur.', 'error')
                return redirect(url_for('connections'))
            
            if utilisateur.statut != 'admin' and not utilisateur.email_verifie:
                flash('Veuillez vérifier votre email avant de vous connecter. Consultez votre boîte mail.', 'error')
                
                if not utilisateur.token_verification:
                    utilisateur.token_verification = generate_token()
                    db.session.commit()
                    envoyer_email_verification(utilisateur)
                    flash('Un nouveau lien de vérification a été envoyé à votre email.', 'info')
                
                return redirect(url_for('connections'))
            
            if utilisateur.password == password:
                session['user_id'] = utilisateur.id
                session['user_nom'] = utilisateur.nom
                session['user_prenom'] = utilisateur.prenom
                session['user_statut'] = utilisateur.statut
                session['user_email'] = utilisateur.email
                
                flash(f'Connexion réussie ! Bienvenue {utilisateur.prenom} {utilisateur.nom}', 'success')
                
                if utilisateur.statut == 'admin':
                    return redirect(url_for('liste_utilisateurs'))
                else:
                    return redirect(url_for('index'))
            else:
                flash('Identifiant ou mot de passe incorrect', 'error')
                return redirect(url_for('connections'))
            
        except Exception as e:
            flash('Une erreur est survenue lors de la connexion', 'error')
            print(f"Erreur connexion: {e}")
    
    return render_template('connections.html')

@app.route('/inscription', methods=['GET', 'POST'])
def inscription():
    est_admin = 'user_statut' in session and session.get('user_statut') == 'admin'
    
    if request.method == 'POST':
        try:
            nom = request.form.get('nom')
            prenom = request.form.get('prenom')
            date_naissance_str = request.form.get('date_naissance')
            lieu_naissance = request.form.get('lieu_naissance')
            organisation = request.form.get('organisation')
            matricule = request.form.get('matricule')
            email = request.form.get('email')
            password = request.form.get('password')
            
            skip_verification = False
            if est_admin and 'skip_verification' in request.form:
                skip_verification = True
            
            if not all([nom, prenom, date_naissance_str, lieu_naissance, matricule, email, password]):
                flash('Tous les champs sont obligatoires', 'error')
                return render_template('inscription.html', est_admin=est_admin)
            
            try:
                date_naissance = datetime.strptime(date_naissance_str, '%Y-%m-%d').date()
            except ValueError:
                flash('Format de date invalide', 'error')
                return render_template('inscription.html', est_admin=est_admin)
            
            if Utilisateur.query.filter_by(email=email).first():
                flash('Cet email est déjà utilisé', 'error')
                return render_template('inscription.html', est_admin=est_admin)
            
            if Utilisateur.query.filter_by(matricule=matricule).first():
                flash('Ce matricule est déjà utilisé', 'error')
                return render_template('inscription.html', est_admin=est_admin)
            
            if est_admin and skip_verification:
                statut = 'user'
                email_verifie = True
                token_verification = None
                token_expiration = None
            else:
                statut = 'pending'
                email_verifie = False
                token_verification = generate_token()
                token_expiration = datetime.now() + timedelta(hours=24)
            
            nouvel_utilisateur = Utilisateur(
                nom=nom,
                prenom=prenom,
                date_naissance=date_naissance,
                lieu_naissance=lieu_naissance,
                organisation=organisation,
                matricule=matricule,
                email=email,
                password=password,
                statut=statut,
                email_verifie=email_verifie,
                token_verification=token_verification,
                date_inscription=datetime.now()
            )
            
            if token_expiration:
                nouvel_utilisateur.token_expiration = token_expiration
            
            db.session.add(nouvel_utilisateur)
            db.session.flush()
            
            if est_admin and skip_verification:
                createur_admin = db.session.get(Utilisateur, session.get('user_id'))
                envoyer_email_creation_admin(nouvel_utilisateur, createur_admin)
                flash(f'Compte créé avec succès pour {prenom} {nom}! Le compte est activé immédiatement.', 'success')
                db.session.commit()
                return redirect(url_for('liste_utilisateurs'))
            else:
                envoyer_email_verification(nouvel_utilisateur)
                flash('Inscription réussie ! Un email de vérification a été envoyé. Vérifiez votre boîte mail avant de vous connecter.', 'success')
                db.session.commit()
                return redirect(url_for('connections'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Une erreur est survenue lors de l\'inscription: {str(e)}', 'error')
            print(f"Erreur inscription: {e}")
            return render_template('inscription.html', est_admin=est_admin)
    
    return render_template('inscription.html', est_admin=est_admin)

@app.route('/verifier_email/<token>')
def verifier_email(token):
    try:
        print(f"\n🔍 VÉRIFICATION DU TOKEN: {token[:30]}...")
        
        utilisateur = Utilisateur.query.filter_by(token_verification=token).first()
        
        if not utilisateur:
            print(f"❌ Token invalide: aucun utilisateur trouvé")
            flash('Lien de vérification invalide', 'error')
            return redirect(url_for('connections'))
        
        print(f"✅ Utilisateur trouvé: {utilisateur.email}")
        print(f"📅 Expiration token: {utilisateur.token_expiration}")
        print(f"📅 Date actuelle: {datetime.now()}")
        
        if utilisateur.email_verifie:
            print(f"ℹ️ Email déjà vérifié pour {utilisateur.email}")
            flash('Votre email est déjà vérifié. Vous pouvez vous connecter.', 'info')
            return redirect(url_for('connections'))
        
        if utilisateur.token_expiration and datetime.now() > utilisateur.token_expiration:
            print(f"❌ Token expiré pour {utilisateur.email}")
            flash('Le lien de vérification a expiré. Utilisez le bouton "Renvoyer le lien" pour en recevoir un nouveau.', 'warning')
            return redirect(url_for('connections'))
        
        if not utilisateur.token_expiration and utilisateur.date_inscription:
            delai_expiration = datetime.now() - utilisateur.date_inscription
            if delai_expiration.total_seconds() > 24 * 3600:
                print(f"❌ Délai d'expiration dépassé pour {utilisateur.email}")
                flash('Le lien de vérification a expiré. Utilisez le bouton "Renvoyer le lien" pour en recevoir un nouveau.', 'warning')
                return redirect(url_for('connections'))
        
        if utilisateur.statut == 'bloque':
            print(f"❌ Compte bloqué: {utilisateur.email}")
            flash('Votre compte est bloqué. Contactez l\'administrateur.', 'error')
            return redirect(url_for('connections'))
        
        utilisateur.email_verifie = True
        
        if utilisateur.statut == 'pending':
            utilisateur.statut = 'user'
            print(f"📝 Statut changé: pending → user")
        
        utilisateur.date_verification = datetime.now()
        utilisateur.token_verification = None
        utilisateur.token_expiration = None
        
        db.session.commit()
        
        print(f"✅ Compte activé avec succès pour {utilisateur.email}!")
        
        try:
            envoyer_email_bienvenue(utilisateur)
            print(f"📧 Email de bienvenue envoyé à {utilisateur.email}")
        except Exception as email_error:
            print(f"⚠️ Erreur envoi email bienvenue: {email_error}")
        
        print(f"➡️ Redirection vers la page de succès")
        return redirect(url_for('verification_reussie'))
        
    except Exception as e:
        db.session.rollback()
        print(f"❌ Erreur lors de la vérification: {e}")
        import traceback
        traceback.print_exc()
        flash('Une erreur est survenue lors de la vérification de votre email', 'error')
        return redirect(url_for('connections'))

@app.route('/deconnexion')
def deconnexion():
    session.clear()
    flash('Vous avez été déconnecté avec succès', 'success')
    return redirect(url_for('connections'))

@app.route('/Admin')
@login_required
@admin_required
def liste_utilisateurs():
    utilisateurs = Utilisateur.query.order_by(Utilisateur.date_inscription.desc()).all()
    date_actuelle = datetime.now().strftime('%d/%m/%Y')
    
    organisations_disponibles = sorted(list(set(
        [u.organisation for u in utilisateurs if u.organisation]
    )))
    
    return render_template('Admin.html', 
                         utilisateurs=utilisateurs, 
                         date_actuelle=date_actuelle,
                         organisations_disponibles=organisations_disponibles,
                         user_nom=session.get('user_nom'),
                         user_prenom=session.get('user_prenom'))

@app.route('/documentation')
@login_required
def documentation():
    return render_template('documentation.html', active_page='documentation',
                         user_nom=session.get('user_nom'),
                         user_prenom=session.get('user_prenom'))

@app.route('/bibliotheque')
@login_required
def bibliotheque():
    return render_template('bibliotheque.html', active_page='bibliotheque',
                         user_nom=session.get('user_nom'),
                         user_prenom=session.get('user_nom'))

@app.route('/code_personnalise')
@login_required
def code_personnalise():
    return render_template('code_personnalise.html',
                         user_nom=session.get('user_nom'),
                         user_prenom=session.get('user_prenom'))

@app.route('/profil')
@login_required
def profil():
    user_id = session.get('user_id')
    utilisateur = db.session.get(Utilisateur, user_id)
    
    return render_template('profil.html', 
                         active_page='profil',
                         user_nom=session.get('user_nom'),
                         user_prenom=session.get('user_prenom'),
                         user_email=session.get('user_email'),
                         user_statut=session.get('user_statut'),
                         utilisateur=utilisateur)

@app.route('/admin/security_logs')
@login_required
@admin_required
def admin_security_logs():
    limit = int(request.args.get('limit', 100))
    security_logs = audit_logger.get_security_logs(limit)
    
    return render_template('security_logs.html',
                         security_logs=security_logs,
                         user_nom=session.get('user_nom'),
                         user_prenom=session.get('user_prenom'))

# ============================================================================
# ROUTES POUR RÉINITIALISATION DE MOT DE PASSE
# ============================================================================

@app.route('/mot_de_passe_oublie')
def mot_de_passe_oublie():
    return render_template('password_reset.html')

@app.route('/demande_reset_password', methods=['POST'])
def demande_reset_password():
    try:
        identifiant = request.form.get('email')
        
        if not identifiant:
            flash('Veuillez entrer votre email ou matricule', 'error')
            return redirect(url_for('mot_de_passe_oublie'))
        
        utilisateur = Utilisateur.query.filter(
            (Utilisateur.email == identifiant) | (Utilisateur.matricule == identifiant)
        ).first()
        
        if not utilisateur:
            flash('Si votre email/matricule existe, un code de réinitialisation vous sera envoyé.', 'info')
            return redirect(url_for('mot_de_passe_oublie') + '?step=code&email=' + identifiant)
        
        if utilisateur.statut == 'bloque':
            flash('Ce compte est bloqué. Contactez l\'administrateur.', 'error')
            return redirect(url_for('mot_de_passe_oublie'))
        
        code = ''.join([str(random.randint(0, 9)) for _ in range(6)])
        token = secrets.token_urlsafe(32)
        
        reset_tokens[token] = {
            'user_id': utilisateur.id,
            'email': utilisateur.email,
            'code': code,
            'expires': datetime.now() + timedelta(minutes=15),
            'attempts': 0
        }
        
        try:
            sujet = "Code de réinitialisation - Plateforme Thermostat UAM"
            contenu_html = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <style>
                    body {{ font-family: Arial, sans-serif; }}
                    .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                    .code {{ 
                        font-size: 24px; 
                        font-weight: bold; 
                        color: #1ea95e; 
                        background-color: #f0f9f4;
                        padding: 10px 20px;
                        border-radius: 5px;
                        display: inline-block;
                        margin: 20px 0;
                    }}
                    .warning {{ color: #ff6b35; font-weight: bold; }}
                </style>
            </head>
            <body>
                <div class="container">
                    <h2>Réinitialisation de votre mot de passe</h2>
                    <p>Bonjour {utilisateur.prenom} {utilisateur.nom},</p>
                    <p>Vous avez demandé la réinitialisation de votre mot de passe.</p>
                    <p>Votre code de vérification est :</p>
                    <div class="code">{code}</div>
                    <p class="warning">Ce code est valable pendant 15 minutes.</p>
                    <p>Si vous n'avez pas fait cette demande, ignorez simplement cet email.</p>
                    <p>Cordialement,<br>L'équipe Thermostat UAM/FAST</p>
                </div>
            </body>
            </html>
            """
            
            contenu_texte = f"""
            Réinitialisation de mot de passe
            
            Bonjour {utilisateur.prenom} {utilisateur.nom},
            
            Votre code de vérification est : {code}
            
            Ce code est valable pendant 15 minutes.
            
            Cordialement,
            L'équipe Thermostat UAM/FAST
            """
            
            envoyer_email(utilisateur.email, sujet, contenu_html, contenu_texte)
            
            print(f"✅ Code envoyé à {utilisateur.email}: {code}")
            print(f"🔐 Token: {token}")
            
            flash('Un code de vérification a été envoyé à votre adresse email.', 'success')
            
        except Exception as e:
            print(f"❌ Erreur envoi email: {e}")
            flash(f'Code de réinitialisation (développement): {code}', 'warning')
        
        return redirect(url_for('mot_de_passe_oublie') + f'?step=code&email={utilisateur.email}&token={token}')
        
    except Exception as e:
        flash('Une erreur est survenue. Veuillez réessayer.', 'error')
        print(f"Erreur demande reset: {e}")
        return redirect(url_for('mot_de_passe_oublie'))

@app.route('/verifier_code_reset', methods=['POST'])
def verifier_code_reset():
    try:
        email = request.form.get('email')
        code_saisi = request.form.get('verification_code')
        token = request.args.get('token')
        
        if not all([email, code_saisi]):
            flash('Veuillez entrer le code de vérification', 'error')
            return redirect(url_for('mot_de_passe_oublie') + f'?step=code&email={email}')
        
        token_data = None
        token_to_use = None
        
        if token:
            token_data = reset_tokens.get(token)
            token_to_use = token
        else:
            for t, data in reset_tokens.items():
                if data['email'] == email:
                    token_data = data
                    token_to_use = t
                    break
        
        if not token_data:
            flash('Code invalide ou expiré', 'error')
            return redirect(url_for('mot_de_passe_oublie') + f'?step=code&email={email}')
        
        if datetime.now() > token_data['expires']:
            del reset_tokens[token_to_use]
            flash('Le code a expiré. Veuillez en demander un nouveau.', 'error')
            return redirect(url_for('mot_de_passe_oublie'))
        
        if token_data['attempts'] >= 3:
            del reset_tokens[token_to_use]
            flash('Trop de tentatives échouées. Veuillez redemander un code.', 'error')
            return redirect(url_for('mot_de_passe_oublie'))
        
        if code_saisi != token_data['code']:
            token_data['attempts'] += 1
            flash('Code incorrect. Il vous reste ' + str(3 - token_data['attempts']) + ' tentatives.', 'error')
            return redirect(url_for('mot_de_passe_oublie') + f'?step=code&email={email}&token={token_to_use}')
        
        flash('Code vérifié avec succès! Créez maintenant votre nouveau mot de passe.', 'success')
        return redirect(url_for('mot_de_passe_oublie') + f'?step=password&email={email}&token={token_to_use}')
        
    except Exception as e:
        flash('Une erreur est survenue. Veuillez réessayer.', 'error')
        print(f"Erreur vérification code: {e}")
        return redirect(url_for('mot_de_passe_oublie'))

@app.route('/reinitialiser_password', methods=['POST'])
def reinitialiser_password():
    try:
        email = request.form.get('email')
        token = request.form.get('token')
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')
        
        if not all([email, token, new_password, confirm_password]):
            flash('Tous les champs sont requis', 'error')
            return redirect(url_for('mot_de_passe_oublie') + f'?step=password&email={email}&token={token}')
        
        if new_password != confirm_password:
            flash('Les mots de passe ne correspondent pas', 'error')
            return redirect(url_for('mot_de_passe_oublie') + f'?step=password&email={email}&token={token}')
        
        if len(new_password) < 8:
            flash('Le mot de passe doit contenir au moins 8 caractères', 'error')
            return redirect(url_for('mot_de_passe_oublie') + f'?step=password&email={email}&token={token}')
        
        token_data = reset_tokens.get(token)
        
        if not token_data:
            flash('Session expirée. Veuillez redemander une réinitialisation.', 'error')
            return redirect(url_for('mot_de_passe_oublie'))
        
        if datetime.now() > token_data['expires']:
            del reset_tokens[token]
            flash('La session a expiré. Veuillez redemander une réinitialisation.', 'error')
            return redirect(url_for('mot_de_passe_oublie'))
        
        if token_data['email'] != email:
            flash('Erreur de vérification', 'error')
            return redirect(url_for('mot_de_passe_oublie'))
        
        utilisateur = Utilisateur.query.get(token_data['user_id'])
        
        if not utilisateur:
            flash('Utilisateur non trouvé', 'error')
            return redirect(url_for('mot_de_passe_oublie'))
        
        utilisateur.password = new_password
        db.session.commit()
        
        del reset_tokens[token]
        
        try:
            sujet = "Confirmation de réinitialisation - Plateforme Thermostat UAM"
            contenu_html = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <style>
                    body {{ font-family: Arial, sans-serif; }}
                    .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                    .success {{ color: #1ea95e; font-weight: bold; }}
                </style>
            </head>
            <body>
                <div class="container">
                    <h2>Mot de passe réinitialisé avec succès</h2>
                    <p>Bonjour {utilisateur.prenom} {utilisateur.nom},</p>
                    <p class="success">Votre mot de passe a été réinitialisé avec succès.</p>
                    <p>Date de la modification : {datetime.now().strftime('%d/%m/%Y %H:%M')}</p>
                    <p>Si vous n'avez pas effectué cette action, veuillez contacter immédiatement l'administrateur.</p>
                    <p>Cordialement,<br>L'équipe Thermostat UAM/FAST</p>
                </div>
            </body>
            </html>
            """
            
            contenu_texte = f"""
            Confirmation de réinitialisation
            
            Bonjour {utilisateur.prenom} {utilisateur.nom},
            
            Votre mot de passe a été réinitialisé avec succès.
            
            Date : {datetime.now().strftime('%d/%m/%Y %H:%M')}
            
            Si vous n'êtes pas à l'origine de cette action, contactez l'administrateur.
            
            Cordialement,
            L'équipe Thermostat UAM/FAST
            """
            
            envoyer_email(utilisateur.email, sujet, contenu_html, contenu_texte)
            
            print(f"✅ Email de confirmation envoyé à {utilisateur.email}")
            print(f"✅ Mot de passe réinitialisé pour {utilisateur.email}")
            
        except Exception as e:
            print(f"⚠️ Erreur envoi email confirmation: {e}")
        
        return redirect(url_for('mot_de_passe_oublie') + '?step=success')
        
    except Exception as e:
        db.session.rollback()
        flash('Une erreur est survenue lors de la réinitialisation', 'error')
        print(f"Erreur réinitialisation: {e}")
        return redirect(url_for('mot_de_passe_oublie') + f'?step=password&email={email}&token={token}')

@app.route('/renvoyer_code_reset', methods=['POST'])
def renvoyer_code_reset():
    try:
        identifiant = request.form.get('email')
        
        if not identifiant:
            return jsonify({'success': False, 'message': 'Email requis'})
        
        now = datetime.now()
        expired_tokens = [t for t, data in reset_tokens.items() if data['expires'] < now]
        for t in expired_tokens:
            del reset_tokens[t]
        
        utilisateur = Utilisateur.query.filter(
            (Utilisateur.email == identifiant) | (Utilisateur.matricule == identifiant)
        ).first()
        
        if not utilisateur:
            return jsonify({'success': True, 'message': 'Si votre compte existe, un code vous sera envoyé'})
        
        code = ''.join([str(random.randint(0, 9)) for _ in range(6)])
        token = secrets.token_urlsafe(32)
        
        reset_tokens[token] = {
            'user_id': utilisateur.id,
            'email': utilisateur.email,
            'code': code,
            'expires': datetime.now() + timedelta(minutes=15),
            'attempts': 0
        }
        
        print(f"🔄 Nouveau code pour {utilisateur.email}: {code}")
        print(f"🔄 Nouveau token: {token}")
        
        return jsonify({
            'success': True, 
            'message': 'Nouveau code envoyé',
            'token': token
        })
        
    except Exception as e:
        print(f"Erreur renvoi code: {e}")
        return jsonify({'success': False, 'message': str(e)})

# ============================================================================
# ROUTES POUR RÉPONDRE AUX TP
# ============================================================================

@app.route('/tp/<int:tp_id>/repondre')
@login_required
def repondre_tp(tp_id):
    tp = db.session.get(TP, tp_id)
    etudiant = db.session.get(Utilisateur, session.get('user_id'))
    
    inscription = EtudiantTP.query.filter_by(
        tp_id=tp_id, 
        etudiant_id=etudiant.id
    ).first()
    
    if not inscription:
        flash('Vous n\'êtes pas inscrit à ce TP', 'error')
        return redirect(url_for('liste_tps_etudiant'))
    
    if tp.date_limite and datetime.now() > tp.date_limite:
        flash('La date limite pour ce TP est dépassée', 'error')
        return redirect(url_for('liste_tps_etudiant'))
    
    professeur = db.session.get(Utilisateur, tp.created_by) if tp.created_by else etudiant
    
    return render_template('repondre_questions.html', 
                         tp=tp,
                         etudiant=etudiant,
                         professeur=professeur)

@app.route('/tp/<int:tp_id>/continuer')
@login_required
def continuer_tp(tp_id):
    tp = db.session.get(TP, tp_id)
    etudiant = db.session.get(Utilisateur, session.get('user_id'))
    
    inscription = EtudiantTP.query.filter_by(
        tp_id=tp_id, 
        etudiant_id=etudiant.id
    ).first()
    
    if not inscription:
        flash('Vous n\'êtes pas inscrit à ce TP', 'error')
        return redirect(url_for('liste_tps_etudiant'))
    
    reponses_existantes = ReponseEtudiant.query.filter_by(
        tp_id=tp_id,
        etudiant_id=etudiant.id
    ).first()
    
    if not reponses_existantes:
        return redirect(url_for('repondre_tp', tp_id=tp_id))
    
    professeur = db.session.get(Utilisateur, tp.created_by) if tp.created_by else etudiant
    
    return render_template('repondre_questions.html', 
                         tp=tp,
                         etudiant=etudiant,
                         professeur=professeur)

@app.route('/tp/<int:tp_id>/commencer')
@login_required
def commencer_tp(tp_id):
    return redirect(url_for('repondre_tp', tp_id=tp_id))

@app.route('/tp/<int:tp_id>/correction')
@login_required
def voir_correction(tp_id):
    try:
        tp = db.session.get(TP, tp_id)
        if not tp:
            flash('TP non trouvé', 'error')
            return redirect(url_for('liste_tps_etudiant'))
            
        etudiant = db.session.get(Utilisateur, session.get('user_id'))
        
        inscription = EtudiantTP.query.filter_by(
            tp_id=tp_id,
            etudiant_id=etudiant.id
        ).first()
        
        if not inscription:
            flash('Vous n\'êtes pas inscrit à ce TP', 'error')
            return redirect(url_for('liste_tps_etudiant'))
        
        questions = Question.query.filter_by(tp_id=tp_id).order_by(Question.ordre).all()
        
        reponses_etudiant = ReponseEtudiant.query.filter_by(
            tp_id=tp_id,
            etudiant_id=etudiant.id
        ).all()
        
        if not reponses_etudiant:
            flash('Vous n\'avez pas encore soumis ce TP', 'error')
            return redirect(url_for('liste_tps_etudiant'))
        
        reponses_dict = {r.question_id: r for r in reponses_etudiant}
        
        professeur = db.session.get(Utilisateur, tp.created_by) if tp.created_by else None
        
        total_points = sum(q.points for q in questions) if questions else 0
        total_notes = sum(r.note for r in reponses_etudiant if r.note is not None)
        pourcentage = (total_notes / total_points * 100) if total_points > 0 else 0
        today_date = datetime.now().strftime('%d/%m/%Y')
        
        return render_template('correction_tp.html',
                             tp=tp,
                             etudiant=etudiant,
                             professeur=professeur,
                             questions=questions,
                             reponses=reponses_etudiant,
                             reponses_dict=reponses_dict,
                             total_points=total_points,
                             total_notes=total_notes,
                             pourcentage=pourcentage,
                             today_date=today_date)
                             
    except Exception as e:
        print(f"Erreur dans voir_correction: {e}")
        flash('Une erreur est survenue', 'error')
        return redirect(url_for('liste_tps_etudiant'))

@app.route('/tp/<int:tp_id>/details')
@login_required
def details_tp(tp_id):
    tp = db.session.get(TP, tp_id)
    etudiant = db.session.get(Utilisateur, session.get('user_id'))
    
    inscription = EtudiantTP.query.filter_by(
        tp_id=tp_id,
        etudiant_id=etudiant.id
    ).first()
    
    if not inscription:
        flash('Vous n\'êtes pas inscrit à ce TP', 'error')
        return redirect(url_for('liste_tps_etudiant'))
    
    professeur = db.session.get(Utilisateur, tp.created_by) if tp.created_by else None
    
    questions_count = Question.query.filter_by(tp_id=tp_id).count()
    
    reponses_etudiant = ReponseEtudiant.query.filter_by(
        tp_id=tp_id,
        etudiant_id=etudiant.id
    ).all()
    
    reponses_count = len(reponses_etudiant)
    reponses_dict = {r.question_id: r for r in reponses_etudiant}
    
    progress = (reponses_count / questions_count * 100) if questions_count > 0 else 0
    
    statut = 'disponible'
    if reponses_count > 0:
        statut = 'en_cours'
    if reponses_count == questions_count and questions_count > 0:
        statut = 'soumis'
    if tp.date_limite and datetime.now() > tp.date_limite:
        statut = 'expire'
    
    jours_restants = 0
    if tp.date_limite:
        delta = tp.date_limite - datetime.now()
        jours_restants = delta.days if delta.days > 0 else 0
    
    is_new = False
    if tp.date_creation:
        delta_nouveau = datetime.now() - tp.date_creation
        is_new = delta_nouveau.days < 1
    
    questions = Question.query.filter_by(tp_id=tp_id).order_by(Question.ordre).all()
    
    date_soumission = None
    if reponses_count == questions_count and questions_count > 0:
        derniere_reponse = ReponseEtudiant.query.filter_by(
            tp_id=tp_id,
            etudiant_id=etudiant.id
        ).order_by(ReponseEtudiant.date_soumission.desc()).first()
        if derniere_reponse:
            date_soumission = derniere_reponse.date_soumission
    
    return render_template('details_tp.html',
                         tp=tp,
                         etudiant=etudiant,
                         professeur=professeur,
                         questions=questions,
                         questions_count=questions_count,
                         reponses_count=reponses_count,
                         reponses_dict=reponses_dict,
                         progress=progress,
                         statut=statut,
                         jours_restants=jours_restants,
                         is_new=is_new,
                         date_soumission=date_soumission)

# ============================================================================
# ROUTES POUR LA LISTE DES TP (ÉTUDIANTS)
# ============================================================================

@app.route('/liste_tps')
@login_required
def liste_tps_etudiant():
    utilisateur = db.session.get(Utilisateur, session.get('user_id'))
    
    inscriptions = EtudiantTP.query.filter_by(etudiant_id=utilisateur.id).all()
    
    tps = []
    for inscription in inscriptions:
        tp = db.session.get(TP, inscription.tp_id)
        if tp and tp.actif:
            reponses = ReponseEtudiant.query.filter_by(
                tp_id=tp.id,
                etudiant_id=utilisateur.id
            ).all()
            
            reponses_count = len(reponses)
            questions_count = tp.nombre_questions
            a_soumis = (reponses_count == questions_count and questions_count > 0)
            
            statut = 'disponible'
            
            if reponses_count > 0 and not a_soumis:
                statut = 'en_cours'
            
            if a_soumis:
                statut = 'soumis'
            
            if tp.date_limite and datetime.now() > tp.date_limite:
                statut = 'expire'
            
            jours_restants = 0
            if tp.date_limite:
                delta = tp.date_limite - datetime.now()
                jours_restants = delta.days if delta.days > 0 else 0
            
            is_new = False
            if tp.date_creation:
                delta_nouveau = datetime.now() - tp.date_creation
                is_new = delta_nouveau.days < 3
            
            date_soumission = None
            if a_soumis:
                derniere_reponse = ReponseEtudiant.query.filter_by(
                    tp_id=tp.id,
                    etudiant_id=utilisateur.id
                ).order_by(ReponseEtudiant.date_soumission.desc()).first()
                if derniere_reponse:
                    date_soumission = derniere_reponse.date_soumission
            
            professeur_nom = 'Professeur'
            if tp.created_by:
                professeur = db.session.get(Utilisateur, tp.created_by)
                if professeur:
                    professeur_nom = f"{professeur.prenom} {professeur.nom}"
            
            tps.append({
                'id': tp.id,
                'titre': tp.titre,
                'description': tp.description,
                'module': tp.module,
                'date_creation': tp.date_creation,
                'date_limite': tp.date_limite,
                'statut': statut,
                'nombre_questions': questions_count,
                'professeur_nom': professeur_nom,
                'jours_restants': jours_restants,
                'is_new': is_new,
                'date_soumission': date_soumission
            })
    
    tps_total = len(tps)
    tps_en_cours = len([tp for tp in tps if tp['statut'] == 'en_cours'])
    tps_soumis = len([tp for tp in tps if tp['statut'] == 'soumis'])
    tps_expires = len([tp for tp in tps if tp['statut'] == 'expire'])
    
    modules = sorted(list(set([tp['module'] for tp in tps if tp['module']])))
    
    return render_template('liste_tps_etudiant.html',
                         tps=tps,
                         tps_total=tps_total,
                         tps_en_cours=tps_en_cours,
                         tps_soumis=tps_soumis,
                         tps_expires=tps_expires,
                         modules=modules,
                         utilisateur=utilisateur,
                         user_prenom=session.get('user_prenom'),
                         user_nom=session.get('user_nom'))

# ============================================================================
# ROUTES API
# ============================================================================

@app.route('/api/notes_etudiant')
@login_required
def api_notes_etudiant():
    try:
        etudiant_id = session.get('user_id')
        
        inscriptions = EtudiantTP.query.filter_by(etudiant_id=etudiant_id).all()
        
        notes_list = []
        
        for inscription in inscriptions:
            tp = db.session.get(TP, inscription.tp_id)
            if not tp:
                continue
            
            reponses = ReponseEtudiant.query.filter_by(
                tp_id=tp.id,
                etudiant_id=etudiant_id
            ).all()
            
            if not reponses:
                continue
            
            note_totale = 0
            points_totaux = 0
            questions_notees = 0
            
            for reponse in reponses:
                if reponse.note is not None:
                    note_totale += reponse.note
                    questions_notees += 1
                
                question = db.session.get(Question, reponse.question_id)
                if question:
                    points_totaux += question.points
            
            if questions_notees > 0:
                pourcentage = round((note_totale / points_totaux) * 100, 1) if points_totaux > 0 else 0
                
                notes_list.append({
                    'tp_id': tp.id,
                    'tp_titre': tp.titre,
                    'note_obtenue': note_totale,
                    'points_totaux': points_totaux,
                    'pourcentage': pourcentage,
                    'affichage': f"{note_totale}/{pourcentage}%"
                })
        
        return jsonify({
            'success': True,
            'notes': notes_list
        })
        
    except Exception as e:
        print(f"❌ Erreur API notes: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/tps/statuts', methods=['POST'])
@login_required
def api_tps_statuts():
    try:
        data = request.get_json()
        tps_ids = data.get('tps_ids', [])
        etudiant_id = session.get('user_id')
        
        if not tps_ids:
            return jsonify({'success': True, 'tps': []})
        
        tps_data = []
        for tp_id in tps_ids:
            tp = db.session.get(TP, tp_id)
            if not tp:
                continue
            
            reponses = ReponseEtudiant.query.filter_by(
                tp_id=tp_id,
                etudiant_id=etudiant_id
            ).all()
            
            reponses_count = len(reponses)
            questions_count = tp.nombre_questions
            a_soumis = (reponses_count == questions_count and questions_count > 0)
            
            statut = 'disponible'
            
            if reponses_count > 0 and not a_soumis:
                statut = 'en_cours'
            
            if a_soumis:
                statut = 'soumis'
            
            if tp.date_limite and datetime.now() > tp.date_limite:
                statut = 'expire'
            
            date_soumission = None
            if a_soumis:
                derniere_reponse = ReponseEtudiant.query.filter_by(
                    tp_id=tp_id,
                    etudiant_id=etudiant_id
                ).order_by(ReponseEtudiant.date_soumission.desc()).first()
                if derniere_reponse:
                    date_soumission = derniere_reponse.date_soumission.isoformat() if derniere_reponse.date_soumission else None
            
            tps_data.append({
                'id': tp_id,
                'statut': statut,
                'date_soumission': date_soumission,
                'a_soumis': a_soumis,
                'reponses_count': reponses_count,
                'questions_count': questions_count
            })
        
        return jsonify({
            'success': True,
            'tps': tps_data,
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        print(f"❌ Erreur API statuts: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# ============================================================================
# ROUTES POUR LA GESTION DES TP (PROFESSEURS)
# ============================================================================

@app.route('/gestion_tps')
@login_required
def gestion_tps():
    try:
        utilisateur = db.session.get(Utilisateur, session.get('user_id'))
        tps = TP.query.filter_by(created_by=utilisateur.id).all()
        
        total_etudiants = 0
        for tp in tps:
            if hasattr(tp, 'nombre_etudiants'):
                total_etudiants += tp.nombre_etudiants
            else:
                count = EtudiantTP.query.filter_by(tp_id=tp.id).count()
                total_etudiants += count
        
        tps_actifs = len([tp for tp in tps if getattr(tp, 'actif', True)]) if tps else 0
        
        return render_template('gestion_tps.html',
                             tps=tps,
                             utilisateur=utilisateur,
                             total_etudiants=total_etudiants,
                             tps_actifs=tps_actifs,
                             date_actuelle=datetime.now().strftime("%d %B %Y"),
                             user_nom=session.get('user_nom'),
                             user_prenom=session.get('user_prenom'))
                             
    except Exception as e:
        print(f"Erreur dans gestion_tps: {e}")
        return render_template('gestion_tps.html',
                             tps=[],
                             total_etudiants=0,
                             tps_actifs=0,
                             date_actuelle=datetime.now().strftime("%d %B %Y"),
                             user_nom=session.get('user_nom'),
                             user_prenom=session.get('user_prenom'))

@app.route('/creer_tp', methods=['GET', 'POST'])
@login_required
def creer_tp():
    if request.method == 'POST':
        try:
            titre = request.form.get('titre')
            description = request.form.get('description')
            module = request.form.get('module')
            date_limite = request.form.get('date_limite')
            etudiants_json = request.form.get('etudiants', '[]')
            
            if not titre:
                flash('Le titre du TP est obligatoire', 'error')
                return redirect(url_for('creer_tp'))
            
            date_limite_dt = None
            if date_limite:
                try:
                    date_limite_dt = datetime.strptime(date_limite, '%Y-%m-%dT%H:%M')
                except ValueError:
                    flash('Format de date limite invalide', 'error')
                    return redirect(url_for('creer_tp'))
            
            nouveau_tp = TP(
                titre=titre,
                description=description,
                module=module,
                date_limite=date_limite_dt,
                created_by=session.get('user_id'),
                nombre_questions=0,
                nombre_etudiants=0,
                actif=True
            )
            
            db.session.add(nouveau_tp)
            db.session.flush()
            
            etudiants_list = []
            try:
                etudiants_list = json.loads(etudiants_json)
                for identifiant in etudiants_list:
                    etudiant = Utilisateur.query.filter(
                        (Utilisateur.matricule == identifiant) | 
                        (Utilisateur.email == identifiant)
                    ).first()
                    
                    if etudiant:
                        existe = EtudiantTP.query.filter_by(
                            tp_id=nouveau_tp.id,
                            etudiant_id=etudiant.id
                        ).first()
                        
                        if not existe:
                            inscription = EtudiantTP(
                                tp_id=nouveau_tp.id,
                                etudiant_id=etudiant.id
                            )
                            db.session.add(inscription)
                
                nouveau_tp.nombre_etudiants = len(etudiants_list)
            except:
                nouveau_tp.nombre_etudiants = 0
            
            db.session.commit()
            
            from controllers.notification_manager import envoyer_notifications_tp_creer
            professeur = db.session.get(Utilisateur, session.get('user_id'))
            nombre_notifications = envoyer_notifications_tp_creer(nouveau_tp, professeur, db)
            
            flash(f'TP "{titre}" créé avec succès ! {nombre_notifications} étudiants ont été notifiés.', 'success')
            return redirect(url_for('gestion_questions', tp_id=nouveau_tp.id))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Erreur lors de la création du TP: {str(e)}', 'error')
            return render_template('creer_tp.html',
                                 user_nom=session.get('user_nom'),
                                 user_prenom=session.get('user_prenom'),
                                 utilisateur=db.session.get(Utilisateur, session.get('user_id')),
                                 titre=request.form.get('titre'),
                                 description=request.form.get('description'),
                                 module=request.form.get('module'),
                                 date_limite=request.form.get('date_limite'))
    
    user_id = session.get('user_id')
    utilisateur = db.session.get(Utilisateur, user_id) if user_id else None
    
    return render_template('creer_tp.html',
                         user_nom=session.get('user_nom'),
                         user_prenom=session.get('user_prenom'),
                         utilisateur=utilisateur,
                         user_organisation=utilisateur.organisation if utilisateur else '',
                         titre='',
                         description='',
                         module='',
                         date_limite='')

@app.route('/tp/<int:tp_id>/gestion')
@login_required
def gestion_questions(tp_id):
    try:
        tp = db.session.get(TP, tp_id)
        if not tp:
            flash('TP non trouvé', 'error')
            return redirect(url_for('gestion_tps'))
        
        if tp.created_by != session.get('user_id'):
            flash('Non autorisé', 'error')
            return redirect(url_for('gestion_tps'))
        
        createur = db.session.get(Utilisateur, tp.created_by)
        
        questions_existantes = Question.query.filter_by(tp_id=tp_id).count()
        tp_a_des_questions = questions_existantes > 0
        
        return render_template('gestion_questions.html',
                             tp=tp,
                             createur=createur,
                             tp_a_des_questions=tp_a_des_questions,
                             user_nom=session.get('user_nom'),
                             user_prenom=session.get('user_prenom'))
                             
    except Exception as e:
        print(f"Erreur dans gestion_questions: {e}")
        flash('Une erreur est survenue', 'error')
        return redirect(url_for('gestion_tps'))

@app.route('/api/tp/<int:tp_id>/date_limite')
@login_required
def get_tp_date_limite(tp_id):
    try:
        tp = db.session.get(TP, tp_id)
        if not tp:
            return jsonify({'success': False, 'message': 'TP non trouvé'}), 404
        
        etudiant_id = session.get('user_id')
        inscription = EtudiantTP.query.filter_by(
            tp_id=tp_id,
            etudiant_id=etudiant_id
        ).first()
        
        if not inscription:
            return jsonify({'success': False, 'message': 'Non inscrit à ce TP'}), 403
        
        return jsonify({
            'success': True,
            'date_limite': tp.date_limite.isoformat() if tp.date_limite else None,
            'titre': tp.titre,
            'module': tp.module
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

# ============================================================================
# ROUTES POUR LE DEBUG ET LA GESTION DES CONNEXIONS ARDUINO
# ============================================================================

@app.route('/api/debug_connexions')
@login_required
def debug_connexions():
    try:
        controller = app.config.get('arduino_controller')
        
        if not controller:
            return jsonify({'error': 'Contrôleur Arduino non disponible'})
        
        connexions_info = []
        for id_connexion, connexion in controller.connexions_arduino.items():
            connexions_info.append({
                'id': id_connexion,
                'connecte': connexion.get('connecte', False),
                'port': connexion.get('port', 'N/A'),
                'agent_id': connexion.get('agent_id', 'N/A'),
                'user_id': connexion.get('user_id'),
                'user_email': connexion.get('user_email', 'N/A'),
                'surveillance_active': connexion.get('surveillance_active', False),
                'type_controleur': connexion.get('type_controleur', 'none'),
                'consigne': connexion.get('consigne', 0),
                'last_activity': connexion.get('last_activity', 0),
                'derniere_donnee_recue': connexion.get('derniere_donnee_recue', 0),
                'derniere_pwm_envoyee': connexion.get('derniere_pwm_envoyee', 0)
            })
        
        return jsonify({
            'success': True,
            'total_connexions': len(connexions_info),
            'connexions': connexions_info,
            'agents': controller.get_agents_status(),
            'controller_in_config': 'arduino_controller' in app.config,
            'controller_class': controller.__class__.__name__
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/fix_port_occupation/<port>')
@login_required
@admin_required
def fix_port_occupation(port):
    try:
        controller = app.config.get('arduino_controller')
        
        if not controller:
            return jsonify({'success': False, 'message': 'Contrôleur Arduino non disponible'})
        
        connexions_a_supprimer = []
        for id_connexion, connexion in controller.connexions_arduino.items():
            if connexion.get('port') == port:
                connexions_a_supprimer.append(id_connexion)
        
        for id_connexion in connexions_a_supprimer:
            if id_connexion in controller.connexions_arduino:
                # Demande à l'agent local de fermer proprement le port série
                controller.demander_fermeture_port(id_connexion)
                controller.connexions_arduino[id_connexion]['connecte'] = False
                del controller.connexions_arduino[id_connexion]
                print(f" Port {id_connexion} supprimée")
        
        audit_logger.log(
            event_type='PORT_FORCE_RELEASE',
            user_id=session.get('user_id'),
            connection_id=None,
            details=f"Port {port} libéré manuellement",
            ip_address=request.remote_addr
        )
        
        return jsonify({
            'success': True,
            'message': f'Port {port} libéré avec succès',
            'connexions_nettoyees': len(connexions_a_supprimer)
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/system_health')
@login_required
def system_health():
    try:
        controller = app.config.get('arduino_controller')
        
        health_info = {
            'timestamp': datetime.now().isoformat(),
            'flask_app': 'running',
            'database': 'connected',
            'controller_available': controller is not None,
            'controller_class': controller.__class__.__name__ if controller else 'None'
        }
        
        if controller:
            health_info.update({
                'active_connections': len(controller.connexions_arduino),
                'data_buffers': {
                    'temps_reel': len(controller.donnees_temps_reel) if hasattr(controller, 'donnees_temps_reel') else 0,
                    'historique': len(controller.historique_detaille) if hasattr(controller, 'historique_detaille') else 0,
                    'controle': len(controller.donnees_controle) if hasattr(controller, 'donnees_controle') else 0
                },
                'ports_utilises_count': len(getattr(controller, 'ports_utilises', [])),
                'ports_utilises': list(getattr(controller, 'ports_utilises', []))
            })
        
        return jsonify({
            'success': True,
            'status': 'healthy',
            'health': health_info
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'status': 'error',
            'error': str(e)
        })

# ============================================================================
# ROUTES POUR LA CONSULTATION DES SOUMISSIONS (ENSEIGNANTS)
# ============================================================================

@app.route('/consulter_soumissions')
@login_required
def consulter_soumissions():
    try:
        utilisateur = db.session.get(Utilisateur, session.get('user_id'))
        
        tps_crees = TP.query.filter_by(created_by=utilisateur.id).order_by(TP.date_creation.desc()).all()
        
        stats = {
            'total_tps': len(tps_crees),
            'total_etudiants': 0,
            'soumissions_completes': 0,
            'soumissions_partielles': 0,
            'moyenne_notes': 0
        }
        
        tps_list = []
        for tp in tps_crees:
            inscriptions = EtudiantTP.query.filter_by(tp_id=tp.id).all()
            stats['total_etudiants'] += len(inscriptions)
            
            for inscription in inscriptions:
                reponses_count = ReponseEtudiant.query.filter_by(
                    tp_id=tp.id,
                    etudiant_id=inscription.etudiant_id
                ).count()
                
                if reponses_count == tp.nombre_questions and tp.nombre_questions > 0:
                    stats['soumissions_completes'] += 1
                elif reponses_count > 0:
                    stats['soumissions_partielles'] += 1
            
            tps_list.append({
                'id': tp.id,
                'titre': tp.titre,
                'module': tp.module
            })
        
        return render_template('consulter_soumissions.html',
                             tps=tps_list,
                             stats=stats,
                             user_nom=session.get('user_nom'),
                             user_prenom=session.get('user_prenom'),
                             utilisateur=utilisateur)
                             
    except Exception as e:
        print(f"Erreur dans consulter_soumissions: {e}")
        flash('Une erreur est survenue lors du chargement des soumissions', 'error')
        return redirect(url_for('gestion_tps'))

# ============================================================================
# ROUTES POUR LES FICHIERS
# ============================================================================

@app.route('/uploads/<path:filename>')
@login_required
def serve_tp_file(filename):
    try:
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        
        if os.path.exists(filepath):
            mime_type = 'application/octet-stream'
            if filename.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp')):
                ext = filename.split('.')[-1].lower()
                if ext == 'jpg':
                    mime_type = 'image/jpeg'
                else:
                    mime_type = f'image/{ext}'
            
            return send_from_directory(
                os.path.dirname(filepath),
                os.path.basename(filepath),
                mimetype=mime_type,
                as_attachment=False
            )
        
        return jsonify({'error': 'Fichier non trouvé'}), 404
        
    except Exception as e:
        print(f"❌ Erreur serve_tp_file: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/uploads/tp_responses/<path:filename>')
@login_required
def serve_tp_response_file(filename):
    try:
        parts = filename.split('/')
        if len(parts) < 2:
            return "Chemin invalide", 400
            
        tp_id = parts[0]
        actual_filename = '/'.join(parts[1:])
        
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], 'tp_responses', tp_id, actual_filename)
        
        if not os.path.exists(filepath):
            return jsonify({'error': 'Fichier non trouvé'}), 404
        
        mime_type = 'application/octet-stream'
        if actual_filename.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp')):
            ext = actual_filename.split('.')[-1].lower()
            if ext == 'jpg':
                mime_type = 'image/jpeg'
            else:
                mime_type = f'image/{ext}'
        
        return send_from_directory(
            os.path.dirname(filepath),
            os.path.basename(filepath),
            mimetype=mime_type,
            as_attachment=False
        )
        
    except Exception as e:
        print(f"❌ Erreur serve_tp_response_file: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/admin/audit_logs')
@login_required
@admin_required
def view_audit_logs():
    user_filter = request.args.get('user_id')
    event_filter = request.args.get('event_type')
    limit = int(request.args.get('limit', 100))
    
    logs = audit_logger.get_user_logs(
        user_id=user_filter,
        limit=limit
    )
    
    if event_filter and event_filter != 'all':
        logs = [log for log in logs if log.get('event_type') == event_filter]
    
    return render_template('audit_logs.html',
                         logs=logs,
                         user_nom=session.get('user_nom'),
                         user_prenom=session.get('user_prenom'))

# ============================================================================
# ROUTES POUR SOUMETTRE LES RÉPONSES TP
# ============================================================================

@app.route('/tp/<int:tp_id>/soumettre', methods=['POST'])
@login_required
def soumettre_reponses(tp_id):
    try:
        data = request.get_json()
        etudiant_id = session.get('user_id')
        
        inscription = EtudiantTP.query.filter_by(
            tp_id=tp_id, 
            etudiant_id=etudiant_id
        ).first()
        
        if not inscription:
            return jsonify({'success': False, 'message': 'Non inscrit à ce TP'}), 403
        
        ReponseEtudiant.query.filter_by(
            tp_id=tp_id,
            etudiant_id=etudiant_id
        ).delete()
        
        for reponse_data in data.get('reponses', []):
            reponse = ReponseEtudiant(
                tp_id=tp_id,
                question_id=reponse_data.get('question_id'),
                etudiant_id=etudiant_id,
                reponse=reponse_data.get('reponse', ''),
                date_soumission=datetime.now()
            )
            
            db.session.add(reponse)
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Travail soumis avec succès',
            'redirect': url_for('liste_tps_etudiant')
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'message': f'Erreur: {str(e)}'
        }), 500

@app.route('/debug/image/<path:filename>')
@login_required
def debug_image(filename):
    full_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    
    info = {
        'filename': filename,
        'full_path': full_path,
        'exists': os.path.exists(full_path),
        'is_file': os.path.isfile(full_path) if os.path.exists(full_path) else False,
        'size': os.path.getsize(full_path) if os.path.exists(full_path) else 0,
        'upload_folder': app.config['UPLOAD_FOLDER'],
        'url_for': url_for('serve_tp_file', filename=filename),
        'direct_url': f"/uploads/{filename}"
    }
    
    if os.path.exists(full_path):
        try:
            info['can_serve'] = True
        except Exception as e:
            info['can_serve'] = False
            info['serve_error'] = str(e)
    
    return jsonify(info)

@app.route('/correction_rapide')
@login_required
def correction_rapide():
    try:
        utilisateur = db.session.get(Utilisateur, session.get('user_id'))
        
        tps = TP.query.filter_by(created_by=utilisateur.id).order_by(TP.date_creation.desc()).all()
        
        return render_template('correction_rapide.html',
                             tps=tps,
                             user_nom=session.get('user_nom'),
                             user_prenom=session.get('user_prenom'),
                             utilisateur=utilisateur)
    except Exception as e:
        print(f"Erreur dans correction_rapide: {e}")
        flash('Une erreur est survenue', 'error')
        return redirect(url_for('consulter_soumissions'))

@app.route('/renvoyer-lien-verification', methods=['POST'])
def renvoyer_lien_verification():
    try:
        data = request.get_json()
        email = data.get('email')
        
        if not email:
            return jsonify({'success': False, 'message': 'Email requis'}), 400
        
        utilisateur = Utilisateur.query.filter_by(email=email).first()
        
        if not utilisateur:
            return jsonify({'success': False, 'message': 'Aucun compte associé à cet email'}), 404
        
        if utilisateur.email_verifie:
            return jsonify({'success': False, 'message': 'Cet email est déjà vérifié'}), 400
        
        nouveau_token = generate_token()
        utilisateur.token_verification = nouveau_token
        utilisateur.token_expiration = datetime.now() + timedelta(hours=24)
        
        db.session.commit()
        
        print(f"✅ Nouveau token généré et sauvegardé: {nouveau_token}")
        print(f"📧 Email: {email}")
        
        envoyer_email_verification(utilisateur)
        
        return jsonify({
            'success': True,
            'message': f'Un nouveau lien de vérification a été envoyé à {email} (valable 24h)'
        })
        
    except Exception as e:
        db.session.rollback()
        print(f"❌ Erreur: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/renvoyer-verification', methods=['POST'])
def renvoyer_verification():
    try:
        email = request.form.get('email')
        
        if not email:
            flash('Email requis', 'error')
            return redirect(url_for('connections'))
        
        utilisateur = Utilisateur.query.filter_by(email=email).first()
        
        if not utilisateur:
            flash('Aucun compte associé à cet email', 'error')
            return redirect(url_for('connections'))
        
        if utilisateur.email_verifie:
            flash('Cet email est déjà vérifié', 'warning')
            return redirect(url_for('connections'))
        
        utilisateur.token_verification = generate_token()
        utilisateur.token_expiration = datetime.now() + timedelta(hours=24)
        db.session.commit()
        
        envoyer_email_verification(utilisateur)
        
        flash(f'Un nouveau lien de vérification a été envoyé à {email} (valable 24h)', 'success')
        
    except Exception as e:
        db.session.rollback()
        print(f"Erreur renvoi vérification: {e}")
        flash('Une erreur est survenue', 'error')
    
    return redirect(url_for('connections'))

@app.route('/verification_reussie')
def verification_reussie():
    return render_template('verification_succes.html')

# ============================================================================
# ANCIENNE ROUTE DE GESTION DU TUNNEL (obsolète depuis l'hébergement direct)
# ============================================================================
# Redirige vers la nouvelle page de supervision (/admin/logs) qui montre
# désormais l'état des agents locaux à la place de l'ancien tunnel HTTP.

@app.route('/admin/tunnel_management')
@login_required
@admin_required
def admin_tunnel_management():
    return redirect(url_for('admin_logs_page'))

# ============================================================================
# FONCTION ADMIN PAR DÉFAUT
# ============================================================================

def create_default_admin():
    """Créer un compte administrateur par défaut si aucun admin n'existe"""
    try:
        print("🔍 Vérification de l'existence d'un administrateur...")
        admin_count = Utilisateur.query.filter_by(statut='admin').count()
        print(f"📊 Nombre d'admins trouvés: {admin_count}")
        
        if admin_count == 0:
            print("👤 Création du compte administrateur par défaut...")
            default_admin = Utilisateur(
                nom='Admin',
                prenom='System',
                email='admin@gmail.com',
                password='Admin123',
                matricule='ADMIN001',
                organisation='UAM/FAST',
                date_naissance=datetime(2024, 10, 20).date(),
                lieu_naissance='Niamey',
                statut='admin',
                email_verifie=True,
                date_inscription=datetime.now()
            )
            
            db.session.add(default_admin)
            db.session.commit()
            
            print("=" * 50)
            print("✅ COMPTE ADMINISTRATEUR PAR DÉFAUT CRÉÉ")
            print("=" * 50)
            print(f"   Email: admin@gmail.com")
            print(f"   Mot de passe: Admin123")  
            print("=" * 50)
        else:
            print("ℹ️ Un administrateur existe déjà, création ignorée.")
        
        return admin_count
    except Exception as e:
        print(f"❌ Erreur création admin par défaut: {e}")
        import traceback
        traceback.print_exc()
        return 0


# ============================================================================
# POINT D'ENTRÉE PRINCIPAL
# ============================================================================
#
# En production sur Render/Railway, ce bloc __main__ n'est PAS exécuté :
# le service doit être démarré avec gunicorn + worker eventlet, qui importe
# directement l'objet `app` (voir Procfile / commande de démarrage) afin de
# supporter les connexions WebSocket persistantes des agents locaux.
# Ce bloc sert uniquement aux tests en local (python app.py).

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        print("✅ Tables créées/vérifiées")
        create_default_admin()

        print("\n" + "="*60)
        print("🌐 MODE HÉBERGEMENT DIRECT (test local)")
        print("="*60)
        print(f"🔗 URL locale : http://localhost:5000")
        print(f"📡 En attente de connexion de l'agent local sur /agent")
        print("="*60 + "\n")

    print("\n🚀 Démarrage de Flask + Socket.IO...")
    port = int(os.environ.get('PORT', 5000))
    socketio.run(app, host='0.0.0.0', port=port, debug=False)