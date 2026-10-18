# controllers/arduino_controller.py

import os
import threading
import time
from datetime import datetime
import json
from flask import request
from controllers.pid_controller import PIController, PIDController
from utils.log_bus import log_bus
from utils.audit_logger import audit_logger


def _env_float(nom, defaut):
    """Lit une durée/valeur configurable dans l'environnement (valeur par défaut sinon)."""
    try:
        return float(os.environ.get(nom, defaut))
    except (TypeError, ValueError):
        return float(defaut)


# ---------------------------------------------------------------------------
# SÉCURITÉ CHAUFFAGE - durées configurables (variables d'environnement)
# ---------------------------------------------------------------------------
# Battement de cœur : tant que la régulation tourne, le SERVEUR envoie au moins
# une commande valide (HB, PWM ou SET) toutes les N secondes. Le watchdog du
# firmware (10 s) coupe le chauffage si rien n'arrive.
HEARTBEAT_REGULATION_S = _env_float('HEARTBEAT_REGULATION_S', 2)
# Inactivité de l'interface (aucune requête de données ni action du propriétaire)
INACTIVITE_COURTE_S = _env_float('INACTIVITE_COURTE_S', 120)    # STOP + PWM:0, connexion "suspendue"
INACTIVITE_LONGUE_S = _env_float('INACTIVITE_LONGUE_S', 600)    # fermeture du port + déconnexion
SESSION_MAX_S = _env_float('SESSION_MAX_S', 7200)               # durée maximale de session (0 = illimitée)
# Délai de grâce après "fermeture de page" (un rechargement ne doit pas tout couper)
GRACE_PAGE_LEAVING_S = _env_float('GRACE_PAGE_LEAVING_S', 15)
SUPERVISION_PERIODE_S = _env_float('SUPERVISION_PERIODE_S', 5)
# Déconnexion : attente de l'accusé "STATUS: STOPPED" de l'Arduino
ACK_STOP_TIMEOUT_S = _env_float('ACK_STOP_TIMEOUT_S', 3)
ACK_STOP_RETRIES = int(_env_float('ACK_STOP_RETRIES', 3))
# Arrêt du serveur : temps laissé aux commandes STOP pour partir avant de quitter
ARRET_SERVEUR_ATTENTE_S = _env_float('ARRET_SERVEUR_ATTENTE_S', 2)

