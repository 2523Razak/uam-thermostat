# utils/email_utils.py - Version finale sans fichiers externes

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from flask import current_app as app
import secrets
import string
import socket

# Logos utilises dans les emails : servis depuis static/image/ via l'URL
# publique du tunnel, plutot qu'encodes en base64. De nombreux clients mail
# (notamment Outlook de bureau) n'affichent tout simplement pas les images
# encodees en base64 (data URI) dans les emails - c'est pour ca qu'elles ne
# s'affichaient pas. Une URL classique fonctionne partout, y compris Outlook.
def get_logo_url(nom_fichier):
    """Construit l'URL publique d'une image de static/image/ pour les emails."""
    base_url = get_best_base_url()
    return f"{base_url}/static/image/{nom_fichier}"



# ============================================================================
# FONCTIONS DE GESTION DES LIENS
# ============================================================================

def get_local_ip_url():
    """Recupere l'URL avec l'adresse IP locale (fonctionne uniquement pour
    une personne connectee au meme reseau que le serveur)."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
        
        if local_ip and local_ip != '127.0.0.1':
            port = app.config.get('PORT', 5000)
            return f"http://{local_ip}:{port}"
    except Exception:
        pass
    
    return None


def get_public_tunnel_url():
    """Recupere l'URL publique du tunnel Render, configuree dans app.py
    (app.config['PUBLIC_TUNNEL_URL']). Fonctionne pour n'importe qui,
    depuis n'importe quel reseau."""
    return app.config.get('PUBLIC_TUNNEL_URL')


def get_best_base_url():
    """
    Retourne la meilleure URL de base disponible.
    Priorite : tunnel public (Render) > IP locale > fallback localhost.
    """
    public_url = get_public_tunnel_url()
    if public_url:
        print(f"Utilisation du tunnel public: {public_url}")
        return public_url
    
    local_url = get_local_ip_url()
    if local_url:
        print(f"Utilisation IP locale: {local_url}")
        return local_url
    
    # Fallback
    fallback = f"http://localhost:{app.config.get('PORT', 5000)}"
    print(f"Utilisation fallback: {fallback}")
    return fallback


def get_page_link(page_path):
    """
    Retourne le lien complet pour une page specifique
    """
    base_url = get_best_base_url()
    return f"{base_url}{page_path}"


def get_all_links():
    """
    Retourne les liens disponibles pour affichage dans le footer.
    'local' est mis en avant en premier : une personne sur le meme reseau
    que le serveur peut s'en servir directement pour se connecter.
    'public' (tunnel Render) fonctionne depuis n'importe ou et sert de
    lien principal pour les liens de verification/action des emails.
    """
    local_url = get_local_ip_url()
    public_url = get_public_tunnel_url()
    
    return {
        'local': local_url,
        'public': public_url,
        'primary': public_url or local_url
    }


# ============================================================================
# FONCTIONS D'ENVOI D'EMAIL
# ============================================================================

def envoyer_email(destinataire, sujet, contenu_html, contenu_texte=None):
    """Envoie un email à l'utilisateur"""
    try:
        message = MIMEMultipart('alternative')
        message['Subject'] = sujet
        message['From'] = app.config['MAIL_DEFAULT_SENDER']
        message['To'] = destinataire
        
        if contenu_texte:
            part1 = MIMEText(contenu_texte, 'plain', 'utf-8')
            message.attach(part1)
        
        part2 = MIMEText(contenu_html, 'html', 'utf-8')
        message.attach(part2)
        
        with smtplib.SMTP(app.config['MAIL_SERVER'], app.config['MAIL_PORT']) as server:
            server.starttls()
            server.login(app.config['MAIL_USERNAME'], app.config['MAIL_PASSWORD'])
            server.send_message(message)
        
        print(f"Email envoye a {destinataire}")
        return True
        
    except Exception as e:
        print(f"Erreur envoi email a {destinataire}: {e}")
        return False


