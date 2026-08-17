# api/admin_logs.py - Interface d'entretien / supervision
#
# Page /admin/logs (réservée aux admins) : montre quels agents locaux sont
# connectés, quelles cartes Arduino sont détectées, et le journal d'événements
# récents (connexions/déconnexions, erreurs) pour diagnostiquer rapidement un
# problème (ex: agent hors-ligne, carte qui décroche, etc.)

from flask import jsonify, render_template, request
from utils.decorators import login_required, admin_required
from utils.log_bus import log_bus


def register_admin_logs_routes(app, arduino_controller):

    @app.route('/admin/logs')
    @login_required
    @admin_required
    def admin_logs_page():
        return render_template('admin/logs.html')

    @app.route('/api/admin/logs')
    @login_required
    @admin_required
    def api_admin_logs():
        limit = request.args.get('limit', 200, type=int)
        level = request.args.get('level') or None
        source = request.args.get('source') or None
        since = request.args.get('since', type=float)

        evenements = log_bus.recent(limit=limit, level=level, source=source, since=since)
        return jsonify({'success': True, 'evenements': evenements})

    @app.route('/api/admin/agents')
    @login_required
    @admin_required
    def api_admin_agents():
        agents = arduino_controller.get_agents_status()
        return jsonify({'success': True, 'agents': agents})

    @app.route('/api/admin/connexions')
    @login_required
    @admin_required
    def api_admin_connexions():
        """Vue d'ensemble de toutes les connexions Arduino actives, toutes personnes confondues"""
        connexions = []
        for id_connexion, c in arduino_controller.connexions_arduino.items():
            connexions.append({
                'id_connexion': id_connexion,
                'port': c.get('port'),
                'agent_id': c.get('agent_id'),
                'connecte': c.get('connecte', False),
                'user_email': c.get('user_email'),
                'type_controleur': c.get('type_controleur'),
                'surveillance_active': c.get('surveillance_active'),
                'temperature': c.get('donnees', {}).get('temperature'),
                'consigne': c.get('consigne'),
                'derniere_donnee_recue': c.get('derniere_donnee_recue'),
            })
        return jsonify({'success': True, 'connexions': connexions})
