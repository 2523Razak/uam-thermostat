# api/arduino.py - Routes API pour Arduino
from flask import jsonify, request, session, Response
from utils.decorators import login_required, connection_ownership_required
from utils.audit_logger import audit_logger
import threading
import time
from datetime import datetime
import csv
import io
from utils.data_export import exporter_donnees_csv, creer_reponse_csv

def register_arduino_routes(app, arduino_controller):
    """Enregistre toutes les routes API pour Arduino avec sécurité"""
    
    # -----------------------------------------------
    # Routes pour la gestion des ports Arduino
    # -----------------------------------------------
    @app.route('/api/ports')
    @login_required
    def get_ports():
        """API pour récupérer les ports Arduino disponibles"""
        try:
            ports = arduino_controller.mettre_a_jour_disponibilite_ports()
            ports_disponibles = [p for p in ports if not p['en_utilisation']]
            print(f"Ports Arduino détectés: {len(ports)} - Disponibles: {len(ports_disponibles)}")
            return jsonify(ports)
        except Exception as e:
            print(f"❌ Erreur récupération ports: {e}")
            return jsonify([])
    
    # -----------------------------------------------
    # Routes pour la gestion des connexions Arduino
    # -----------------------------------------------
    @app.route('/api/check_connection')
    @login_required
    def check_connection():
        """API pour vérifier si une connexion est active"""
        try:
            id_connexion = request.args.get('connection_id')
            
            if id_connexion and id_connexion in arduino_controller.connexions_arduino:
                connexion = arduino_controller.connexions_arduino[id_connexion]
                if connexion.get('connecte'):
                    port = connexion.get('port')
                    if port and not arduino_controller.verifier_port_existe(port):
                        print(f"❌ Port {port} n'existe plus physiquement")
                        connexion['connecte'] = False
                        return jsonify({'active': False})
                    
                    return jsonify({'active': True})
            
            return jsonify({'active': False})
        except Exception as e:
            print(f"❌ Erreur vérification connexion: {e}")
            return jsonify({'active': False})
    
    @app.route('/api/connect', methods=['POST'])
    @login_required
    def connect_arduino():
        """API pour connecter un Arduino avec sécurité"""
        try:
            donnees = request.json
            port = donnees.get('port')
            
            if not port:
                return jsonify({'success': False, 'message': 'Port non spécifié'})

            ports_actuels = arduino_controller.mettre_a_jour_disponibilite_ports()
            info_port = next((p for p in ports_actuels if p['port'] == port), None)
            
            if info_port and info_port['en_utilisation']:
                return jsonify({'success': False, 'message': 'Port déjà utilisé'})

            for id_connexion, connexion in arduino_controller.connexions_arduino.items():
                if connexion.get('connecte') and port in id_connexion:
                    return jsonify({'success': False, 'message': 'Port déjà utilisé'})

            # ID de connexion inclut user_id pour la sécurité
            current_user_id = session.get('user_id')
            current_user_email = session.get('user_email', 'unknown')
            id_connexion = f"user_{current_user_id}_{int(time.time())}_{port.replace('/', '_')}"
            
            print(f"Début connexion sécurisée: {id_connexion} pour user {current_user_id}")
            
            # Log d'audit de la tentative
            audit_logger.log(
                event_type='ARDUINO_CONNECT_ATTEMPT',
                user_id=current_user_id,
                connection_id=id_connexion,
                details=f"Tentative de connexion au port {port}",
                ip_address=request.remote_addr
            )
            
            # Lancer la connexion dans un thread avec les infos utilisateur
            thread = threading.Thread(
                target=arduino_controller.lire_donnees_arduino, 
                args=(port, id_connexion, current_user_id, current_user_email),
                daemon=True
            )
            thread.start()
            
            attente_maximale = 5
            for i in range(attente_maximale * 2):
                if (id_connexion in arduino_controller.connexions_arduino and 
                    arduino_controller.connexions_arduino[id_connexion]['connecte']):
                    
                    print(f"✅ Connexion réussie: {id_connexion}")
                    
                    # Log de succès
                    audit_logger.log(
                        event_type='ARDUINO_CONNECT_SUCCESS',
                        user_id=current_user_id,
                        connection_id=id_connexion,
                        details=f"Connexion réussie au port {port}",
                        ip_address=request.remote_addr
                    )
                    
                    return jsonify({
                        'success': True, 
                        'connection_id': id_connexion,
                        'message': f'Connecté à {port}'
                    })
                time.sleep(0.5)
            
            print(f"Timeout connexion: {id_connexion}")
            
            # Log d'échec
            audit_logger.log(
                event_type='ARDUINO_CONNECT_FAILURE',
                user_id=current_user_id,
                connection_id=id_connexion,
                details=f"Timeout de connexion au port {port}",
                ip_address=request.remote_addr
            )
            
            return jsonify({
                'success': False, 
                'message': f'Timeout - Impossible de se connecter à {port}'
            })
            
        except Exception as e:
            print(f"❌ Erreur connexion: {e}")
            return jsonify({'success': False, 'message': f'Erreur: {str(e)}'})
    
    # -----------------------------------------------
    # Routes avec vérification de propriété utilisateur
    # -----------------------------------------------
    
    @app.route('/api/control_monitoring', methods=['POST'])
    @login_required
    @connection_ownership_required
    def control_monitoring():
        """API pour démarrer/arrêter le monitoring"""
        try:
            donnees = request.json
            id_connexion = donnees.get('connection_id')
            action = donnees.get('action')
            
            if id_connexion and id_connexion in arduino_controller.connexions_arduino:
                if action == 'stop':
                    arduino_controller.connexions_arduino[id_connexion]['surveillance_active'] = False
                    
                    if 'pi_controller' in arduino_controller.connexions_arduino[id_connexion]:
                        arduino_controller.connexions_arduino[id_connexion]['pi_controller'].reset()
                    if 'pid_controller' in arduino_controller.connexions_arduino[id_connexion]:
                        arduino_controller.connexions_arduino[id_connexion]['pid_controller'].reset()
                    
                    arduino_controller.connexions_arduino[id_connexion]['derniere_pwm_envoyee'] = 0
                    arduino_controller.connexions_arduino[id_connexion]['derniere_sortie_calculee'] = 0
                    
                    # Log d'audit
                    audit_logger.log(
                        event_type='MONITORING_STOP',
                        user_id=session.get('user_id'),
                        connection_id=id_connexion,
                        details="Monitoring arrêté",
                        ip_address=request.remote_addr
                    )
                    
                    print(f"⏸️ Monitoring arrêté pour {id_connexion}")
                    return jsonify({'success': True, 'message': 'Monitoring arrêté'})
                
                elif action == 'start':
                    arduino_controller.connexions_arduino[id_connexion]['surveillance_active'] = True
                    
                    type_controleur = arduino_controller.connexions_arduino[id_connexion]['type_controleur']
                    arduino_controller.envoyer_mode_arduino(id_connexion, type_controleur)
                    
                    if type_controleur == 'none':
                        consigne = arduino_controller.connexions_arduino[id_connexion]['consigne']
                        if arduino_controller.connexions_arduino[id_connexion]['connecte']:
                            arduino_controller.envoyer_commande_brute(id_connexion, f"SET:{consigne}\n")
                            print(f"Consigne envoyée au démarrage: {consigne}°C")
                    
                    # Log d'audit
                    audit_logger.log(
                        event_type='MONITORING_START',
                        user_id=session.get('user_id'),
                        connection_id=id_connexion,
                        details="Monitoring démarré",
                        ip_address=request.remote_addr
                    )
                    
                    print(f"▶️ Monitoring démarré pour {id_connexion}")
                    return jsonify({'success': True, 'message': 'Monitoring démarré'})
            
            return jsonify({'success': False, 'message': 'Connexion non trouvée'})
        except Exception as e:
            return jsonify({'success': False, 'message': f'Erreur: {str(e)}'})
    
    @app.route('/api/set_controller_mode', methods=['POST'])
    @login_required
    @connection_ownership_required
    def set_controller_mode():
        """API pour définir le type de contrôleur"""
        try:
            donnees = request.json
            id_connexion = donnees.get('connection_id')
            type_controleur = donnees.get('controller_type')
            
            if not id_connexion:
                return jsonify({'success': False, 'message': 'ID de connexion manquant'})
                
            if not type_controleur:
                return jsonify({'success': False, 'message': 'Type de contrôleur manquant'})
            
            if id_connexion in arduino_controller.connexions_arduino:
                ancien_type = arduino_controller.connexions_arduino[id_connexion].get('type_controleur', 'none')
                arduino_controller.connexions_arduino[id_connexion]['type_controleur'] = type_controleur
                
                arduino_controller.envoyer_mode_arduino(id_connexion, type_controleur)
                
                if 'pi_controller' in arduino_controller.connexions_arduino[id_connexion]:
                    arduino_controller.connexions_arduino[id_connexion]['pi_controller'].reset()
                if 'pid_controller' in arduino_controller.connexions_arduino[id_connexion]:
                    arduino_controller.connexions_arduino[id_connexion]['pid_controller'].reset()
                
                arduino_controller.connexions_arduino[id_connexion]['derniere_pwm_envoyee'] = 0
                arduino_controller.connexions_arduino[id_connexion]['derniere_sortie_calculee'] = 0
                
                # Log d'audit
                audit_logger.log(
                    event_type='CONTROLLER_MODE_CHANGE',
                    user_id=session.get('user_id'),
                    connection_id=id_connexion,
                    details=f"Mode contrôleur changé: {ancien_type} → {type_controleur}",
                    ip_address=request.remote_addr
                )
                
                print(f"Mode contrôleur changé: {ancien_type} -> {type_controleur} pour {id_connexion}")
                
                return jsonify({'success': True, 'message': f'Mode contrôleur défini: {type_controleur}'})
            
            return jsonify({'success': False, 'message': 'Connexion non trouvée'})
        except Exception as e:
            print(f"❌ Erreur définition mode contrôleur: {e}")
            return jsonify({'success': False, 'message': f'Erreur: {str(e)}'})
    
    @app.route('/api/set_controller_params', methods=['POST'])
    @login_required
    @connection_ownership_required
    def set_controller_params():
        """API pour définir les paramètres du contrôleur"""
        try:
            donnees = request.json
            id_connexion = donnees.get('connection_id')
            controller_type = donnees.get('controller_type')
            parameters = donnees.get('parameters')
            
            if not id_connexion:
                return jsonify({'success': False, 'message': 'ID de connexion manquant'})
                
            if not controller_type:
                return jsonify({'success': False, 'message': 'Type de contrôleur manquant'})
                
            if not parameters:
                return jsonify({'success': False, 'message': 'Paramètres manquants'})
            
            if id_connexion in arduino_controller.connexions_arduino:
                if controller_type == 'pi' and 'pi_controller' in arduino_controller.connexions_arduino[id_connexion]:
                    controller = arduino_controller.connexions_arduino[id_connexion]['pi_controller']
                    controller.kp = parameters.get('kp', 2.0)
                    controller.ki = parameters.get('ki', 0.2)
                    print(f"Paramètres PI mis à jour: Kp={controller.kp}, Ki={controller.ki}")
                    
                elif controller_type == 'pid' and 'pid_controller' in arduino_controller.connexions_arduino[id_connexion]:
                    controller = arduino_controller.connexions_arduino[id_connexion]['pid_controller']
                    controller.kp = parameters.get('kp', 2.0)
                    controller.ki = parameters.get('ki', 0.2)
                    controller.kd = parameters.get('kd', 0.1)
                    print(f"Paramètres PID mis à jour: Kp={controller.kp}, Ki={controller.ki}, Kd={controller.kd}")
                
                if 'parametres' not in arduino_controller.connexions_arduino[id_connexion]:
                    arduino_controller.connexions_arduino[id_connexion]['parametres'] = {}
                
                arduino_controller.connexions_arduino[id_connexion]['parametres'][controller_type] = parameters
                
                # Log d'audit
                audit_logger.log(
                    event_type='CONTROLLER_PARAMS_CHANGE',
                    user_id=session.get('user_id'),
                    connection_id=id_connexion,
                    details=f"Paramètres {controller_type} mis à jour: {parameters}",
                    ip_address=request.remote_addr
                )
                
                return jsonify({'success': True, 'message': f'Paramètres du contrôleur {controller_type} définis'})
            
            return jsonify({'success': False, 'message': 'Connexion non trouvée'})
        except Exception as e:
            print(f"❌ Erreur définition paramètres contrôleur: {e}")
            return jsonify({'success': False, 'message': f'Erreur: {str(e)}'})
    
    @app.route('/api/update_consigne', methods=['POST'])
    @login_required
    @connection_ownership_required
    def update_consigne():
        """API pour mettre à jour la consigne"""
        try:
            donnees = request.json
            id_connexion = donnees.get('connection_id')
            consigne = donnees.get('consigne')
            type_controleur = donnees.get('controller_type', 'none')
            
            if not id_connexion:
                return jsonify({'success': False, 'message': 'ID de connexion manquant'})
                
            if not consigne:
                return jsonify({'success': False, 'message': 'Consigne manquante'})
            
            consigne_numerique = float(consigne)
            if consigne_numerique < 0 or consigne_numerique > 100:
                return jsonify({'success': False, 'message': 'Consigne doit être entre 0 et 100°C'})
            
            if id_connexion in arduino_controller.connexions_arduino:
                ancienne_consigne = arduino_controller.connexions_arduino[id_connexion]['consigne']
                
                arduino_controller.connexions_arduino[id_connexion]['consigne'] = consigne_numerique
                arduino_controller.connexions_arduino[id_connexion]['donnees']['consigne'] = consigne_numerique
                
                if 'pi_controller' in arduino_controller.connexions_arduino[id_connexion]:
                    controller = arduino_controller.connexions_arduino[id_connexion]['pi_controller']
                    controller.setpoint = consigne_numerique
                    controller.reset()
                    print(f"🔄 Contrôleur PI réinitialisé avec consigne: {consigne_numerique}°C")
                    
                if 'pid_controller' in arduino_controller.connexions_arduino[id_connexion]:
                    controller = arduino_controller.connexions_arduino[id_connexion]['pid_controller']
                    controller.setpoint = consigne_numerique
                    controller.reset()
                    print(f"🔄 Contrôleur PID réinitialisé avec consigne: {consigne_numerique}°C")
                
                arduino_controller.connexions_arduino[id_connexion]['derniere_sortie_calculee'] = 0
                
                if type_controleur == 'none' and arduino_controller.connexions_arduino[id_connexion]['connecte']:
                    arduino_controller.envoyer_commande_brute(id_connexion, f"SET:{consigne_numerique}\n")
                    print(f"Consigne envoyée à Arduino: {consigne_numerique}°C")
                
                # Log d'audit
                audit_logger.log(
                    event_type='SETPOINT_CHANGE',
                    user_id=session.get('user_id'),
                    connection_id=id_connexion,
                    details=f"Consigne changée: {ancienne_consigne} → {consigne_numerique}°C",
                    ip_address=request.remote_addr
                )
                
                print(f"Consigne mise à jour: {consigne}°C (Mode: {type_controleur}) pour {id_connexion}")
                
                return jsonify({'success': True, 'message': f'Consigne: {consigne}°C'})
            
            return jsonify({'success': False, 'message': 'Connexion non trouvée'})
        except Exception as e:
            print(f"❌ Erreur mise à jour consigne: {e}")
            return jsonify({'success': False, 'message': f'Erreur: {str(e)}'})
    
    @app.route('/api/disconnect', methods=['POST'])
    @login_required
    @connection_ownership_required
    def disconnect_arduino():
        """API pour déconnecter un Arduino"""
        try:
            donnees = request.json
            id_connexion = donnees.get('connection_id')
            raison = donnees.get('reason', 'non spécifiée')
            print(f"🔴🔴🔴 DÉCONNEXION DEMANDÉE - Connexion: {id_connexion} - RAISON: {raison} 🔴🔴🔴")
            
            if id_connexion and id_connexion in arduino_controller.connexions_arduino:
                if arduino_controller.connexions_arduino[id_connexion]['connecte']:
                    # Demande à l'agent local de fermer le port série (STOP + close)
                    arduino_controller.demander_fermeture_port(id_connexion)
                    time.sleep(0.5)
                
                arduino_controller.connexions_arduino[id_connexion]['connecte'] = False
                
                # Log d'audit
                audit_logger.log(
                    event_type='ARDUINO_DISCONNECT',
                    user_id=session.get('user_id'),
                    connection_id=id_connexion,
                    details="Arduino déconnecté",
                    ip_address=request.remote_addr
                )
                
                if id_connexion in arduino_controller.connexions_arduino:
                    del arduino_controller.connexions_arduino[id_connexion]
                
                print(f"🔌 Déconnexion réussie: {id_connexion}")
                return jsonify({'success': True, 'message': 'Déconnecté'})
            
            return jsonify({'success': False, 'message': 'Connexion non trouvée'})
        except Exception as e:
            print(f"❌ Erreur déconnexion: {e}")
            return jsonify({'success': False, 'message': f'Erreur: {str(e)}'})
    
    # -----------------------------------------------
    # Routes d'audit et de gestion
    # -----------------------------------------------
    
    @app.route('/api/user_audit_logs')
    @login_required
    def get_user_audit_logs():
        """API pour obtenir les logs d'audit de l'utilisateur"""
        try:
            user_id = session.get('user_id')
            limit = int(request.args.get('limit', 50))
            
            user_logs = audit_logger.get_user_logs(user_id, limit)
            
            return jsonify({
                'success': True,
                'logs': user_logs,
                'count': len(user_logs)
            })
            
        except Exception as e:
            print(f"❌ Erreur récupération logs audit: {e}")
            return jsonify({'success': False, 'message': f'Erreur: {str(e)}'})
    
    @app.route('/api/cleanup_user_connections', methods=['POST'])
    @login_required
    def cleanup_user_connections():
        """API pour nettoyer les connexions inactives de l'utilisateur"""
        try:
            user_id = session.get('user_id')
            current_time = time.time()
            cleaned = 0
            
            for id_connexion, connexion in list(arduino_controller.connexions_arduino.items()):
                if connexion.get('user_id') == user_id:
                    last_activity = connexion.get('last_activity', 0)
                    if current_time - last_activity > 1800:  # 30 minutes
                        # Marquer comme inactive
                        connexion['connecte'] = False
                        cleaned += 1
                        
                        # Log d'audit
                        audit_logger.log(
                            event_type='CONNECTION_CLEANUP',
                            user_id=user_id,
                            connection_id=id_connexion,
                            details="Connexion nettoyée manuellement (inactive > 30min)",
                            ip_address=request.remote_addr
                        )
            
            return jsonify({
                'success': True,
                'message': f'{cleaned} connexion(s) nettoyée(s)',
                'cleaned_count': cleaned
            })
            
        except Exception as e:
            print(f"❌ Erreur nettoyage connexions: {e}")
            return jsonify({'success': False, 'message': f'Erreur: {str(e)}'})
    
    # -----------------------------------------------
    # Routes de données (lecture seule - pas besoin de vérification de propriété)
    # -----------------------------------------------
    
    @app.route('/api/data')
    @login_required
    def get_data():
        """API pour récupérer les données de l'Arduino connecté"""
        try:
            id_connexion = request.args.get('connection_id')
            
            if id_connexion and id_connexion in arduino_controller.connexions_arduino:
                data = arduino_controller.connexions_arduino[id_connexion]['donnees'].copy()
                
                if 'controller_data' in arduino_controller.connexions_arduino[id_connexion] and arduino_controller.connexions_arduino[id_connexion]['controller_data']:
                    data['controller_data'] = arduino_controller.connexions_arduino[id_connexion]['controller_data']
                
                return jsonify(data)
            else:
                print(f"⚠️ /api/data: connexion '{id_connexion}' introuvable dans connexions_arduino (clés actuelles: {list(arduino_controller.connexions_arduino.keys())}) -> valeurs par défaut renvoyées")
                return jsonify({
                    'temperature': 0.0,
                    'consigne': 25.0, 
                    'timestamp': time.time()
                })
        except Exception as e:
            print(f"❌ Erreur récupération données: {e}")
            return jsonify({'temperature': 0, 'consigne': 25, 'timestamp': time.time()})
    
    @app.route('/api/historical_data')
    @login_required
    def get_historical_data():
        """API pour récupérer les données historiques"""
        try:
            id_connexion = request.args.get('connection_id')
            limit = int(request.args.get('limit', 100))
            
            if not id_connexion:
                return jsonify({'labels': [], 'temperatures': [], 'consignes': []})
            
            if id_connexion in arduino_controller.donnees_temps_reel and arduino_controller.donnees_temps_reel[id_connexion]:
                donnees = arduino_controller.donnees_temps_reel[id_connexion]
                
                donnees_limitees = donnees[-limit:]
                
                labels = []
                temperatures = []
                consignes = []
                errors = []
                outputs = []
                
                for donnee in donnees_limitees:
                    dt = datetime.fromtimestamp(donnee['timestamp'])
                    labels.append(dt.strftime('%H:%M:%S'))
                    temperatures.append(donnee['temperature'])
                    consignes.append(donnee['consigne'])
                    
                    if donnee.get('controller_data'):
                        errors.append(donnee['controller_data'].get('error', 0))
                        outputs.append(donnee['controller_data'].get('output', 0))
                    else:
                        errors.append(0)
                        outputs.append(0)
                
                print(f"Données historiques envoyées: {len(labels)} points pour {id_connexion}")
                return jsonify({
                    'labels': labels,
                    'temperatures': temperatures,
                    'consignes': consignes,
                    'errors': errors,
                    'outputs': outputs
                })
            
            elif id_connexion in arduino_controller.connexions_arduino:
                connexion = arduino_controller.connexions_arduino[id_connexion]
                if 'donnees' in connexion and connexion['donnees']:
                    donnee = connexion['donnees']
                    dt = datetime.fromtimestamp(donnee['timestamp'])
                    
                    error = 0
                    output = 0
                    
                    if 'controller_data' in connexion and connexion['controller_data']:
                        error = connexion['controller_data'].get('error', 0)
                        output = connexion['controller_data'].get('output', 0)
                    
                    return jsonify({
                        'labels': [dt.strftime('%H:%M:%S')],
                        'temperatures': [donnee['temperature']],
                        'consignes': [donnee['consigne']],
                        'errors': [error],
                        'outputs': [output]
                    })
            
            return jsonify({
                'labels': [], 
                'temperatures': [], 
                'consignes': [],
                'errors': [],
                'outputs': []
            })
            
        except Exception as e:
            print(f"❌ Erreur récupération données historiques: {e}")
            return jsonify({
                'labels': [], 
                'temperatures': [], 
                'consignes': [],
                'errors': [],
                'outputs': []
            })
    
    @app.route('/api/control_data')
    @login_required
    def get_control_data():
        """API pour obtenir les données de contrôle"""
        try:
            id_connexion = request.args.get('connection_id')
            limit = int(request.args.get('limit', 100))
            
            if not id_connexion or id_connexion not in arduino_controller.donnees_controle:
                return jsonify({'labels': [], 'errors': [], 'p_terms': [], 'i_terms': [], 'd_terms': [], 'outputs': []})
            
            donnees = arduino_controller.donnees_controle[id_connexion]
            
            donnees_limitees = donnees[-limit:]
            
            labels = []
            errors = []
            p_terms = []
            i_terms = []
            d_terms = []
            outputs = []
            
            for donnee in donnees_limitees:
                dt = datetime.fromtimestamp(donnee['timestamp'])
                labels.append(dt.strftime('%H:%M:%S'))
                errors.append(donnee['error'])
                p_terms.append(donnee['p_term'])
                i_terms.append(donnee['i_term'])
                d_terms.append(donnee['d_term'])
                outputs.append(donnee['output'])
            
            return jsonify({
                'labels': labels,
                'errors': errors,
                'p_terms': p_terms,
                'i_terms': i_terms,
                'd_terms': d_terms,
                'outputs': outputs
            })
            
        except Exception as e:
            print(f"❌ Erreur récupération données contrôle: {e}")
            return jsonify({'labels': [], 'errors': [], 'p_terms': [], 'i_terms': [], 'd_terms': [], 'outputs': []})
    
    @app.route('/api/request_temp', methods=['POST'])
    @login_required
    @connection_ownership_required
    def request_temp():
        """API pour demander une lecture de température manuelle"""
        try:
            donnees = request.json
            id_connexion = donnees.get('connection_id')
            
            if id_connexion and id_connexion in arduino_controller.connexions_arduino:
                if arduino_controller.connexions_arduino[id_connexion]['connecte']:
                    arduino_controller.envoyer_commande_brute(id_connexion, "TEMP\n")
                    
                    # Log d'audit
                    audit_logger.log(
                        event_type='MANUAL_TEMP_REQUEST',
                        user_id=session.get('user_id'),
                        connection_id=id_connexion,
                        details="Demande manuelle de température",
                        ip_address=request.remote_addr
                    )
                    
                    return jsonify({'success': True, 'message': 'Demande de température envoyée'})
            
            return jsonify({'success': False, 'message': 'Connexion non trouvée'})
        except Exception as e:
            print(f"❌ Erreur demande température: {e}")
            return jsonify({'success': False, 'message': f'Erreur: {str(e)}'})
    
    @app.route('/api/export_data', methods=['POST'])
    @login_required
    @connection_ownership_required
    def export_data():
        """API pour exporter les données en CSV"""
        try:
            donnees = request.json
            id_connexion = donnees.get('connection_id')
            export_type = donnees.get('export_type', 'complet')
            
            if not id_connexion:
                return jsonify({'success': False, 'message': 'ID de connexion manquant'})

            if export_type == 'complet' and id_connexion in arduino_controller.donnees_temps_reel and arduino_controller.donnees_temps_reel[id_connexion]:
                # Export COMPLET
                output = exporter_donnees_csv(arduino_controller.donnees_temps_reel[id_connexion], 'complet')
                
                # Log d'audit
                audit_logger.log(
                    event_type='DATA_EXPORT',
                    user_id=session.get('user_id'),
                    connection_id=id_connexion,
                    details=f"Export complet des données ({len(arduino_controller.donnees_temps_reel[id_connexion])} points)",
                    ip_address=request.remote_addr
                )
                
                print(f"✅ Export complet réussi: {len(arduino_controller.donnees_temps_reel[id_connexion])} points exportés pour {id_connexion}")
                
            else:
                # Export RÉSUMÉ
                if id_connexion in arduino_controller.connexions_arduino and arduino_controller.connexions_arduino[id_connexion]:
                    connexion = arduino_controller.connexions_arduino[id_connexion]
                    donnees_actuelles = connexion.get('donnees', {})
                    
                    if not donnees_actuelles:
                        return jsonify({'success': False, 'message': 'Aucune donnée disponible pour l\'export'})
                    
                    # Préparer les données pour l'export
                    export_data = [{
                        'timestamp': donnees_actuelles.get('timestamp', time.time()),
                        'temperature': donnees_actuelles.get('temperature', 0),
                        'consigne': donnees_actuelles.get('consigne', 0),
                        'valeur_pwm': 0,
                        'type_controleur': connexion.get('type_controleur', 'aucun'),
                        'surveillance_active': connexion.get('surveillance_active', False),
                        'controller_data': connexion.get('controller_data', {}),
                        'kp': 0,
                        'ki': 0,
                        'kd': 0
                    }]
                    
                    output = exporter_donnees_csv(export_data, 'resume')
                    
                    # Log d'audit
                    audit_logger.log(
                        event_type='DATA_EXPORT',
                        user_id=session.get('user_id'),
                        connection_id=id_connexion,
                        details="Export résumé des données",
                        ip_address=request.remote_addr
                    )
                    
                    print(f"✅ Export résumé réussi pour {id_connexion}")
                else:
                    return jsonify({'success': False, 'message': 'Aucune donnée disponible pour l\'export'})
            
            date_export = datetime.now().strftime('%Y%m%d_%H%M%S')
            type_label = 'complet' if export_type == 'complet' else 'resume'
            filename = f"donnees_temperature_{type_label}_{date_export}.csv"
            
            return creer_reponse_csv(output, filename)
            
        except Exception as e:
            print(f"❌ Erreur export données: {e}")
            import traceback
            traceback.print_exc()
            return jsonify({'success': False, 'message': f'Erreur export: {str(e)}'})
    
    @app.route('/api/data_stats')
    @login_required
    def get_data_stats():
        """API pour obtenir les statistiques des données"""
        try:
            id_connexion = request.args.get('connection_id')
            
            if not id_connexion or id_connexion not in arduino_controller.donnees_temps_reel:
                return jsonify({'total_points': 0, 'periode': 'Aucune donnée'})
            
            donnees = arduino_controller.donnees_temps_reel[id_connexion]
            if not donnees:
                return jsonify({'total_points': 0, 'periode': 'Aucune donnée'})
            
            total_points = len(donnees)
            debut = datetime.fromtimestamp(donnees[0]['timestamp']).strftime('%Y-%m-%d %H:%M:%S')
            fin = datetime.fromtimestamp(donnees[-1]['timestamp']).strftime('%Y-%m-%d %H:%M:%S')
            periode = f"De {debut} à {fin}"
            
            return jsonify({
                'total_points': total_points,
                'periode': periode,
                'dernier_enregistrement': fin
            })
            
        except Exception as e:
            print(f"❌ Erreur statistiques données: {e}")
            return jsonify({'total_points': 0, 'periode': 'Erreur'})
    
    @app.route('/api/debug_data')
    @login_required
    def debug_data():
        """Route de debug pour vérifier les données"""
        try:
            id_connexion = request.args.get('connection_id')
            
            if not id_connexion:
                return jsonify({'error': 'ID de connexion manquant'})
            
            stats_temps_reel = {}
            stats_historique = {}
            stats_controle = {}
            
            if id_connexion in arduino_controller.donnees_temps_reel:
                stats_temps_reel = {
                    'total_points': len(arduino_controller.donnees_temps_reel[id_connexion]),
                    'dernier_point': arduino_controller.donnees_temps_reel[id_connexion][-1] if arduino_controller.donnees_temps_reel[id_connexion] else 'Aucun'
                }
            
            if id_connexion in arduino_controller.historique_detaille:
                stats_historique = {
                    'total_evenements': len(arduino_controller.historique_detaille[id_connexion]),
                    'dernier_evenement': arduino_controller.historique_detaille[id_connexion][-1] if arduino_controller.historique_detaille[id_connexion] else 'Aucun'
                }
            
            if id_connexion in arduino_controller.donnees_controle:
                stats_controle = {
                    'total_points_controle': len(arduino_controller.donnees_controle[id_connexion]),
                    'dernier_point_controle': arduino_controller.donnees_controle[id_connexion][-1] if arduino_controller.donnees_controle[id_connexion] else 'Aucun'
                }
            
            return jsonify({
                'donnees_temps_reel': stats_temps_reel,
                'historique_evenements': stats_historique,
                'donnees_controle': stats_controle,
                'connexions_actives': list(arduino_controller.connexions_arduino.keys())
            })
            
        except Exception as e:
            return jsonify({'error': str(e)})
    
    @app.route('/api/debug_controller/<id_connexion>')
    @login_required
    def debug_controller(id_connexion):
        """Debug des contrôleurs"""
        from flask import current_app
        
        arduino_controller = current_app.config.get('arduino_controller')
        if not arduino_controller:
            return jsonify({'error': 'Contrôleur Arduino non disponible'})
            
        if id_connexion in arduino_controller.connexions_arduino:
            connexion = arduino_controller.connexions_arduino[id_connexion]
            
            # Vérification de propriété
            current_user_id = session.get('user_id')
            connection_user_id = connexion.get('user_id')
            
            if current_user_id != connection_user_id:
                return jsonify({'error': 'Accès non autorisé à cette connexion'})
            
            return jsonify({
                'type_controleur': connexion.get('type_controleur'),
                'consigne': connexion.get('consigne'),
                'temperature': connexion['donnees'].get('temperature'),
                'pi_controller_exists': 'pi_controller' in connexion,
                'pid_controller_exists': 'pid_controller' in connexion,
                'controller_data': connexion.get('controller_data'),
                'derniere_sortie_calculee': connexion.get('derniere_sortie_calculee', 0),
                'derniere_pwm_envoyee': connexion.get('derniere_pwm_envoyee', 0),
                'user_id': connexion.get('user_id'),
                'last_activity': connexion.get('last_activity', 0)
            })
        return jsonify({'error': 'Connexion non trouvée'})
    
    @app.route('/api/health')
    def health_check():
        """API pour vérifier la santé du serveur"""
        return jsonify({'status': 'healthy', 'timestamp': time.time()})
    
    # -----------------------------------------------
    # Route pour vérifier les connexions actives de l'utilisateur
    # -----------------------------------------------
    
    @app.route('/api/user_connections')
    @login_required
    def get_user_connections():
        """API pour obtenir les connexions actives de l'utilisateur"""
        try:
            from flask import current_app
            
            user_id = session.get('user_id')
            arduino_controller = current_app.config.get('arduino_controller')
            
            if not arduino_controller:
                return jsonify({'success': False, 'message': 'Contrôleur Arduino non disponible'})
            
            user_connections = []
            
            for id_connexion, connexion in arduino_controller.connexions_arduino.items():
                if connexion.get('user_id') == user_id and connexion.get('connecte'):
                    user_connections.append({
                        'id': id_connexion,
                        'port': connexion.get('port'),
                        'type_controleur': connexion.get('type_controleur'),
                        'surveillance_active': connexion.get('surveillance_active'),
                        'last_activity': connexion.get('last_activity'),
                        'temperature': connexion.get('donnees', {}).get('temperature', 0),
                        'consigne': connexion.get('donnees', {}).get('consigne', 0)
                    })
            
            return jsonify({
                'success': True,
                'connections': user_connections,
                'count': len(user_connections)
            })
            
        except Exception as e:
            print(f"❌ Erreur récupération connexions utilisateur: {e}")
            return jsonify({'success': False, 'message': f'Erreur: {str(e)}'})