def get_header_html():
    """Genere l'en-tete HTML avec le logo"""
    return f"""
    <div class="header">
        <div style="display: flex; align-items: center; justify-content: center; gap: 12px;">
            <img src="{get_logo_url('thermostat.png')}" alt="Thermostat UAM" style="height: 40px; width: auto;">
            <div>
                <h1 style="margin: 0; font-size: 24px;">Thermostat UAM</h1>
            </div>
        </div>
    </div>
    """


def get_footer_html():
    """Genere le pied de page avec le logo et les liens d'acces
    (local en premier, puis le lien public du tunnel)."""
    links = get_all_links()
    local_url = links.get('local')
    public_url = links.get('public')
    
    footer_html = f"""
        <div class="footer">
            <div style="text-align: center; margin-bottom: 18px;">
                <img src="{get_logo_url('thermostat.png')}" alt="Thermostat UAM" style="height: 48px; width: auto;">
            </div>
            <div class="access-info">
                <p style="margin: 0 0 10px 0; font-weight: 600;">Acces a la plateforme :</p>
    """
    
    if local_url:
        footer_html += f'                <p style="margin: 5px 0;">• Acces local : <a href="{local_url}" style="color: #1ea95e;">{local_url}</a></p>\n'
        footer_html += '                <p style="margin: 5px 0; font-size: 11px; color: #888;">Ce lien fonctionne uniquement pour une personne connectee au meme reseau que le serveur.</p>\n'
    
    if public_url:
        footer_html += f'                <p style="margin: 5px 0;">• Acces public : <a href="{public_url}" style="color: #1ea95e;">{public_url}</a></p>\n'
    
    footer_html += """
            </div>
            <div style="margin-top: 20px; padding-top: 15px; border-top: 1px solid #eee;">
                <p>Cet email est un message automatique, merci de ne pas y repondre.</p>
                <p>&copy; 2025 Thermostat UAM - Universite Abdou Moumouni / Faculte des Sciences et Techniques</p>
            </div>
        </div>
    """
    
    return footer_html


def get_button_html(text, url):
    """Genere un bouton simple et elegant"""
    return f'<a href="{url}" style="display: inline-block; background: #1ea95e; color: white; padding: 8px 22px; text-decoration: none; border-radius: 25px; font-weight: 500; font-size: 13px; margin: 10px 0;">{text}</a>'


# ============================================================================
# EMAIL DE VERIFICATION
# ============================================================================