# États de sécurité d'une connexion
ETAT_NORMAL = 'normal'
ETAT_PAUSE = 'pause'            # "Arrêter la surveillance" : chauffage coupé, PID ignoré
ETAT_SUSPENDU = 'suspendu'      # inactivité courte : chauffage coupé
ETAT_URGENCE = 'urgence'        # arrêt d'urgence : aucun PWM tant que non réarmé
ETAT_VERROUILLE = 'verrouille'  # watchdog/surchauffe de l'Arduino : réarmement requis

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
            # --- sécurité chauffage ---
            'etat_securite': ETAT_NORMAL,
            'alerte_securite': None,
            'cree_le': time.time(),
            'derniere_activite_ui': time.time(),   # dernière requête de données / action du propriétaire
            'depart_page_le': None,                # début du délai de grâce après fermeture de page
            'dernier_envoi_regulation': 0,         # dernier HB/PWM/SET envoyé
            'consigne_definie': False,             # boucle ouverte : pas de chauffe avant une consigne explicite
            'pwm_arduino': 0,                      # dernier PWM annoncé par l'Arduino (ligne DATA)
            'stop_accuse_le': 0,                   # dernier "STATUS: STOPPED" reçu
            'dernier_stop_envoye': 0,
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
            self.connexions_arduino[id_connexion]['derniere_activite_ui'] = time.time()
            # ARM : lève un éventuel verrou d'une session précédente (sans chauffer),
            # puis mode "none" : l'Arduino ne chauffe qu'après une consigne explicite.
            self.envoyer_commande_brute(id_connexion, "ARM\n")
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

                        connexion['pwm_arduino'] = pwm_recue
                        connexion['donnees'] = {
                            "temperature": temperature_actuelle,
                            "consigne": consigne_actuelle,
                            "timestamp": time.time()
                        }

                        type_controleur = connexion['type_controleur']

                        # SÉCURITÉ : pause, urgence, suspension ou verrou -> aucune régulation.
                        # Les mesures sont enregistrées (affichage) mais jamais envoyées au PID,
                        # et aucun PWM/SET n'est émis. Si l'Arduino chauffe encore, on renvoie STOP.
                        if connexion.get('etat_securite', ETAT_NORMAL) != ETAT_NORMAL or not connexion.get('surveillance_active', True):
                            connexion['controller_data'] = None
                            self._garantir_chauffage_coupe(id_connexion, connexion)
                            self.enregistrer_donnees_temps_reel(
                                id_connexion, temperature_actuelle, consigne_actuelle,
                                type_controleur, connexion['surveillance_active'], None
                            )
                            return

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
                            # BOUCLE OUVERTE : mêmes sécurités que le PID. SET n'est envoyé qu'après
                            # une consigne explicite de l'utilisateur, puis répété toutes les
                            # HEARTBEAT_REGULATION_S secondes (il sert aussi de battement de cœur).
                            if connexion.get('consigne_definie'):
                                maintenant = time.time()
                                if maintenant - connexion.get('dernier_envoi_regulation', 0) >= HEARTBEAT_REGULATION_S:
                                    if self.envoyer_commande_brute(id_connexion, f"SET:{consigne_actuelle}\n"):
                                        connexion['dernier_envoi_regulation'] = maintenant

                        if type_controleur in ['pi', 'pid', 'mpc', 'custom']:
                            # Une sortie absente (None) est traitée comme 0 : jamais de chauffe "par défaut"
                            self._appliquer_sortie_regulation(id_connexion, connexion, 0 if output is None else output)

                        connexion['controller_data'] = controller_data

                        self.enregistrer_donnees_temps_reel(
                            id_connexion, temperature_actuelle, consigne_actuelle,
                            type_controleur, connexion['surveillance_active'], controller_data
                        )

                    except (ValueError, IndexError) as e:
                        log_bus.error('arduino', f"Erreur analyse ligne DATA ({id_connexion}) : {e} - Ligne: {ligne}")

            elif ligne.startswith("STATUS:"):
                self._traiter_statut_arduino(id_connexion, connexion, ligne)
            elif "ALERTE" in ligne:
                log_bus.warning('arduino', f"ALERTE : {ligne} ({id_connexion})")
            # PONG, "PWM recue:", "Mode defini:", "Consigne definie:", "Temperature:"
            # sont des accusés de réception : ils sont gérés localement par
            # l'agent (voir agent_local/agent_arduino.py) qui ne les relaie
            # pas tous pour ne pas saturer la liaison Internet.

        except Exception as e:
            log_bus.error('arduino', f"Erreur traitement ligne ({id_connexion}) : {e}")

    # ========================================================================
    # SÉCURITÉ CHAUFFAGE
    # ========================================================================

    def _audit(self, id_connexion, evenement, details):
        """Journal d'audit (ne doit jamais empêcher une coupure de chauffage)."""
        try:
            connexion = self.connexions_arduino.get(id_connexion, {})
            audit_logger.log(
                event_type=evenement,
                user_id=connexion.get('user_id'),
                connection_id=id_connexion,
                details=details,
                ip_address=None
            )
        except Exception as e:
            log_bus.error('arduino', f"Audit impossible ({evenement}) : {e}")

    def _traiter_statut_arduino(self, id_connexion, connexion, ligne):
        """Lignes STATUS: de l'Arduino : accusé de STOP, watchdog, surchauffe, verrou."""
        statut = ligne.split(":", 1)[1].strip().upper() if ":" in ligne else ""
        if statut == "STOPPED":
            connexion['stop_accuse_le'] = time.time()
        elif statut in ("WATCHDOG", "SURCHAUFFE", "VERROUILLE"):
            if connexion.get('etat_securite') != ETAT_VERROUILLE:
                connexion['etat_securite'] = ETAT_VERROUILLE
                self.reinitialiser_regulation(connexion)
                if statut == "SURCHAUFFE":
                    msg = "Surchauffe détectée par l'Arduino : chauffage coupé. Réarmement requis."
                else:
                    msg = ("Liaison de régulation perdue : le chauffage a été coupé par la sécurité "
                           "de l'Arduino (watchdog). Réarmement requis.")
                connexion['alerte_securite'] = msg
                log_bus.warning('arduino', f"{statut} ({id_connexion}) : chauffage coupé par l'Arduino")
                self._audit(id_connexion, 'ARDUINO_' + statut, msg)

    def reinitialiser_regulation(self, connexion):
        """Remet le PID dans un état cohérent avec un chauffage à 0 (intégrale et dérivée nulles)."""
        maintenant = time.time()
        for cle in ('pi_controller', 'pid_controller'):
            if cle in connexion:
                connexion[cle].reset()
        connexion['controller_state'] = {
            'last_error': 0,
            'integral_state': 0,
            'last_time': maintenant,
            'state_history': []
        }
        connexion['controller_data'] = None
        connexion['derniere_pwm_envoyee'] = 0
        connexion['derniere_sortie_calculee'] = 0
        connexion['dernier_envoi_regulation'] = 0

    def _appliquer_sortie_regulation(self, id_connexion, connexion, output):
        """Envoie la sortie du PID : PWM en cas de changement (y compris 0),
        sinon battement de cœur HB toutes les HEARTBEAT_REGULATION_S secondes."""
        maintenant = time.time()
        derniere_sortie = connexion.get('derniere_sortie_calculee', 0)
        jamais_envoye = connexion.get('dernier_envoi_regulation', 0) == 0
        retour_a_zero = (output <= 0 and connexion.get('derniere_pwm_envoyee', 0) != 0)

        if jamais_envoye or retour_a_zero or abs(output - derniere_sortie) > 1:
            if self.envoyer_commande_pwm_arduino(id_connexion, output):
                connexion['derniere_sortie_calculee'] = output
                connexion['dernier_envoi_regulation'] = maintenant
        elif maintenant - connexion['dernier_envoi_regulation'] >= HEARTBEAT_REGULATION_S:
            if self.envoyer_commande_brute(id_connexion, "HB\n"):
                connexion['dernier_envoi_regulation'] = maintenant

    def _garantir_chauffage_coupe(self, id_connexion, connexion):
        """En pause/urgence/suspension/verrou : si l'Arduino annonce encore un PWM > 0,
        on renvoie STOP + PWM:0 (au plus toutes les 2 s)."""
        if connexion.get('pwm_arduino', 0) > 0 and time.time() - connexion.get('dernier_stop_envoye', 0) >= 2:
            self.couper_chauffage(id_connexion, "chauffage encore actif en état de sécurité")

    def couper_chauffage(self, id_connexion, raison=""):
        """Envoie immédiatement STOP puis PWM:0 à l'Arduino via l'agent. Ne dépend pas du PID.
        Retourne True si les commandes ont été transmises à l'agent."""
        connexion = self.connexions_arduino.get(id_connexion)
        if not connexion:
            return False
        connexion['dernier_stop_envoye'] = time.time()
        ok = self.envoyer_commande_brute(id_connexion, "STOP\n")
        ok = self.envoyer_commande_brute(id_connexion, "PWM:0\n") and ok
        connexion['derniere_pwm_envoyee'] = 0
        connexion['derniere_sortie_calculee'] = 0
        log_bus.warning('arduino', f"Coupure chauffage ({id_connexion}) : {raison or 'demande'} - commandes transmises : {ok}")
        return ok

    def marquer_activite_ui(self, id_connexion):
        """Appelée par les requêtes de données/actions du propriétaire : l'interface est vivante."""
        connexion = self.connexions_arduino.get(id_connexion)
        if connexion:
            connexion['derniere_activite_ui'] = time.time()
            connexion['depart_page_le'] = None   # annule le délai de grâce (rechargement de page)

    def mettre_en_pause(self, id_connexion, raison="pause demandée"):
        """« Arrêter la surveillance » : STOP + PWM:0, mesures ignorées, PID réinitialisé."""
        connexion = self.connexions_arduino.get(id_connexion)
        if not connexion:
            return False
        connexion['surveillance_active'] = False
        if connexion.get('etat_securite') == ETAT_NORMAL:
            connexion['etat_securite'] = ETAT_PAUSE
        self.reinitialiser_regulation(connexion)
        return self.couper_chauffage(id_connexion, raison)

    def arret_urgence(self, id_connexion, utilisateur=None):
        """Arrêt d'urgence : fonctionne même si le PID est en erreur (n'utilise pas le PID)."""
        connexion = self.connexions_arduino.get(id_connexion)
        if not connexion:
            return False
        # D'abord couper (priorité absolue), ensuite seulement l'état et le nettoyage
        ok = self.couper_chauffage(id_connexion, f"ARRÊT D'URGENCE ({utilisateur})")
        connexion['etat_securite'] = ETAT_URGENCE
        connexion['surveillance_active'] = False
        connexion['type_controleur'] = 'none'
        connexion['consigne_definie'] = False
        connexion['alerte_securite'] = "Arrêt d'urgence activé : chauffage coupé. Réarmez pour reprendre."
        try:
            self.reinitialiser_regulation(connexion)
        except Exception as e:
            log_bus.error('controle', f"Réinitialisation PID impossible pendant l'urgence ({id_connexion}) : {e}")
        return ok

    def rearmer(self, id_connexion):
        """Réarmement explicite après urgence/verrou/pause : PID réinitialisé, ARM envoyé.
        Le chauffage ne repart pas seul : une consigne ou un PWM valide est ensuite requis."""
        connexion = self.connexions_arduino.get(id_connexion)
        if not connexion or not connexion.get('connecte'):
            return False
        self.reinitialiser_regulation(connexion)
        connexion['etat_securite'] = ETAT_NORMAL
        connexion['alerte_securite'] = None
        connexion['surveillance_active'] = True
        connexion['depart_page_le'] = None
        connexion['derniere_activite_ui'] = time.time()
        ok = self.envoyer_commande_brute(id_connexion, "ARM\n")
        # L'action de réarmement est explicite : la consigne affichée est considérée définie
        connexion['consigne_definie'] = True
        self.envoyer_mode_arduino(id_connexion, connexion.get('type_controleur', 'none'))
        return ok

    def signaler_depart_page(self, id_connexion):
        """La page se ferme (pagehide) : démarre le délai de grâce. Si aucune activité ne
        reprend avant GRACE_PAGE_LEAVING_S, la supervision coupe le chauffage."""
        connexion = self.connexions_arduino.get(id_connexion)
        if connexion and connexion.get('depart_page_le') is None:
            connexion['depart_page_le'] = time.time()

    def suspendre_inactivite(self, id_connexion, raison):
        connexion = self.connexions_arduino.get(id_connexion)
        if not connexion:
            return
        if connexion.get('etat_securite') in (ETAT_NORMAL, ETAT_PAUSE):
            connexion['etat_securite'] = ETAT_SUSPENDU
            connexion['surveillance_active'] = False
            connexion['alerte_securite'] = f"Connexion suspendue ({raison}) : chauffage coupé."
            self.reinitialiser_regulation(connexion)
            self.couper_chauffage(id_connexion, raison)
            self._audit(id_connexion, 'CONNEXION_SUSPENDUE', f"Chauffage coupé : {raison}")

    def fermer_apres_inactivite(self, id_connexion, raison):
        """Étape 2 : coupe, ferme le port série (libéré pour les autres) et déconnecte."""
        connexion = self.connexions_arduino.get(id_connexion)
        if not connexion:
            return
        self.couper_chauffage(id_connexion, raison)
        self.demander_fermeture_port(id_connexion)
        self._audit(id_connexion, 'CONNEXION_FERMEE_AUTO', f"Port fermé : {raison}")
        log_bus.warning('arduino', f"Connexion {id_connexion} fermée automatiquement : {raison}")
        connexion['connecte'] = False
        self.connexions_arduino.pop(id_connexion, None)

    def superviser(self):
        """Tâche périodique (APScheduler) : inactivité de l'interface, fermeture de page,
        durée maximale de session, et filet de sécurité STOP."""
        maintenant = time.time()
        for id_connexion, connexion in list(self.connexions_arduino.items()):
            try:
                inactif = maintenant - connexion.get('derniere_activite_ui', maintenant)
                depart = connexion.get('depart_page_le')
                duree = maintenant - connexion.get('cree_le', maintenant)

                if SESSION_MAX_S > 0 and duree > SESSION_MAX_S:
                    self.fermer_apres_inactivite(id_connexion, f"durée maximale de session atteinte ({int(SESSION_MAX_S)} s)")
                    continue
                if inactif > INACTIVITE_LONGUE_S:
                    self.fermer_apres_inactivite(id_connexion, f"inactivité longue ({int(inactif)} s)")
                    continue
                if depart is not None and maintenant - depart > GRACE_PAGE_LEAVING_S:
                    connexion['depart_page_le'] = None
                    self.suspendre_inactivite(id_connexion, "page fermée")
                elif inactif > INACTIVITE_COURTE_S and connexion.get('etat_securite') == ETAT_NORMAL:
                    self.suspendre_inactivite(id_connexion, f"inactivité ({int(inactif)} s)")

                # Filet de sécurité : hors état normal, le chauffage doit être à 0
                if connexion.get('etat_securite') != ETAT_NORMAL and connexion.get('connecte'):
                    self._garantir_chauffage_coupe(id_connexion, connexion)
            except Exception as e:
                log_bus.error('arduino', f"Erreur supervision {id_connexion} : {e}")

    def arret_serveur(self, *_):
        """SIGTERM / arrêt du serveur : STOP à toutes les connexions actives avant de quitter."""
        n = 0
        for id_connexion, connexion in list(self.connexions_arduino.items()):
            if connexion.get('connecte'):
                try:
                    self.couper_chauffage(id_connexion, "arrêt du serveur")
                    n += 1
                except Exception as e:
                    log_bus.error('arduino', f"Arrêt serveur : échec STOP {id_connexion} : {e}")
        if n:
            log_bus.warning('system', f"Arrêt du serveur : STOP envoyé à {n} connexion(s)")
            time.sleep(ARRET_SERVEUR_ATTENTE_S)   # laisse partir les émissions Socket.IO

    def deconnecter_avec_accuse(self, id_connexion):
        """Déconnexion : STOP puis attente de « STATUS: STOPPED » (ACK_STOP_RETRIES essais
        de ACK_STOP_TIMEOUT_S). Retourne (reussi, message)."""
        connexion = self.connexions_arduino.get(id_connexion)
        if not connexion:
            return False, "Connexion non trouvée"
        if connexion.get('etat_securite') == ETAT_NORMAL:
            connexion['etat_securite'] = ETAT_PAUSE
        connexion['surveillance_active'] = False
        self.reinitialiser_regulation(connexion)

        if not connexion.get('connecte'):
            return False, ("Liaison avec la carte perdue : l'arrêt du chauffage ne peut pas être confirmé. "
                           "La sécurité de l'Arduino coupera le chauffage de façon autonome.")

        for _ in range(max(1, ACK_STOP_RETRIES)):
            debut = time.time()
            self.couper_chauffage(id_connexion, "déconnexion")
            while time.time() - debut < ACK_STOP_TIMEOUT_S:
                if connexion.get('stop_accuse_le', 0) >= debut:
                    self.demander_fermeture_port(id_connexion)
                    return True, "Déconnecté"
                time.sleep(0.1)
        return False, ("ALERTE : l'arrêt du chauffage n'a pas été confirmé par l'Arduino. "
                       "La connexion reste ouverte : réessayez ou utilisez l'arrêt d'urgence.")

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