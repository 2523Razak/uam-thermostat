# utils/security.py
"""
Fonctions de durcissement de sécurité pour l'application, regroupées ici
pour être appliquées en un seul appel depuis app.py :

    from utils.security import init_security, login_rate_limiter
    init_security(app)

Contient :
- Protection CSRF (Flask-WTF) pour toutes les routes qui modifient des
  données (POST/PUT/PATCH/DELETE), y compris les routes API JSON (le
  jeton est transmis automatiquement par static/js/security.js).
- En-têtes HTTP de sécurité (anti-clickjacking, anti-sniffing, etc.).
- Limiteur de débit simple (en mémoire) contre le bruteforce de mots de
  passe sur /connections.
"""
import time
import threading
from collections import defaultdict, deque

from flask import request, jsonify, session
from flask_wtf import CSRFProtect
from flask_wtf.csrf import CSRFError
from werkzeug.security import generate_password_hash, check_password_hash


csrf = CSRFProtect()


# ============================================================================
# MOTS DE PASSE — hachage et vérification rétrocompatible
# ============================================================================
# Historiquement, les mots de passe étaient stockés EN CLAIR dans la base de
# données (colonne Utilisateur.password). C'est une faille de sécurité
# critique : quiconque a accès à la base (fuite, sauvegarde, employé
# malveillant, injection SQL) récupère directement tous les mots de passe.
#
# Les fonctions ci-dessous permettent de migrer en douceur, sans casser
# les comptes existants ni forcer une réinitialisation manuelle :
#  - hash_password() est utilisée pour TOUT nouveau mot de passe (inscription,
#    changement de mot de passe, réinitialisation).
#  - verify_password() sait vérifier aussi bien un hash moderne qu'un ancien
#    mot de passe en clair, et signale à l'appelant qu'il doit re-hasher et
#    sauvegarder le mot de passe (upgrade transparent à la prochaine
#    connexion réussie).

_HASH_PREFIXES = ('pbkdf2:', 'scrypt:', 'argon2', 'bcrypt$', '$2b$', '$2a$')


def hash_password(plain_password: str) -> str:
    """Retourne le hash sécurisé (PBKDF2) d'un mot de passe en clair."""
    return generate_password_hash(plain_password)


def _looks_hashed(value: str) -> bool:
    return bool(value) and value.startswith(_HASH_PREFIXES)


def verify_password(stored_value: str, provided_password: str):
    """
    Vérifie un mot de passe fourni contre la valeur stockée en base.

    Retourne un tuple (is_valid, needs_rehash) :
      - is_valid       : True si le mot de passe correspond
      - needs_rehash   : True si stored_value était en clair (ancien format)
                          et doit être remplacé par hash_password(provided_password)
                          puis sauvegardé par l'appelant.
    """
    if stored_value is None:
        return False, False

    if _looks_hashed(stored_value):
        try:
            return check_password_hash(stored_value, provided_password), False
        except Exception:
            return False, False

    # Ancien format : mot de passe stocké en clair.
    is_valid = stored_value == provided_password
    return is_valid, is_valid


def init_security(app):
    """Active la protection CSRF et les en-têtes de sécurité sur l'app Flask."""

    # ------------------------------------------------------------------
    # CSRF
    # ------------------------------------------------------------------
    csrf.init_app(app)

    @app.errorhandler(CSRFError)
    def _handle_csrf_error(e):
        # Pour les appels API/JSON on renvoie une réponse JSON exploitable
        # par le frontend plutôt qu'une page HTML d'erreur.
        wants_json = (
            request.path.startswith('/api/')
            or request.accept_mimetypes.best == 'application/json'
            or request.is_json
        )
        if wants_json:
            return jsonify({
                'success': False,
                'message': "Session expirée ou jeton de sécurité invalide. Merci de recharger la page et réessayer.",
                'error': 'csrf_invalid'
            }), 400
        from flask import flash, redirect, url_for
        flash("Votre session a expiré. Merci de réessayer.", "error")
        return redirect(url_for('connections'))

    # Les webhooks / intégrations tierces qui ne passent pas par le
    # navigateur (ex : callback de l'agent local Arduino) n'ont pas de
    # cookie de session et ne peuvent donc pas fournir de jeton CSRF ;
    # elles sont protégées différemment (secret partagé). On les exempte
    # explicitement ici si besoin via app.config['WTF_CSRF_EXEMPT_LIST'].

    # ------------------------------------------------------------------
    # En-têtes HTTP de sécurité
    # ------------------------------------------------------------------
    @app.after_request
    def _set_security_headers(response):
        response.headers.setdefault('X-Content-Type-Options', 'nosniff')
        response.headers.setdefault('X-Frame-Options', 'SAMEORIGIN')
        response.headers.setdefault('Referrer-Policy', 'strict-origin-when-cross-origin')
        response.headers.setdefault('Permissions-Policy', 'geolocation=(), microphone=(), camera=()')
        # HSTS uniquement si la requête est déjà en HTTPS (proxy Render/Railway)
        if request.is_secure:
            response.headers.setdefault(
                'Strict-Transport-Security', 'max-age=63072000; includeSubDomains'
            )
        return response

    return app


# ============================================================================
# LIMITEUR DE DÉBIT (anti brute-force) — implémentation simple en mémoire
# ============================================================================
# Pour un déploiement multi-workers/multi-instances il est préférable
# d'utiliser Flask-Limiter + Redis, mais cette implémentation en mémoire
# suffit à ralentir sérieusement les attaques automatisées sur un seul
# worker et ne nécessite aucune dépendance supplémentaire.

class _RateLimiter:
    def __init__(self, max_attempts=8, window_seconds=300, lock_seconds=600):
        self.max_attempts = max_attempts
        self.window_seconds = window_seconds
        self.lock_seconds = lock_seconds
        self._attempts = defaultdict(deque)
        self._locked_until = {}
        self._lock = threading.Lock()

    def _key(self):
        # On combine l'IP et l'identifiant tenté pour éviter qu'un
        # attaquant ne bloque un utilisateur légitime simplement en
        # échouant plusieurs fois avec son identifiant depuis une autre IP,
        # tout en limitant correctement le bruteforce depuis une IP donnée.
        ip = request.headers.get('X-Forwarded-For', request.remote_addr) or 'unknown'
        return ip.split(',')[0].strip()

    def is_locked(self):
        key = self._key()
        with self._lock:
            locked_until = self._locked_until.get(key)
            if locked_until and time.time() < locked_until:
                return True, int(locked_until - time.time())
            if locked_until:
                del self._locked_until[key]
        return False, 0

    def register_failure(self):
        key = self._key()
        now = time.time()
        with self._lock:
            attempts = self._attempts[key]
            attempts.append(now)
            while attempts and now - attempts[0] > self.window_seconds:
                attempts.popleft()
            if len(attempts) >= self.max_attempts:
                self._locked_until[key] = now + self.lock_seconds
                attempts.clear()

    def register_success(self):
        key = self._key()
        with self._lock:
            self._attempts.pop(key, None)
            self._locked_until.pop(key, None)


login_rate_limiter = _RateLimiter(max_attempts=8, window_seconds=300, lock_seconds=600)