def envoyer_email_verification(utilisateur):
    """Envoie un email de verification professionnel"""
    sujet = "Thermostat UAM - Verification de votre adresse email"
    
    verification_path = f"/verifier_email/{utilisateur.token_verification}"
    primary_link = get_page_link(verification_path)
    
    header_html = get_header_html()
    footer_html = get_footer_html()
    button = get_button_html("Verifier mon email", primary_link)
    
    print(f"\n" + "="*60)
    print(f"Email de verification envoye a: {utilisateur.email}")
    print(f"Lien principal: {primary_link}")
    print("="*60 + "\n")
    
    contenu_html = f"""
    <!DOCTYPE html>
    <html lang="fr">
    <head>
        <meta charset="UTF-8">
        <title>Verification Email - Thermostat UAM</title>
        <style>
            body {{ font-family: 'Segoe UI', 'Roboto', Arial, sans-serif; line-height: 1.6; color: #333; margin: 0; padding: 0; background: #f5f5f5; }}
            .container {{ max-width: 650px; margin: 30px auto; padding: 0; background: #ffffff; border-radius: 12px; box-shadow: 0 4px 15px rgba(0,0,0,0.1); overflow: hidden; }}
            .header {{ background: linear-gradient(135deg, #010207 0%, #2c3e50 100%); color: white; padding: 28px 20px; text-align: center; }}
            .content {{ padding: 38px 32px; }}
            .info-box {{ background: #e3f2fd; padding: 22px; border-radius: 10px; margin: 28px 0; border-left: 4px solid #2196f3; }}
            .warning-box {{ background: #fff3e0; padding: 22px; border-radius: 10px; margin: 28px 0; border-left: 4px solid #ff9800; }}
            .footer {{ background: #f8f9fa; padding: 25px 30px; border-top: 1px solid #eee; color: #888; font-size: 12px; }}
            .lien-alternatif {{ font-size: 12px; color: #888; word-break: break-all; margin-top: 15px; text-align: center; padding: 12px; background: #f9f9f9; border-radius: 8px; }}
        </style>
    </head>
    <body>
        <div class="container">
            {header_html}
            
            <div class="content">
                <p style="font-size: 16px;">Bonjour <strong>{utilisateur.prenom} {utilisateur.nom}</strong>,</p>
                
                <p>Merci de vous etre inscrit sur la plateforme Thermostat UAM. Pour finaliser votre inscription et activer votre compte, veuillez confirmer votre adresse email en cliquant sur le bouton ci-dessous :</p>
                
                <div style="text-align: center; margin: 28px 0;">
                    {button}
                </div>
                
                <div class="lien-alternatif">
                    <p>Lien direct : <a href="{primary_link}" style="color: #1ea95e;">{primary_link}</a></p>
                </div>
                
                <div class="warning-box">
                    <p style="font-weight: 600;">Delai de validation</p>
                    <p>Ce lien de verification est valable <strong>24 heures</strong>.</p>
                </div>
                
                <div class="info-box">
                    <p style="font-weight: 600;">Prochaines etapes</p>
                    <ul>
                        <li>Acceder a votre espace personnel</li>
                        <li>Configurer et controler votre thermostat</li>
                        <li>Consulter et realiser vos travaux pratiques</li>
                    </ul>
                </div>
                
                <p>Si vous n'etes pas a l'origine de cette inscription, ignorez cet email.</p>
                
                <p>Cordialement,<br>
                <strong>L'equipe Thermostat UAM</strong></p>
                <div style="text-align: right; margin-top: 18px;">
                    <img src="{get_logo_url('uam.jpg')}" alt="UAM" style="height: 26px; width: 26px; border-radius: 50%; object-fit: cover; margin-left: 8px; vertical-align: middle;">
                    <img src="{get_logo_url('fast.jpg')}" alt="FAST" style="height: 26px; width: 26px; border-radius: 50%; object-fit: cover; margin-left: 8px; vertical-align: middle;">
                </div>
            </div>
            
            {footer_html}
        </div>
    </body>
    </html>
    """
    
    contenu_texte = f"""
    THERMOSTAT UAM - VERIFICATION DE VOTRE ADRESSE EMAIL
    
    Bonjour {utilisateur.prenom} {utilisateur.nom},
    
    Merci de votre inscription. Pour activer votre compte, veuillez cliquer sur le lien suivant :
    
    {primary_link}
    
    Ce lien est valable 24 heures.
    
    Cordialement,
    L'equipe Thermostat UAM
    """
    
    return envoyer_email(utilisateur.email, sujet, contenu_html, contenu_texte)


# ============================================================================
# EMAIL DE BIENVENUE
# ============================================================================

