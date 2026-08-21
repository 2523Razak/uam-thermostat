# controllers/arduino_controller.py

import threading
import time
from datetime import datetime
import json
from flask import request
from controllers.pid_controller import PIController, PIDController
from utils.log_bus import log_bus

# Durée après laquelle un agent est considéré hors-ligne s'il n'a pas donné
AGENT_TIMEOUT = 45

# Durée après laquelle une connexion Arduino est considérée perdue si aucune
DONNEES_TIMEOUT = 30


class ArduinoController:
    def __init__(self, app, socketio=None):
        self.app = app
        self.socketio = socketio

        # États des connexions "logiques" Arduino
        self.connexions_arduino = {}
        self.donnees_temps_reel = {}
        self.historique_detaille = {}
        self.donnees_controle = {}

        # --- suivi des agents locaux connectés ---
        # agents[agent_id] = {'sid': ..., 'derniere_activite': ts, 'ports': [...]}
        self.agents = {}
        self.sid_vers_agent = {}          # sid Socket.IO -> agent_id
        self.port_vers_agent = {}         # nom de port -> agent_id qui l'a signalé

        self.demarrer_verification_connexions()

    # ========================================================================
    # GESTION DES AGENTS LOCAUX (connexion Socket.IO namespace /agent)
    # ========================================================================

    def register_agent(self, agent_id, sid):
        """Enregistre un agent. Retourne True si c'est une connexion 'nouvelle'
        du point de vue du serveur (agent jamais vu, ou serveur redémarré et
        ayant perdu toute trace de lui) - utilisé pour demander à l'agent de
        libérer d'éventuels ports orphelins qu'il aurait gardés ouverts."""
        nouveau = agent_id not in self.agents
        self.agents[agent_id] = {
            'sid': sid,
            'derniere_activite': time.time(),
            'connecte_depuis': self.agents.get(agent_id, {}).get('connecte_depuis', time.time()),
            'ports': self.agents.get(agent_id, {}).get('ports', []),
        }
        self.sid_vers_agent[sid] = agent_id
        if nouveau:
            log_bus.info('agent', f"Nouvel agent connecté : {agent_id}")
        else:
            log_bus.info('agent', f"Agent reconnecté : {agent_id}")
        return nouveau

    def unregister_agent_by_sid(self, sid):

        agent_id = self.sid_vers_agent.pop(sid, None)
        if not agent_id:
            return None

        agent_info = self.agents.get(agent_id)
        if not agent_info or agent_info.get('sid') != sid:
            log_bus.info('agent', f"Déconnexion tardive ignorée pour {agent_id} (agent déjà reconnecté)")
            return agent_id

        del self.agents[agent_id]
        log_bus.warning('agent', f"Agent déconnecté : {agent_id}")

        for id_connexion, connexion in self.connexions_arduino.items():
            if connexion.get('agent_id') == agent_id and connexion.get('connecte'):
                connexion['connecte'] = False
                log_bus.warning('arduino', f"Connexion {id_connexion} coupée (agent {agent_id} hors-ligne)")

        for port, aid in list(self.port_vers_agent.items()):
            if aid == agent_id:
                del self.port_vers_agent[port]
        return agent_id

    def touch_agent(self, agent_id):
        if agent_id in self.agents:
            self.agents[agent_id]['derniere_activite'] = time.time()

    def set_agent_ports(self, agent_id, ports):
        """Reçoit la liste des ports Arduino détectés par un agent (rafraîchie périodiquement)"""
        if agent_id not in self.agents:
            self.agents[agent_id] = {'sid': None, 'derniere_activite': time.time(), 'connecte_depuis': time.time(), 'ports': []}
        self.agents[agent_id]['ports'] = ports
        self.agents[agent_id]['derniere_activite'] = time.time()
        for p in ports:
            self.port_vers_agent[p['port']] = agent_id

    def get_agents_status(self):
        """Utilisé par la page d'administration /admin/logs"""
        maintenant = time.time()
        resultat = []
        for agent_id, info in self.agents.items():
            en_ligne = (maintenant - info['derniere_activite']) < AGENT_TIMEOUT
            resultat.append({
                'agent_id': agent_id,
                'en_ligne': en_ligne,
                'derniere_activite': info['derniere_activite'],
                'secondes_depuis_activite': round(maintenant - info['derniere_activite'], 1),
                'connecte_depuis': info.get('connecte_depuis'),
                'nombre_ports': len(info.get('ports', [])),
                'ports': info.get('ports', []),
            })
        return resultat

    # ========================================================================
    # OUVERTURE / FERMETURE DE CONNEXION (demandée à l'agent)
    # ========================================================================

    def lire_donnees_arduino(self, port, id_connexion, user_id=None, user_email=None):
        
        agent_id = self.port_vers_agent.get(port)

        if not agent_id or agent_id not in self.agents:
            log_bus.error('arduino', f"Impossible de connecter {port} : aucun agent local ne signale ce port")
            return

        consigne_actuelle = 25.0
        pi_controller = PIController(kp=1.0, ki=0.1, setpoint=consigne_actuelle)
        pid_controller = PIDController(kp=1.0, ki=0.1, kd=0.05, setpoint=consigne_actuelle)

        self.connexions_arduino[id_connexion] = {
            'agent_id': agent_id,
            'connecte': False,  # passera à True dès confirmation de l'agent
            'user_id': user_id,
            'user_email': user_email,
            'surveillance_active': True,
            'donnees': {'temperature': 0.0, 'consigne': consigne_actuelle, 'timestamp': time.time()},
            'consigne': consigne_actuelle,
            'type_controleur': 'none',
            'port': port,
            'pi_controller': pi_controller,
            'pid_controller': pid_controller,
            'controller_data': None,
            'derniere_pwm_envoyee': 0,
            'dernier_mode_envoye': 'none',
            'derniere_sortie_calculee': 0,
            'controller_state': {
                'last_error': 0,
                'integral_state': 0,
                'last_time': time.time(),
                'state_history': []
            },
            'custom_code_type': 'pi',
            'last_activity': time.time(),
            'derniere_donnee_recue': time.time(),
        }

        log_bus.info('arduino', f"Demande d'ouverture envoyée à l'agent {agent_id} pour {port} ({id_connexion})")

        if self.socketio:
            self.socketio.emit(
                'server:open_port',
                {'connection_id': id_connexion, 'port': port},
                room=agent_id,
                namespace='/agent'
            )

    def demander_fermeture_port(self, id_connexion):
        """Remplace l'ancien 'port_serie.write(b"STOP\\n"); port_serie.close()' des routes."""
        connexion = self.connexions_arduino.get(id_connexion)
        if not connexion:
            return

        agent_id = connexion.get('agent_id')
        if agent_id and self.socketio:
            self.socketio.emit(
                'server:close_port',
                {'connection_id': id_connexion},
                room=agent_id,
                namespace='/agent'
            )
        log_bus.info('arduino', f"Demande de fermeture envoyée pour {id_connexion}")

    def mettre_a_jour_statut_connexion(self, id_connexion, connecte, erreur=None):
        """Appelée par le hub d'agents quand l'agent confirme l'ouverture/fermeture réelle du port série."""
        if id_connexion not in self.connexions_arduino:
            return

        etait_connecte = self.connexions_arduino[id_connexion]['connecte']
        self.connexions_arduino[id_connexion]['connecte'] = connecte
        self.connexions_arduino[id_connexion]['last_activity'] = time.time()

        if connecte and not etait_connecte:
            log_bus.info('arduino', f"Connexion série confirmée par l'agent : {id_connexion}")
            self.connexions_arduino[id_connexion]['derniere_donnee_recue'] = time.time()
            self.envoyer_mode_arduino(id_connexion, 'none')
        elif not connecte and etait_connecte:
            msg = f"Connexion série perdue : {id_connexion}"
            if erreur:
                msg += f" ({erreur})"
            log_bus.warning('arduino', msg)

    # ========================================================================
    # TRAITEMENT DES LIGNES REÇUES DE L'ARDUINO (relayées par l'agent)
    # ========================================================================

    def traiter_ligne_arduino(self, id_connexion, ligne):
        
        from controllers.code_personnalise import custom_code_manager

        if id_connexion not in self.connexions_arduino:
            return

        connexion = self.connexions_arduino[id_connexion]
        if not ligne:
            return

        connexion['derniere_donnee_recue'] = time.time()

        try:
            if ligne.startswith("DATA:"):
                parts = ligne.split(":")
                if len(parts) >= 4:
                    try:
                        temperature_actuelle = float(parts[1])
                        consigne_actuelle = connexion['consigne']

                        pwm_recue = 0
                        if parts[3]:
                            try:
                                pwm_recue = int(float(parts[3]))
                            except ValueError:
                                pwm_recue = 0

                        connexion['donnees'] = {
                            "temperature": temperature_actuelle,
                            "consigne": consigne_actuelle,
                            "timestamp": time.time()
                        }

                        type_controleur = connexion['type_controleur']

                        controller_data = None
                        output = 0

                        if type_controleur in ['pi', 'pid', 'mpc', 'custom']:
                            try:
                                error = consigne_actuelle - temperature_actuelle

                                state = connexion['controller_state']
                                last_error = state.get('last_error', 0)
                                integral_state = state.get('integral_state', 0)
                                state_history = state.get('state_history', [])

                                dt = time.time() - state.get('last_time', time.time() - 1)

                                inputs = {
                                    'error': error,
                                    'dt': dt,
                                    'last_error': last_error,
                                    'integral_state': integral_state,
                                    'state_history': state_history[-10:] if state_history else []
                                }

                                code_type_to_execute = type_controleur
                                if type_controleur == 'custom':
                                    code_type_to_execute = connexion.get('custom_code_type', 'pi')

                                conn_user_id = connexion.get('user_id', 'default')

                                result, metadata = custom_code_manager.execute_control_code(
                                    user_id=conn_user_id,
                                    connection_id=id_connexion,
                                    code_type=code_type_to_execute,
                                    **inputs
                                )

                                if isinstance(result, tuple):
                                    output = result[0]
                                    if len(result) > 1:
                                        integral_state = result[1]
                                else:
                                    output = result

                                state['last_error'] = error
                                state['integral_state'] = integral_state
                                state['last_time'] = time.time()

                                state_history.append({
                                    'timestamp': time.time(),
                                    'temperature': temperature_actuelle,
                                    'consigne': consigne_actuelle,
                                    'error': error,
                                    'output': output
                                })

                                if len(state_history) > 100:
                                    state_history = state_history[-100:]

                                state['state_history'] = state_history

                                controller_data = {
                                    'error': error,
                                    'output': output,
                                    'type': type_controleur,
                                    'source': metadata.get('source', 'default'),
                                    'is_custom': metadata.get('source') == 'user'
                                }

                                for terme in ('p_term', 'i_term', 'd_term'):
                                    if terme in metadata:
                                        controller_data[terme] = metadata[terme]

                            except Exception as e:
                                log_bus.error('controle', f"Erreur exécution contrôleur {type_controleur} pour {id_connexion} : {e}")
                                pi_controller = connexion['pi_controller']
                                pid_controller = connexion['pid_controller']
                                if type_controleur == 'pi':
                                    output = pi_controller.update(temperature_actuelle)
                                    controller_data = {
                                        'error': pi_controller.error, 'p_term': pi_controller.p_term,
                                        'i_term': pi_controller.i_term, 'output': output,
                                        'type': 'pi', 'source': 'default_fallback'
                                    }
                                elif type_controleur == 'pid':
                                    output = pid_controller.update(temperature_actuelle)
                                    controller_data = {
                                        'error': pid_controller.error, 'p_term': pid_controller.p_term,
                                        'i_term': pid_controller.i_term, 'd_term': pid_controller.d_term,
                                        'output': output, 'type': 'pid', 'source': 'default_fallback'
                                    }
                                else:
                                    output = 0
                                    controller_data = None
                        else:
                            output = 0
                            controller_data = None
                            self.envoyer_commande_brute(id_connexion, f"SET:{consigne_actuelle}\n")

                        if type_controleur in ['pi', 'pid', 'mpc', 'custom'] and output is not None and output > 0:
                            derniere_sortie = connexion.get('derniere_sortie_calculee', 0)
                            if abs(output - derniere_sortie) > 1 or derniere_sortie == 0:
                                if self.envoyer_commande_pwm_arduino(id_connexion, output):
                                    connexion['derniere_sortie_calculee'] = output

                        connexion['controller_data'] = controller_data

                        self.enregistrer_donnees_temps_reel(
                            id_connexion, temperature_actuelle, consigne_actuelle,
                            type_controleur, connexion['surveillance_active'], controller_data
                        )

                    except (ValueError, IndexError) as e:
                        log_bus.error('arduino', f"Erreur analyse ligne DATA ({id_connexion}) : {e} - Ligne: {ligne}")

            elif ligne.startswith("STATUS:"):
                pass  # information seulement, rien à faire côté serveur
            elif "ALERTE" in ligne:
                log_bus.warning('arduino', f"ALERTE : {ligne} ({id_connexion})")
            # PONG, "PWM recue:", "Mode defini:", "Consigne definie:", "Temperature:"
            # sont des accusés de réception : ils sont gérés localement par
            # l'agent (voir agent_local/agent_arduino.py) qui ne les relaie
            # pas tous pour ne pas saturer la liaison Internet.

        except Exception as e:
            log_bus.error('arduino', f"Erreur traitement ligne ({id_connexion}) : {e}")

    # ========================================================================
    # ENVOI DE COMMANDES 
    # ========================================================================

    def envoyer_commande_brute(self, id_connexion, commande):
        """
        Envoie une commande texte brute (ex: "SET:25.0\\n", "STOP\\n", "TEMP\\n")
        à la carte Arduino via l'agent local qui gère cette connexion.
        """
        connexion = self.connexions_arduino.get(id_connexion)
        if not connexion or not connexion.get('connecte'):
            return False

        agent_id = connexion.get('agent_id')
        if not agent_id or not self.socketio:
            return False

        self.socketio.emit(
            'server:command',
            {'connection_id': id_connexion, 'command': commande},
            room=agent_id,
            namespace='/agent'
        )
        return True

    def envoyer_commande_pwm_arduino(self, id_connexion, output):
        """Envoie une commande PWM à l'Arduino (output attendu entre 0 et 100)"""
        try:
            pwm_value = int((output / 100) * 255)
            pwm_value = max(0, min(255, pwm_value))
            commande = f"PWM:{pwm_value}\n"

            if self.envoyer_commande_brute(id_connexion, commande):
                self.connexions_arduino[id_connexion]['derniere_pwm_envoyee'] = pwm_value
                return True
        except Exception as e:
            log_bus.error('arduino', f"Erreur envoi PWM ({id_connexion}) : {e}")
        return False

    def envoyer_mode_arduino(self, id_connexion, mode):
        """Envoie le mode de contrôle à l'Arduino (ex: 'none', 'pi', 'pid', 'mpc', 'custom')"""
        try:
            commande = f"MODE:{mode}\n"
            if self.envoyer_commande_brute(id_connexion, commande):
                self.connexions_arduino[id_connexion]['dernier_mode_envoye'] = mode
                return True
        except Exception as e:
            log_bus.error('arduino', f"Erreur envoi mode ({id_connexion}) : {e}")
        return False

    # ========================================================================
    # ENREGISTREMENT DES DONNÉES / HISTORIQUE
    # ========================================================================

    def enregistrer_donnees_temps_reel(self, id_connexion, temperature, consigne, type_controleur, surveillance_active, controller_data=None):
        """Enregistre les données en temps réel dans un buffer"""
        if id_connexion not in self.donnees_temps_reel:
            self.donnees_temps_reel[id_connexion] = []

        kp, ki, kd = 0, 0, 0
        if id_connexion in self.connexions_arduino:
            actual_type = type_controleur
            if type_controleur == 'custom':
                actual_type = self.connexions_arduino[id_connexion].get('custom_code_type', 'pi')

            if actual_type == 'pi' and 'pi_controller' in self.connexions_arduino[id_connexion]:
                controller = self.connexions_arduino[id_connexion]['pi_controller']
                kp = controller.kp
                ki = controller.ki
            elif actual_type == 'pid' and 'pid_controller' in self.connexions_arduino[id_connexion]:
                controller = self.connexions_arduino[id_connexion]['pid_controller']
                kp = controller.kp
                ki = controller.ki
                kd = controller.kd

        valeur_pwm = 0
        if controller_data and 'output' in controller_data:
            valeur_pwm = int((controller_data['output'] / 100) * 255)
        else:
            valeur_pwm = int((consigne / 100) * 255)

        entree = {
            'timestamp': time.time(),
            'temperature': temperature,
            'consigne': consigne,
            'valeur_pwm': valeur_pwm,
            'type_controleur': type_controleur,
            'surveillance_active': surveillance_active,
            'controller_data': controller_data,
            'kp': kp,
            'ki': ki,
            'kd': kd,
            'consigne_controleur': consigne
        }

        self.donnees_temps_reel[id_connexion].append(entree)
        if len(self.donnees_temps_reel[id_connexion]) > 10000:
            self.donnees_temps_reel[id_connexion] = self.donnees_temps_reel[id_connexion][-10000:]

        if controller_data:
            if id_connexion not in self.donnees_controle:
                self.donnees_controle[id_connexion] = []

            controle_entree = {
                'timestamp': time.time(),
                'error': controller_data.get('error', 0),
                'p_term': controller_data.get('p_term', 0),
                'i_term': controller_data.get('i_term', 0),
                'd_term': controller_data.get('d_term', 0),
                'output': controller_data.get('output', 0),
                'type_controleur': type_controleur,
                'kp': kp,
                'ki': ki,
                'kd': kd,
                'consigne': consigne
            }

            self.donnees_controle[id_connexion].append(controle_entree)
            if len(self.donnees_controle[id_connexion]) > 5000:
                self.donnees_controle[id_connexion] = self.donnees_controle[id_connexion][-5000:]

        if id_connexion in self.connexions_arduino:
            self.connexions_arduino[id_connexion]['donnees'] = {
                "temperature": temperature,
                "consigne": consigne,
                "timestamp": time.time()
            }
            if controller_data:
                self.connexions_arduino[id_connexion]['controller_data'] = controller_data

            if 'parametres_controleur' not in self.connexions_arduino[id_connexion]:
                self.connexions_arduino[id_connexion]['parametres_controleur'] = {}

            actual_type = type_controleur
            if type_controleur == 'custom':
                actual_type = self.connexions_arduino[id_connexion].get('custom_code_type', 'pi')

            if actual_type == 'pi':
                self.connexions_arduino[id_connexion]['parametres_controleur']['pi'] = {'kp': kp, 'ki': ki}
            elif actual_type == 'pid':
                self.connexions_arduino[id_connexion]['parametres_controleur']['pid'] = {'kp': kp, 'ki': ki, 'kd': kd}

        return True

    def enregistrer_changement(self, id_connexion, type_evenement, ancienne_valeur=None, nouvelle_valeur=None):
        """Enregistre chaque changement dans l'historique (inchangé)"""
        try:
            with self.app.test_request_context():
                adresse_ip = request.remote_addr if request else 'N/A'
        except RuntimeError:
            adresse_ip = 'N/A'

        if id_connexion not in self.historique_detaille:
            self.historique_detaille[id_connexion] = []

        donnees_courantes = {}
        if id_connexion in self.connexions_arduino:
            donnees_courantes = self.connexions_arduino[id_connexion]['donnees'].copy()
            type_controleur = self.connexions_arduino[id_connexion].get('type_controleur', 'aucun')
            surveillance_active = self.connexions_arduino[id_connexion].get('surveillance_active', False)

            actual_type = type_controleur
            if type_controleur == 'custom':
                actual_type = self.connexions_arduino[id_connexion].get('custom_code_type', 'pi')

            kp, ki, kd = 0, 0, 0
            if actual_type == 'pi' and 'pi_controller' in self.connexions_arduino[id_connexion]:
                controller = self.connexions_arduino[id_connexion]['pi_controller']
                kp = controller.kp
                ki = controller.ki
            elif actual_type == 'pid' and 'pid_controller' in self.connexions_arduino[id_connexion]:
                controller = self.connexions_arduino[id_connexion]['pid_controller']
                kp = controller.kp
                ki = controller.ki
                kd = controller.kd

            parametres_sauvegardes = self.connexions_arduino[id_connexion].get('parametres_controleur', {})
            if actual_type in parametres_sauvegardes:
                params = parametres_sauvegardes[actual_type]
                kp = params.get('kp', kp)
                ki = params.get('ki', ki)
                kd = params.get('kd', kd)
        else:
            type_controleur = 'aucun'
            surveillance_active = False
            kp, ki, kd = 0, 0, 0

        temperature_courante = donnees_courantes.get('temperature', 0) if donnees_courantes else 0
        consigne_courante = donnees_courantes.get('consigne', 0) if donnees_courantes else 0

        entree = {
            'timestamp': time.time(),
            'evenement': type_evenement,
            'ancienne_valeur': ancienne_valeur,
            'nouvelle_valeur': nouvelle_valeur,
            'donnees_courantes': donnees_courantes,
            'type_controleur': type_controleur,
            'surveillance_active': surveillance_active,
            'kp': kp,
            'ki': ki,
            'kd': kd,
            'temperature': temperature_courante,
            'consigne': consigne_courante,
            'erreur': consigne_courante - temperature_courante if donnees_courantes else 0,
            'adresse_ip': adresse_ip
        }

        self.historique_detaille[id_connexion].append(entree)
        if len(self.historique_detaille[id_connexion]) > 5000:
            self.historique_detaille[id_connexion] = self.historique_detaille[id_connexion][-5000:]

        try:
            log_entry = {
                'timestamp': datetime.fromtimestamp(entree['timestamp']).strftime('%Y-%m-%d %H:%M:%S'),
                'id_connexion': id_connexion,
                'evenement': type_evenement,
                'ancienne_valeur': str(ancienne_valeur),
                'nouvelle_valeur': str(nouvelle_valeur),
                'temperature': temperature_courante,
                'consigne': consigne_courante,
                'type_controleur': type_controleur,
                'kp': kp, 'ki': ki, 'kd': kd,
                'ip': adresse_ip
            }
            log_file = f"historique_changements_{datetime.now().strftime('%Y%m')}.log"
            with open(log_file, 'a', encoding='utf-8') as f:
                f.write(json.dumps(log_entry) + '\n')
        except Exception as e:
            log_bus.error('arduino', f"Erreur écriture log historique : {e}")

        log_bus.info('arduino', f"Événement {type_evenement} ({id_connexion})")

    # ========================================================================
    # PORTS DISPONIBLES proviennent maintenant des agents, pas de pyserial local
    # ========================================================================

    def verifier_port_existe(self, nom_port):
        """Le port existe-t-il selon les dernières infos rapportées par un agent ?"""
        agent_id = self.port_vers_agent.get(nom_port)
        if not agent_id or agent_id not in self.agents:
            return False
        maintenant = time.time()
        if (maintenant - self.agents[agent_id]['derniere_activite']) > AGENT_TIMEOUT:
            return False  # agent hors-ligne : on ne peut plus garantir que le port existe
        ports_agent = [p['port'] for p in self.agents[agent_id].get('ports', [])]
        return nom_port in ports_agent

    def obtenir_ports_disponibles(self):
        """Agrège les ports Arduino détectés par tous les agents en ligne."""
        ports_trouves = []
        maintenant = time.time()

        ports_deja_connectes = set()
        for connexion in self.connexions_arduino.values():
            if connexion.get('connecte'):
                ports_deja_connectes.add(connexion.get('port'))

        for agent_id, info in self.agents.items():
            if (maintenant - info['derniere_activite']) > AGENT_TIMEOUT:
                continue  # agent hors-ligne, on ignore ses ports (obsolètes)
            for port_info in info.get('ports', []):
                physiquement_occupe = bool(port_info.get('en_utilisation'))
                ports_trouves.append({
                    'port': port_info['port'],
                    'description': port_info.get('description', ''),
                    'en_utilisation': physiquement_occupe or (port_info['port'] in ports_deja_connectes),
                    'agent_id': agent_id,
                })

        if not ports_trouves:
            log_bus.info('arduino', "Aucun Arduino détecté par les agents connectés")

        return ports_trouves

    def mettre_a_jour_disponibilite_ports(self):
        """Met à jour le statut 'en_utilisation' des ports selon les connexions actives."""
        tous_ports = self.obtenir_ports_disponibles()

        ports_utilises = []
        for connexion in self.connexions_arduino.values():
            if connexion.get('connecte'):
                ports_utilises.append(connexion.get('port'))

        for info_port in tous_ports:
            if info_port['port'] in ports_utilises:
                info_port['en_utilisation'] = True
        return tous_ports

    # ========================================================================
    # SURVEILLANCE PÉRIODIQUE DES CONNEXIONS ACTIVES
    # ========================================================================

    def verifier_connexions_actives(self):
        #Vérifie périodiquement si les connexions Arduino sont toujours actives.
        try:
            maintenant = time.time()
            connexions_a_marquer_deconnectees = []

            for id_connexion, connexion in self.connexions_arduino.items():
                if not connexion.get('connecte'):
                    continue

                agent_id = connexion.get('agent_id')
                agent_en_ligne = (
                    agent_id in self.agents and
                    (maintenant - self.agents[agent_id]['derniere_activite']) < AGENT_TIMEOUT
                )

                if not agent_en_ligne:
                    connexions_a_marquer_deconnectees.append((id_connexion, "agent local hors-ligne"))
                    continue

                derniere_donnee = connexion.get('derniere_donnee_recue', connexion.get('last_activity', maintenant))
                if (maintenant - derniere_donnee) > DONNEES_TIMEOUT:
                    connexions_a_marquer_deconnectees.append((id_connexion, "aucune donnée reçue récemment"))

            for id_connexion, raison in connexions_a_marquer_deconnectees:
                if id_connexion in self.connexions_arduino:
                    self.connexions_arduino[id_connexion]['connecte'] = False
                    log_bus.warning('arduino', f"Connexion {id_connexion} marquée inactive : {raison}")

        except Exception as e:
            log_bus.error('arduino', f"Erreur vérification connexions actives : {e}")

    def demarrer_verification_connexions(self):
        """Démarre la vérification périodique des connexions (identique à l'original)"""
        def verification_periodique():
            while True:
                try:
                    self.verifier_connexions_actives()
                    time.sleep(5)
                except Exception as e:
                    log_bus.error('arduino', f"Erreur dans la vérification périodique : {e}")
                    time.sleep(10)

        thread = threading.Thread(target=verification_periodique, daemon=True)
        thread.start()