def envoyer_email_bienvenue(utilisateur):
    """Envoie un email de bienvenue professionnel"""
    sujet = "Thermostat UAM - Bienvenue sur la plateforme"
    
    est_admin = utilisateur.statut == 'admin'
    connexion_path = "/connections"
    primary_link = get_page_link(connexion_path)
    
    header_html = get_header_html()
    footer_html = get_footer_html()
    button = get_button_html("Acceder a mon espace", primary_link)
    
    contenu_html = f"""
    <!DOCTYPE html>
    <html lang="fr">
    <head>
        <meta charset="UTF-8">
        <title>Bienvenue - Thermostat UAM</title>
        <style>
            body {{ font-family: 'Segoe UI', 'Roboto', Arial, sans-serif; line-height: 1.6; color: #333; margin: 0; padding: 0; background: #f5f5f5; }}
            .container {{ max-width: 650px; margin: 30px auto; padding: 0; background: #ffffff; border-radius: 12px; box-shadow: 0 4px 15px rgba(0,0,0,0.1); overflow: hidden; }}
            .header {{ background: linear-gradient(135deg, #010207 0%, #2c3e50 100%); color: white; padding: 28px 20px; text-align: center; }}
            .content {{ padding: 38px 32px; }}
            .success-box {{ background: #e8f5e9; padding: 22px; border-radius: 10px; margin: 28px 0; text-align: center; border-left: 4px solid #4caf50; }}
            .info-box {{ background: #e3f2fd; padding: 22px; border-radius: 10px; margin: 28px 0; border-left: 4px solid #2196f3; }}
            .admin-box {{ background: #f3e5f5; padding: 22px; border-radius: 10px; margin: 28px 0; border-left: 4px solid #9c27b0; }}
            .credentials-box {{ background: #fff8e1; padding: 22px; border-radius: 10px; margin: 28px 0; border-left: 4px solid #ffc107; }}
            .footer {{ background: #f8f9fa; padding: 25px 30px; border-top: 1px solid #eee; color: #888; font-size: 12px; }}
            .highlight {{ font-weight: 600; color: #1ea95e; }}
            .lien-alternatif {{ font-size: 12px; color: #888; word-break: break-all; margin-top: 15px; text-align: center; padding: 12px; background: #f9f9f9; border-radius: 8px; }}
        </style>
    </head>
    <body>
        <div class="container">
            {header_html}
            
            <div class="content">
                <p>Bonjour <strong>{utilisateur.prenom} {utilisateur.nom}</strong>,</p>
                
                <div class="success-box">
                    <p style="font-weight: 600;">Compte active avec succes</p>
                    <p>Votre compte a ete valide et vous pouvez desormais acceder a toutes les fonctionnalites.</p>
                </div>
                
                {f'''
                <div class="admin-box">
                    <p style="font-weight: 600;">Acces Administrateur</p>
                    <ul>
                        <li>Gerer l'ensemble des utilisateurs</li>
                        <li>Creer et superviser les travaux pratiques</li>
                        <li>Configurer et surveiller le systeme thermostatique</li>
                    </ul>
                </div>
                ''' if est_admin else ''}
                
                <div class="credentials-box">
                    <p style="font-weight: 600;">Identifiants de connexion</p>
                    <p><strong>Identifiant :</strong> {utilisateur.email}</p>
                    <p><strong>Identifiant alternatif :</strong> {utilisateur.matricule}</p>
                    <p><strong>Statut :</strong> <span class="highlight">{utilisateur.statut.upper()}</span></p>
                    <p><strong>Date d'activation :</strong> {datetime.now().strftime('%d/%m/%Y a %H:%M')}</p>
                </div>
                
                <div class="info-box">
                    <p>Cliquez sur le bouton ci-dessous pour vous connecter :</p>
                    
                    <div style="text-align: center;">
                        {button}
                    </div>
                    
                    <div class="lien-alternatif">
                        <p>Lien direct : <a href="{primary_link}" style="color: #1ea95e;">{primary_link}</a></p>
                    </div>
                </div>
                
                <div style="background: #f5f5f5; padding: 22px; border-radius: 10px; margin: 28px 0;">
                    <p style="font-weight: 600;">Fonctionnalites disponibles</p>
                    <ul>
                        <li>Controle et surveillance en temps reel du thermostat</li>
                        <li>Acces aux travaux pratiques et ressources pedagogiques</li>
                        <li>Historique detaille des donnees et activites</li>
                        <li>Personnalisation avancee des parametres</li>
                    </ul>
                </div>
                
                <p>Pour toute question, n'hesitez pas a contacter notre equipe.</p>
                
                <p>Cordialement,<br>
                <strong>L'equipe Thermostat UAM</strong></p>
                <div style="text-align: right; margin-top: 18px;">
                    <img src="{get_logo_url('uam.jpg')}" alt="UAM" style="height: 26px; width: 26px; border-radius: 50%; object-fit: cover; margin-left: 8px; vertical-align: middle;">
                    <img src="{get_logo_url('fast.jpg')}" alt="FAST" style="height: 26px; width: 26px; border-radius: 50%; object-fit: cover; margin-left: 8px; vertical-align: middle;">
                </div>
            </div>
            
            {footer_html}
        </div>
    </body>
    </html>
    """
    
    contenu_texte = f"""
    THERMOSTAT UAM - BIENVENUE SUR LA PLATEFORME
    
    Bonjour {utilisateur.prenom} {utilisateur.nom},
    
    VOTRE COMPTE EST ACTIVE
    
    Identifiants :
    - Email : {utilisateur.email}
    - Matricule : {utilisateur.matricule}
    
    LIEN DE CONNEXION : {primary_link}
    
    Cordialement,
    L'equipe Thermostat UAM
    """
    
    return envoyer_email(utilisateur.email, sujet, contenu_html, contenu_texte)


# ============================================================================
# EMAIL DE CREATION PAR ADMIN
# ============================================================================

def envoyer_email_creation_admin(utilisateur, createur_admin):
    """Envoie un email pour un compte cree par un administrateur"""
    sujet = "Thermostat UAM - Votre compte a ete cree"
    
    connexion_path = "/connections"
    primary_link = get_page_link(connexion_path)
    
    header_html = get_header_html()
    footer_html = get_footer_html()
    button = get_button_html("Acceder a mon espace", primary_link)
    
    contenu_html = f"""
    <!DOCTYPE html>
    <html lang="fr">
    <head>
        <meta charset="UTF-8">
        <title>Compte cree - Thermostat UAM</title>
        <style>
            body {{ font-family: 'Segoe UI', 'Roboto', Arial, sans-serif; line-height: 1.6; color: #333; margin: 0; padding: 0; background: #f5f5f5; }}
            .container {{ max-width: 650px; margin: 30px auto; padding: 0; background: #ffffff; border-radius: 12px; box-shadow: 0 4px 15px rgba(0,0,0,0.1); overflow: hidden; }}
            .header {{ background: linear-gradient(135deg, #010207 0%, #2c3e50 100%); color: white; padding: 28px 20px; text-align: center; }}
            .content {{ padding: 38px 32px; }}
            .info-box {{ background: #e3f2fd; padding: 22px; border-radius: 10px; margin: 28px 0; border-left: 4px solid #2196f3; }}
            .credentials-box {{ background: #fff8e1; padding: 22px; border-radius: 10px; margin: 28px 0; border-left: 4px solid #ffc107; }}
            .footer {{ background: #f8f9fa; padding: 25px 30px; border-top: 1px solid #eee; color: #888; font-size: 12px; }}
            .lien-alternatif {{ font-size: 12px; color: #888; word-break: break-all; margin-top: 15px; text-align: center; padding: 12px; background: #f9f9f9; border-radius: 8px; }}
        </style>
    </head>
    <body>
        <div class="container">
            {header_html}
            
            <div class="content">
                <p>Bonjour <strong>{utilisateur.prenom} {utilisateur.nom}</strong>,</p>
                
                <div class="info-box">
                    <p style="font-weight: 600;">Compte cree par l'administration</p>
                    <p><strong>Administrateur :</strong> {createur_admin.prenom} {createur_admin.nom}</p>
                    <p><strong>Date de creation :</strong> {datetime.now().strftime('%d/%m/%Y a %H:%M')}</p>
                </div>
                
                <div class="credentials-box">
                    <p style="font-weight: 600;">Vos informations de connexion</p>
                    <p><strong>Identifiant :</strong> {utilisateur.email}</p>
                    <p><strong>Identifiant alternatif :</strong> {utilisateur.matricule}</p>
                    <p><strong>Statut :</strong> {utilisateur.statut.upper()}</p>
                </div>
                
                <div style="text-align: center;">
                    {button}
                </div>
                
                <div class="lien-alternatif">
                    <p>Lien direct : <a href="{primary_link}" style="color: #1ea95e;">{primary_link}</a></p>
                </div>
                
                <p>Pour toute question, contactez l'administrateur qui a cree votre compte.</p>
                
                <p>Cordialement,<br>
                <strong>L'equipe Thermostat UAM</strong></p>
                <div style="text-align: right; margin-top: 18px;">
                    <img src="{get_logo_url('uam.jpg')}" alt="UAM" style="height: 26px; width: 26px; border-radius: 50%; object-fit: cover; margin-left: 8px; vertical-align: middle;">
                    <img src="{get_logo_url('fast.jpg')}" alt="FAST" style="height: 26px; width: 26px; border-radius: 50%; object-fit: cover; margin-left: 8px; vertical-align: middle;">
                </div>
            </div>
            
            {footer_html}
        </div>
    </body>
    </html>
    """
    
    contenu_texte = f"""
    THERMOSTAT UAM - VOTRE COMPTE A ETE CREE
    
    Bonjour {utilisateur.prenom} {utilisateur.nom},
    
    Un administrateur a cree votre compte.
    
    Identifiants :
    - Email : {utilisateur.email}
    - Matricule : {utilisateur.matricule}
    
    LIEN DE CONNEXION : {primary_link}
    
    Cordialement,
    L'equipe Thermostat UAM
    """
    
    return envoyer_email(utilisateur.email, sujet, contenu_html, contenu_texte)


# ============================================================================
# NOTIFICATION DE CHANGEMENT DE STATUT
# ============================================================================

def envoyer_notification_statut(utilisateur, ancien_statut, nouveau_statut, raison=None):
    """Envoie une notification de changement de statut"""
    sujet = "Thermostat UAM - Notification de changement de statut"
    
    connexion_path = "/connections"
    primary_link = get_page_link(connexion_path)
    
    header_html = get_header_html()
    footer_html = get_footer_html()
    button = get_button_html("Acceder a la plateforme", primary_link)
    
    contenu_html = f"""
    <!DOCTYPE html>
    <html lang="fr">
    <head>
        <meta charset="UTF-8">
        <title>Changement de statut - Thermostat UAM</title>
        <style>
            body {{ font-family: 'Segoe UI', 'Roboto', Arial, sans-serif; line-height: 1.6; color: #333; margin: 0; padding: 0; background: #f5f5f5; }}
            .container {{ max-width: 650px; margin: 30px auto; padding: 0; background: #ffffff; border-radius: 12px; box-shadow: 0 4px 15px rgba(0,0,0,0.1); overflow: hidden; }}
            .header {{ background: linear-gradient(135deg, #010207 0%, #2c3e50 100%); color: white; padding: 28px 20px; text-align: center; }}
            .content {{ padding: 38px 32px; }}
            .statut-box {{ background: #f5f5f5; padding: 22px; border-radius: 10px; margin: 28px 0; border-left: 4px solid #2196f3; }}
            .warning-box {{ background: #ffebee; padding: 22px; border-radius: 10px; margin: 28px 0; border-left: 4px solid #f44336; }}
            .success-box {{ background: #e8f5e9; padding: 22px; border-radius: 10px; margin: 28px 0; border-left: 4px solid #4caf50; }}
            .info-box {{ background: #e3f2fd; padding: 22px; border-radius: 10px; margin: 28px 0; border-left: 4px solid #2196f3; }}
            .badge {{ display: inline-block; padding: 4px 12px; border-radius: 20px; font-size: 12px; font-weight: 600; }}
            .badge-admin {{ background: #9c27b0; color: white; }}
            .badge-user {{ background: #4caf50; color: white; }}
            .badge-bloque {{ background: #f44336; color: white; }}
            .footer {{ background: #f8f9fa; padding: 25px 30px; border-top: 1px solid #eee; color: #888; font-size: 12px; }}
            .lien-alternatif {{ font-size: 12px; color: #888; word-break: break-all; margin-top: 15px; text-align: center; padding: 12px; background: #f9f9f9; border-radius: 8px; }}
        </style>
    </head>
    <body>
        <div class="container">
            {header_html}
            
            <div class="content">
                <p>Bonjour <strong>{utilisateur.prenom} {utilisateur.nom}</strong>,</p>
                
                <div class="statut-box">
                    <p style="font-weight: 600;">Votre statut a ete modifie</p>
                    <p><strong>Ancien statut :</strong> <span class="badge badge-user">{ancien_statut.upper()}</span></p>
                    <p><strong>Nouveau statut :</strong> <span class="badge badge-{nouveau_statut if nouveau_statut in ['admin','user','bloque'] else 'user'}">{nouveau_statut.upper()}</span></p>
                    <p><strong>Date :</strong> {datetime.now().strftime('%d/%m/%Y a %H:%M')}</p>
                    {f"<p><strong>Raison :</strong> {raison}</p>" if raison else ""}
                </div>
                
                {f'''
                <div class="warning-box">
                    <p style="font-weight: 600;">Compte bloque</p>
                    <p>Votre compte a ete bloque. Vous ne pouvez plus acceder a la plateforme.</p>
                </div>
                ''' if nouveau_statut == 'bloque' else ''}
                
                {f'''
                <div class="success-box">
                    <p style="font-weight: 600;">Compte debloque</p>
                    <p>Votre compte a ete debloque. Vous pouvez a nouveau acceder a la plateforme.</p>
                </div>
                ''' if ancien_statut == 'bloque' and nouveau_statut != 'bloque' else ''}
                
                {f'''
                <div class="info-box">
                    <p style="font-weight: 600;">Nouveau statut administrateur</p>
                    <p>Felicitations ! Votre compte a ete promu au statut d'administrateur.</p>
                </div>
                ''' if nouveau_statut == 'admin' else ''}
                
                <div class="info-box">
                    <p>Cliquez sur le bouton ci-dessous pour vous connecter :</p>
                    
                    <div style="text-align: center;">
                        {button}
                    </div>
                    
                    <div class="lien-alternatif">
                        <p>Lien direct : <a href="{primary_link}" style="color: #1ea95e;">{primary_link}</a></p>
                    </div>
                </div>
                
                <p>Cordialement,<br>
                <strong>L'equipe Thermostat UAM</strong></p>
                <div style="text-align: right; margin-top: 18px;">
                    <img src="{get_logo_url('uam.jpg')}" alt="UAM" style="height: 26px; width: 26px; border-radius: 50%; object-fit: cover; margin-left: 8px; vertical-align: middle;">
                    <img src="{get_logo_url('fast.jpg')}" alt="FAST" style="height: 26px; width: 26px; border-radius: 50%; object-fit: cover; margin-left: 8px; vertical-align: middle;">
                </div>
            </div>
            
            {footer_html}
        </div>
    </body>
    </html>
    """
    
    contenu_texte = f"""
    THERMOSTAT UAM - NOTIFICATION DE CHANGEMENT DE STATUT
    
    Bonjour {utilisateur.prenom} {utilisateur.nom},
    
    Votre statut a ete modifie :
    Ancien : {ancien_statut.upper()}
    Nouveau : {nouveau_statut.upper()}
    Date : {datetime.now().strftime('%d/%m/%Y a %H:%M')}
    
    LIEN DE CONNEXION : {primary_link}
    
    Cordialement,
    L'equipe Thermostat UAM
    """
    
    return envoyer_email(utilisateur.email, sujet, contenu_html, contenu_texte)


# ============================================================================
# CONFIRMATION DE CHANGEMENT DE MOT DE PASSE
# ============================================================================

def envoyer_confirmation_changement_mdp(utilisateur, ip_address):
    """Envoie une confirmation de changement de mot de passe"""
    sujet = "Thermostat UAM - Confirmation de changement de mot de passe"
    
    connexion_path = "/connections"
    primary_link = get_page_link(connexion_path)
    
    header_html = get_header_html()
    footer_html = get_footer_html()
    button = get_button_html("Acceder a la plateforme", primary_link)
    
    contenu_html = f"""
    <!DOCTYPE html>
    <html lang="fr">
    <head>
        <meta charset="UTF-8">
        <title>Changement mot de passe - Thermostat UAM</title>
        <style>
            body {{ font-family: 'Segoe UI', 'Roboto', Arial, sans-serif; line-height: 1.6; color: #333; margin: 0; padding: 0; background: #f5f5f5; }}
            .container {{ max-width: 650px; margin: 30px auto; padding: 0; background: #ffffff; border-radius: 12px; box-shadow: 0 4px 15px rgba(0,0,0,0.1); overflow: hidden; }}
            .header {{ background: linear-gradient(135deg, #010207 0%, #2c3e50 100%); color: white; padding: 28px 20px; text-align: center; }}
            .content {{ padding: 38px 32px; }}
            .success-box {{ background: #e8f5e9; padding: 22px; border-radius: 10px; margin: 28px 0; text-align: center; border-left: 4px solid #4caf50; }}
            .info-box {{ background: #e3f2fd; padding: 22px; border-radius: 10px; margin: 28px 0; border-left: 4px solid #2196f3; }}
            .warning-box {{ background: #fff3e0; padding: 22px; border-radius: 10px; margin: 28px 0; border-left: 4px solid #ff9800; }}
            .footer {{ background: #f8f9fa; padding: 25px 30px; border-top: 1px solid #eee; color: #888; font-size: 12px; }}
            .lien-alternatif {{ font-size: 12px; color: #888; word-break: break-all; margin-top: 15px; text-align: center; padding: 12px; background: #f9f9f9; border-radius: 8px; }}
        </style>
    </head>
    <body>
        <div class="container">
            {header_html}
            
            <div class="content">
                <p>Bonjour <strong>{utilisateur.prenom} {utilisateur.nom}</strong>,</p>
                
                <div class="success-box">
                    <p style="font-weight: 600;">Mot de passe modifie avec succes</p>
                </div>
                
                <div class="info-box">
                    <p style="font-weight: 600;">Details de l'operation</p>
                    <p><strong>Date :</strong> {datetime.now().strftime('%d/%m/%Y a %H:%M:%S')}</p>
                    <p><strong>Adresse IP :</strong> {ip_address}</p>
                    <p><strong>Compte :</strong> {utilisateur.email}</p>
                </div>
                
                <div class="warning-box">
                    <p style="font-weight: 600;">Si vous n'etes pas a l'origine de ce changement</p>
                    <p>Contactez immediatement l'administrateur.</p>
                </div>
                
                <div class="info-box">
                    <p>Cliquez sur le bouton ci-dessous pour vous connecter :</p>
                    
                    <div style="text-align: center;">
                        {button}
                    </div>
                    
                    <div class="lien-alternatif">
                        <p>Lien direct : <a href="{primary_link}" style="color: #1ea95e;">{primary_link}</a></p>
                    </div>
                </div>
                
                <p>Cordialement,<br>
                <strong>L'equipe de securite Thermostat UAM</strong></p>
                <div style="text-align: right; margin-top: 18px;">
                    <img src="{get_logo_url('uam.jpg')}" alt="UAM" style="height: 26px; width: 26px; border-radius: 50%; object-fit: cover; margin-left: 8px; vertical-align: middle;">
                    <img src="{get_logo_url('fast.jpg')}" alt="FAST" style="height: 26px; width: 26px; border-radius: 50%; object-fit: cover; margin-left: 8px; vertical-align: middle;">
                </div>
            </div>
            
            {footer_html}
        </div>
    </body>
    </html>
    """
    
    contenu_texte = f"""
    THERMOSTAT UAM - CONFIRMATION DE CHANGEMENT DE MOT DE PASSE
    
    Bonjour {utilisateur.prenom} {utilisateur.nom},
    
    Votre mot de passe a ete modifie avec succes.
    
    Date : {datetime.now().strftime('%d/%m/%Y a %H:%M:%S')}
    IP : {ip_address}
    
    LIEN DE CONNEXION : {primary_link}
    
    Cordialement,
    L'equipe Thermostat UAM
    """
    
    return envoyer_email(utilisateur.email, sujet, contenu_html, contenu_texte)


# ============================================================================
# FONCTION UTILITAIRE
# ============================================================================

def generate_token(length=32):
    """Genere un token aleatoire pour la verification email"""
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))