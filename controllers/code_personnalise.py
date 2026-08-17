# code_personnalise.py
import ast
import threading
import time
import json
import hashlib
from datetime import datetime
from typing import Dict, Any, Optional, Tuple
import sys
import io

# Forcer l'encodage UTF-8 pour la console Windows
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# ============================================================================
# GESTIONNAIRE DE CODE PERSONNALISÉ
# ============================================================================

class CustomCodeManager:
    """Gestionnaire de code personnalisé avec sandbox sécurisé"""
    
    def __init__(self, arduino_controller=None):
        # Stockage des codes utilisateur par clé user_id + connection_id
        self.user_codes = {}
        
        # Référence au contrôleur Arduino
        self.arduino_controller = arduino_controller
        
        # Codes par défaut du système
        self.default_codes = {
            'pi': {
                'name': 'Contrôleur PI',
                'code': '''def control(error, dt, integral_state=0, **kwargs):
    # Récupérer les paramètres depuis kwargs
    kp = kwargs.get('kp', 1.5)      # Valeur par défaut 1.5
    ki = kwargs.get('ki', 0.05)     # Valeur par défaut 0.05
    setpoint = kwargs.get('setpoint', 25.0)  # Valeur par défaut 25.0
    
    # Mise à jour de l'intégrale
    integral_state = integral_state + (error * dt)
    
    # Limiter l'intégrale pour éviter le windup
    integral_state = max(-100, min(100, integral_state))
    
    # Calcul de la sortie
    output = (kp * error) + (ki * integral_state)
    
    # Saturation
    output = max(0, min(100, output))
    
    return output, integral_state''',
                'description': 'Contrôleur Proportionnel-Intégral standard',
                'variables': ['error', 'dt', 'integral_state']
            },
            'pid': {
                'name': 'Contrôleur PID',
                'code': '''def control(error, dt, last_error=0, integral_state=0, **kwargs):
    # Récupérer les paramètres depuis kwargs
    kp = kwargs.get('kp', 2.0)      # Valeur par défaut 2.0
    ki = kwargs.get('ki', 0.08)     # Valeur par défaut 0.08
    kd = kwargs.get('kd', 0.1)      # Valeur par défaut 0.1
    setpoint = kwargs.get('setpoint', 25.0)  # Valeur par défaut 25.0
    
    # Mise à jour de l'intégrale
    integral_state = integral_state + (error * dt)
    
    # Limiter l'intégrale pour éviter le windup
    integral_state = max(-100, min(100, integral_state))
    
    # Calcul de la dérivée
    if dt > 0:
        derivative = (error - last_error) / dt
    else:
        derivative = 0
    
    # Calcul de la sortie
    output = (kp * error) + (ki * integral_state) + (kd * derivative)
    
    # Saturation
    output = max(0, min(100, output))
    
    return output, integral_state''',
                'description': 'Contrôleur Proportionnel-Intégral-Dérivé',
                'variables': ['error', 'dt', 'last_error', 'integral_state']
            },
            'mpc': {
                'name': 'Contrôleur MPC simplifié',
                'code': '''def control(error, dt, state_history=[], **kwargs):
    # Récupérer les paramètres depuis kwargs
    kp = kwargs.get('kp', 2.0)      # Valeur par défaut 2.0
    ki = kwargs.get('ki', 0.05)     # Valeur par défaut 0.05
    setpoint = kwargs.get('setpoint', 25.0)  # Valeur par défaut 25.0
    
    # Paramètres MPC
    prediction_horizon = kwargs.get('prediction_horizon', 5)
    control_horizon = kwargs.get('control_horizon', 2)
    
    # État simple pour l'exemple
    if len(state_history) < 2:
        # Pas assez de données pour la prédiction
        output = kp * error
    else:
        # Prédiction très simple basée sur la tendance
        recent_error = state_history[-1]['error']
        error_change = error - recent_error
        
        # Contrôle basé sur la prédiction
        predicted_error = error + error_change * prediction_horizon
        output = (kp * predicted_error) + (ki * error * dt)
    
    # Saturation
    output = max(0, min(100, output))
    
    return output''',
                'description': 'Contrôleur Prédictif Modèle simplifié',
                'variables': ['error', 'dt', 'state_history']
            }
        }
        
        # Sandbox sécurisé
        self.sandbox_globals = {
            '__builtins__': {
                'abs': abs,
                'max': max,
                'min': min,
                'len': len,
                'range': range,
                'float': float,
                'int': int,
                'bool': bool,
                'list': list,
                'dict': dict,
                'tuple': tuple,
                'str': str,
                'round': round,
                'sum': sum,
                'pow': pow,
                '__import__': None  # Bloquer les imports
            }
        }
        
        # Historique d'exécution
        self.execution_history = {}
        
        # Verrou pour accès concurrent
        self.lock = threading.RLock()
        
        print("✅ CustomCodeManager initialisé")
    
    def set_arduino_controller(self, arduino_controller):
        """Définit la référence au contrôleur Arduino"""
        self.arduino_controller = arduino_controller
        print("✅ ArduinoController lié à CustomCodeManager")
    
    def _get_default_params(self, code_type: str) -> Dict[str, float]:
        """Retourne les paramètres par défaut pour un type de contrôleur"""
        defaults = {
            'pi': {'kp': 1.5, 'ki': 0.05, 'setpoint': 25.0},
            'pid': {'kp': 2.0, 'ki': 0.08, 'kd': 0.1, 'setpoint': 25.0},
            'mpc': {'kp': 2.0, 'ki': 0.05, 'setpoint': 25.0, 'prediction_horizon': 5, 'control_horizon': 2}
        }
        return defaults.get(code_type, {})
    
    def _get_actual_controller_params(self, connection_id: str, code_type: str) -> Dict[str, float]:
        """Récupère les paramètres actuels du contrôleur"""
        try:
            # Si arduino_controller n'est pas défini, utiliser les valeurs par défaut
            if not self.arduino_controller:
                print("⚠️ ArduinoController non disponible dans CustomCodeManager")
                return self._get_default_params(code_type)
            
            if connection_id not in self.arduino_controller.connexions_arduino:
                print(f"⚠️ Connexion {connection_id} non trouvée dans arduino_controller")
                return self._get_default_params(code_type)
            
            conn_data = self.arduino_controller.connexions_arduino[connection_id]
            params = {}
            
            print(f"🔍 Recherche paramètres pour {code_type} dans connexion {connection_id}")
            
            if code_type == 'pi':
                if 'pi_controller' in conn_data:
                    controller = conn_data['pi_controller']
                    params['kp'] = controller.kp
                    params['ki'] = controller.ki
                    params['setpoint'] = getattr(controller, 'setpoint', 25.0)
                    print(f"📊 Paramètres PI récupérés: Kp={params['kp']}, Ki={params['ki']}, Setpoint={params['setpoint']}")
                
                # Vérifier aussi les paramètres stockés
                if 'parametres' in conn_data and 'pi' in conn_data['parametres']:
                    pi_params = conn_data['parametres']['pi']
                    params['kp'] = pi_params.get('kp', params.get('kp', 1.0))
                    params['ki'] = pi_params.get('ki', params.get('ki', 0.1))
                    print(f"📊 Paramètres PI stockés utilisés: Kp={params['kp']}, Ki={params['ki']}")
            
            elif code_type == 'pid':
                if 'pid_controller' in conn_data:
                    controller = conn_data['pid_controller']
                    params['kp'] = controller.kp
                    params['ki'] = controller.ki
                    params['kd'] = controller.kd
                    params['setpoint'] = getattr(controller, 'setpoint', 25.0)
                    print(f"📊 Paramètres PID récupérés: Kp={params['kp']}, Ki={params['ki']}, Kd={params['kd']}, Setpoint={params['setpoint']}")
                
                # Vérifier aussi les paramètres stockés
                if 'parametres' in conn_data and 'pid' in conn_data['parametres']:
                    pid_params = conn_data['parametres']['pid']
                    params['kp'] = pid_params.get('kp', params.get('kp', 2.0))
                    params['ki'] = pid_params.get('ki', params.get('ki', 0.08))
                    params['kd'] = pid_params.get('kd', params.get('kd', 0.1))
                    print(f"📊 Paramètres PID stockés utilisés: Kp={params['kp']}, Ki={params['ki']}, Kd={params['kd']}")
            
            elif code_type == 'mpc':
                # Paramètres par défaut pour MPC
                params.update(self._get_default_params('mpc'))
            
            # Ajouter les paramètres de base si manquants
            defaults = self._get_default_params(code_type)
            for key, value in defaults.items():
                if key not in params:
                    params[key] = value
            
            print(f"✅ Paramètres finaux pour {code_type}: {params}")
            return params
            
        except Exception as e:
            print(f"⚠️ Erreur récupération paramètres contrôleur: {e}")
            return self._get_default_params(code_type)
    
    def validate_code_security(self, code: str) -> Tuple[bool, str]:
        """Valide la sécurité du code avant exécution"""
        try:
            # Vérifications de sécurité
            forbidden_patterns = [
                'import ', 'from ', '__import__', 'exec(', 'eval(',
                'compile(', 'open(', '__builtins__', 'os.', 'sys.',
                'subprocess', 'threading', 'multiprocessing', 'socket',
                'file(', 'input(', 'raw_input', 'getattr', 'setattr',
                'delattr', 'globals(', 'locals(', 'vars(', 'dir('
            ]
            
            for pattern in forbidden_patterns:
                if pattern in code.lower():
                    return False, f"Pattern interdit détecté: {pattern}"
            
            # Analyse syntaxique
            tree = ast.parse(code, mode='exec')
            
            # Vérifier les appels de fonction dangereux
            for node in ast.walk(tree):
                # Bloquer les imports
                if isinstance(node, ast.Import) or isinstance(node, ast.ImportFrom):
                    return False, "Les imports ne sont pas autorisés"
                
                # Bloquer les appels à des fonctions dangereuses
                if isinstance(node, ast.Call):
                    if isinstance(node.func, ast.Name):
                        func_name = node.func.id.lower()
                        if func_name in ['exec', 'eval', 'compile', 'open', 'input']:
                            return False, f"Appel à une fonction dangereuse: {func_name}"
            
            return True, "Code sécurisé"
            
        except SyntaxError as e:
            return False, f"Erreur de syntaxe: {str(e)}"
        except Exception as e:
            return False, f"Erreur de validation: {str(e)}"
    
    def save_user_code(self, user_id: str, connection_id: str, code_type: str, code: str, 
                      name: str = "Code personnalisé", description: str = "") -> Dict[str, Any]:
        """Sauvegarde le code personnalisé d'un utilisateur"""
        with self.lock:
            # Créer une clé unique utilisateur + connexion
            user_key = f"user_{user_id}_{connection_id}"
            
            if user_key not in self.user_codes:
                self.user_codes[user_key] = {}
            
            # Validation de sécurité
            is_valid, message = self.validate_code_security(code)
            if not is_valid:
                return {
                    'success': False,
                    'message': f"Code non sécurisé: {message}",
                    'code_hash': None
                }
            
            # Générer un hash pour identifier le code
            code_hash = hashlib.md5(code.encode()).hexdigest()[:8]
            
            # Sauvegarder le code
            self.user_codes[user_key][code_type] = {
                'code': code,
                'name': name,
                'description': description,
                'code_hash': code_hash,
                'user_id': user_id,
                'connection_id': connection_id,
                'created_at': datetime.now().isoformat(),
                'last_modified': datetime.now().isoformat(),
                'is_active': False,
                'execution_count': 0,
                'last_execution': None
            }
            
            # Sauvegarde dans un fichier pour persistance
            self._save_to_file(user_key)
            
            print(f"💾 Code {code_type} sauvegardé pour utilisateur {user_id}, connexion {connection_id}")
            
            return {
                'success': True,
                'message': 'Code sauvegardé avec succès',
                'code_hash': code_hash
            }
    
    def activate_user_code(self, user_id: str, connection_id: str, code_type: str) -> Dict[str, Any]:
        """Active le code personnalisé d'un utilisateur"""
        with self.lock:
            user_key = f"user_{user_id}_{connection_id}"
            
            if user_key not in self.user_codes:
                return {
                    'success': False,
                    'message': 'Aucun code sauvegardé pour cette connexion'
                }
            
            if code_type not in self.user_codes[user_key]:
                return {
                    'success': False,
                    'message': f'Aucun code de type {code_type} trouvé'
                }
            
            # Activer le code utilisateur
            self.user_codes[user_key][code_type]['is_active'] = True
            self.user_codes[user_key][code_type]['activated_at'] = datetime.now().isoformat()
            
            # Désactiver les autres codes du même type pour cet utilisateur
            for key in self.user_codes:
                if key.startswith(f"user_{user_id}_"):
                    for other_type in self.user_codes[key]:
                        if other_type == code_type and other_type != code_type:
                            self.user_codes[key][other_type]['is_active'] = False
            
            # Mettre à jour le fichier
            self._save_to_file(user_key)
            
            print(f"✅ Code personnalisé {code_type} activé pour utilisateur {user_id}, connexion {connection_id}")
            
            return {
                'success': True,
                'message': f'Code {code_type} activé',
                'is_active': True
            }
    
    def deactivate_user_code(self, user_id: str, connection_id: str, code_type: str) -> Dict[str, Any]:
        """Désactive le code personnalisé d'un utilisateur"""
        with self.lock:
            user_key = f"user_{user_id}_{connection_id}"
            
            if user_key in self.user_codes and code_type in self.user_codes[user_key]:
                self.user_codes[user_key][code_type]['is_active'] = False
                self._save_to_file(user_key)
                
                print(f"✅ Code personnalisé {code_type} désactivé pour utilisateur {user_id}")
                
                return {
                    'success': True,
                    'message': f'Code {code_type} désactivé',
                    'is_active': False
                }
            
            return {
                'success': False,
                'message': 'Code non trouvé'
            }
    
    def get_active_code(self, user_id: str, connection_id: str, code_type: str) -> Optional[Dict[str, Any]]:
        """Récupère le code actif (utilisateur ou par défaut)"""
        with self.lock:
            user_key = f"user_{user_id}_{connection_id}"
            
            # Vérifier si l'utilisateur a un code actif
            if (user_key in self.user_codes and 
                code_type in self.user_codes[user_key] and
                self.user_codes[user_key][code_type]['is_active']):
                
                user_code = self.user_codes[user_key][code_type].copy()
                user_code['is_custom'] = True
                user_code['source'] = 'user'
                
                # Récupérer les paramètres actuels pour les inclure
                controller_params = self._get_actual_controller_params(connection_id, code_type)
                user_code['controller_params'] = controller_params
                
                print(f"🔧 Code personnalisé actif trouvé pour {code_type} (user: {user_id})")
                return user_code
            
            # Retourner le code par défaut
            if code_type in self.default_codes:
                default_code = self.default_codes[code_type].copy()
                default_code['is_custom'] = False
                default_code['source'] = 'default'
                default_code['is_active'] = True
                
                # Récupérer les paramètres actuels pour les inclure
                controller_params = self._get_actual_controller_params(connection_id, code_type)
                default_code['controller_params'] = controller_params
                
                print(f"🔧 Code par défaut utilisé pour {code_type}")
                return default_code
            
            print(f"⚠️ Aucun code trouvé pour {code_type}")
            return None
    
    def execute_control_code(self, user_id: str, connection_id: str, code_type: str, 
                           **kwargs) -> Tuple[Any, Dict[str, Any]]:
        """Exécute le code de contrôle (utilisateur ou par défaut) avec les paramètres actuels"""
        with self.lock:
            try:
                print(f"🔧 Début exécution code {code_type} pour {connection_id} (user: {user_id})")
                
                # Récupérer le code actif
                code_info = self.get_active_code(user_id, connection_id, code_type)
                
                if not code_info:
                    raise ValueError(f"Aucun code disponible pour {code_type}")
                
                # RÉCUPÉRER LES PARAMÈTRES ACTUELS DU CONTRÔLEUR
                controller_params = self._get_actual_controller_params(connection_id, code_type)
                print(f"📊 Paramètres contrôleur récupérés: {controller_params}")
                
                # Préparer l'environnement d'exécution
                exec_globals = self.sandbox_globals.copy()
                
                # Ajouter les arguments d'entrée
                for key, value in kwargs.items():
                    exec_globals[key] = value
                
                # AJOUTER LES PARAMÈTRES DU CONTRÔLEUR À L'ENVIRONNEMENT
                # Ceci permet d'accéder directement à kp, ki, kd dans le code
                exec_globals.update(controller_params)
                
                # Ajouter aussi les paramètres dans kwargs pour le passage à la fonction
                all_params = {**kwargs, **controller_params}
                
                # Compiler et exécuter le code
                print(f"📝 Exécution du code {code_type}")
                code_obj = compile(code_info['code'], '<user_code>', 'exec')
                exec(code_obj, exec_globals)
                
                # Récupérer la fonction control
                if 'control' not in exec_globals:
                    raise ValueError("La fonction 'control' n'est pas définie dans le code")
                
                control_func = exec_globals['control']
                
                # Préparer les arguments pour la fonction control
                func_args = {}
                import inspect
                sig = inspect.signature(control_func)
                
                # Passer tous les paramètres disponibles
                for param_name in sig.parameters:
                    if param_name in all_params:
                        func_args[param_name] = all_params[param_name]
                    elif param_name == 'integral_state':
                        func_args[param_name] = kwargs.get('integral_state', 0)
                    elif param_name == 'last_error':
                        func_args[param_name] = kwargs.get('last_error', 0)
                    elif param_name == 'state_history':
                        func_args[param_name] = kwargs.get('state_history', [])
                    elif param_name == 'kwargs':
                        # Si la fonction accepte **kwargs, passer tous les paramètres
                        func_args[param_name] = all_params
                
                print(f"📤 Arguments passés à control(): {func_args}")
                
                # Exécuter la fonction
                result = control_func(**func_args)
                
                print(f"✅ Code exécuté avec succès. Résultat: {result}")
                
                # Mettre à jour les statistiques
                if code_info.get('is_custom'):
                    user_key = f"user_{user_id}_{connection_id}"
                    
                    if user_key not in self.execution_history:
                        self.execution_history[user_key] = {}
                    
                    if code_type not in self.execution_history[user_key]:
                        self.execution_history[user_key][code_type] = []
                    
                    self.execution_history[user_key][code_type].append({
                        'timestamp': datetime.now().isoformat(),
                        'inputs': all_params,
                        'result': result,
                        'controller_params': controller_params
                    })
                    
                    # Limiter l'historique
                    if len(self.execution_history[user_key][code_type]) > 100:
                        self.execution_history[user_key][code_type] = \
                            self.execution_history[user_key][code_type][-100:]
                    
                    # Mettre à jour le compteur
                    self.user_codes[user_key][code_type]['execution_count'] += 1
                    self.user_codes[user_key][code_type]['last_execution'] = \
                        datetime.now().isoformat()
                
                return result, {
                    'success': True,
                    'source': code_info['source'],
                    'code_hash': code_info.get('code_hash'),
                    'execution_time': datetime.now().isoformat(),
                    'controller_params': controller_params
                }
                
            except Exception as e:
                error_msg = f"Erreur d'exécution du code {code_type}: {str(e)}"
                print(f"❌ {error_msg}")
                
                # En cas d'erreur, utiliser le code par défaut
                if code_type in self.default_codes:
                    print(f"⚠️ Utilisation du code par défaut pour {code_type}")
                    default_code = self.default_codes[code_type]
                    
                    # Ré-exécuter avec le code par défaut
                    exec_globals = self.sandbox_globals.copy()
                    
                    # Préparer les paramètres
                    all_params = {**kwargs, **self._get_actual_controller_params(connection_id, code_type)}
                    
                    for key, value in all_params.items():
                        exec_globals[key] = value
                    
                    code_obj = compile(default_code['code'], '<default_code>', 'exec')
                    exec(code_obj, exec_globals)
                    
                    if 'control' in exec_globals:
                        control_func = exec_globals['control']
                        
                        # Appel basique
                        try:
                            # Préparer les arguments pour la fonction control
                            func_args = {}
                            import inspect
                            sig = inspect.signature(control_func)
                            
                            for param_name in sig.parameters:
                                if param_name in all_params:
                                    func_args[param_name] = all_params[param_name]
                                elif param_name == 'integral_state':
                                    func_args[param_name] = kwargs.get('integral_state', 0)
                                elif param_name == 'last_error':
                                    func_args[param_name] = kwargs.get('last_error', 0)
                                elif param_name == 'state_history':
                                    func_args[param_name] = kwargs.get('state_history', [])
                                elif param_name == 'kwargs':
                                    func_args[param_name] = all_params
                            
                            result = control_func(**func_args)
                            return result, {
                                'success': False,
                                'message': error_msg,
                                'source': 'default_fallback',
                                'used_fallback': True,
                                'controller_params': all_params
                            }
                        except Exception as fallback_error:
                            print(f"❌ Erreur même avec fallback: {fallback_error}")
                
                # Si tout échoue, retourner une sortie nulle
                return 0, {
                    'success': False,
                    'message': error_msg,
                    'source': 'error',
                    'used_fallback': False
                }
    
    def get_user_codes(self, user_id: str, connection_id: str) -> Dict[str, Any]:
        """Récupère tous les codes d'un utilisateur pour une connexion"""
        with self.lock:
            user_key = f"user_{user_id}_{connection_id}"
            
            if user_key not in self.user_codes:
                return {
                    'success': True,
                    'codes': {},
                    'message': 'Aucun code personnalisé'
                }
            
            # Formater les données pour l'affichage
            formatted_codes = {}
            for code_type, code_info in self.user_codes[user_key].items():
                formatted_codes[code_type] = {
                    'name': code_info['name'],
                    'description': code_info['description'],
                    'is_active': code_info['is_active'],
                    'created_at': code_info['created_at'],
                    'last_modified': code_info['last_modified'],
                    'execution_count': code_info.get('execution_count', 0),
                    'code_preview': code_info['code'][:200] + 
                                   ('...' if len(code_info['code']) > 200 else ''),
                    'code_length': len(code_info['code']),
                    'code_hash': code_info.get('code_hash')
                }
            
            return {
                'success': True,
                'codes': formatted_codes,
                'count': len(formatted_codes)
            }
    
    def delete_user_code(self, user_id: str, connection_id: str, code_type: str) -> Dict[str, Any]:
        """Supprime un code personnalisé"""
        with self.lock:
            user_key = f"user_{user_id}_{connection_id}"
            
            if (user_key in self.user_codes and 
                code_type in self.user_codes[user_key]):
                
                deleted_code = self.user_codes[user_key].pop(code_type)
                
                # Si c'était le seul code, supprimer l'entrée
                if not self.user_codes[user_key]:
                    del self.user_codes[user_key]
                
                # Sauvegarder
                self._save_to_file(user_key)
                
                return {
                    'success': True,
                    'message': f'Code {code_type} supprimé',
                    'deleted_name': deleted_code.get('name', 'Code')
                }
            
            return {
                'success': False,
                'message': 'Code non trouvé'
            }
    
    def _save_to_file(self, user_key: str):
        """Sauvegarde les codes utilisateur dans un fichier"""
        try:
            if user_key in self.user_codes:
                filename = f"user_codes_{user_key}.json"
                with open(filename, 'w', encoding='utf-8') as f:
                    data_to_save = {}
                    for code_type, code_info in self.user_codes[user_key].items():
                        data_to_save[code_type] = {
                            'code': code_info['code'],
                            'name': code_info['name'],
                            'description': code_info['description'],
                            'created_at': code_info['created_at'],
                            'last_modified': code_info['last_modified'],
                            'is_active': code_info.get('is_active', False),
                            'user_id': code_info.get('user_id'),
                            'connection_id': code_info.get('connection_id')
                        }
                    
                    json.dump(data_to_save, f, indent=2, ensure_ascii=False)
                
                print(f"💾 Codes sauvegardés pour {user_key}")
        except Exception as e:
            print(f"⚠️ Erreur sauvegarde codes: {e}")
    
    def _load_from_file(self, user_key: str):
        """Charge les codes utilisateur depuis un fichier"""
        try:
            filename = f"user_codes_{user_key}.json"
            with open(filename, 'r', encoding='utf-8') as f:
                loaded_data = json.load(f)
                
                for code_type, code_info in loaded_data.items():
                    if user_key not in self.user_codes:
                        self.user_codes[user_key] = {}
                    
                    self.user_codes[user_key][code_type] = {
                        'code': code_info['code'],
                        'name': code_info['name'],
                        'description': code_info['description'],
                        'created_at': code_info['created_at'],
                        'last_modified': code_info['last_modified'],
                        'is_active': code_info.get('is_active', False),
                        'user_id': code_info.get('user_id'),
                        'connection_id': code_info.get('connection_id'),
                        'code_hash': hashlib.md5(code_info['code'].encode()).hexdigest()[:8],
                        'execution_count': 0,
                        'last_execution': None
                    }
                
                print(f"📂 Codes chargés pour {user_key}")
        except FileNotFoundError:
            pass  # Fichier non trouvé, c'est normal
        except Exception as e:
            print(f"⚠️ Erreur chargement codes: {e}")
    
    def reset_to_default(self, user_id: str, connection_id: str, code_type: str) -> Dict[str, Any]:
        """Réinitialise à la configuration par défaut"""
        with self.lock:
            user_key = f"user_{user_id}_{connection_id}"
            
            # Désactiver tout code personnalisé
            if (user_key in self.user_codes and 
                code_type in self.user_codes[user_key]):
                self.user_codes[user_key][code_type]['is_active'] = False
                self._save_to_file(user_key)
            
            print(f"🔄 Code {code_type} réinitialisé aux paramètres par défaut pour utilisateur {user_id}")
            
            return {
                'success': True,
                'message': f'Code {code_type} réinitialisé aux paramètres par défaut',
                'is_active': False,
                'source': 'default'
            }
    
    def get_controller_params_for_test(self, connection_id: str, code_type: str) -> Dict[str, Any]:
        """API pour obtenir les paramètres actuels pour le frontend"""
        try:
            params = self._get_actual_controller_params(connection_id, code_type)
            return {
                'success': True,
                'params': params,
                'code_type': code_type,
                'connection_id': connection_id
            }
        except Exception as e:
            return {
                'success': False,
                'message': str(e),
                'params': {}
            }
    
    def get_all_user_codes(self, user_id: str) -> Dict[str, Any]:
        """Récupère tous les codes d'un utilisateur (toutes connexions)"""
        with self.lock:
            user_codes = {}
            
            for user_key, codes in self.user_codes.items():
                if user_key.startswith(f"user_{user_id}_"):
                    # Extraire l'ID de connexion de la clé
                    connection_id = user_key.replace(f"user_{user_id}_", "", 1)
                    
                    user_codes[connection_id] = {}
                    for code_type, code_info in codes.items():
                        user_codes[connection_id][code_type] = {
                            'name': code_info['name'],
                            'description': code_info['description'],
                            'is_active': code_info['is_active'],
                            'created_at': code_info['created_at'],
                            'last_modified': code_info['last_modified']
                        }
            
            return {
                'success': True,
                'codes': user_codes,
                'count': len(user_codes)
            }

# Instance globale
custom_code_manager = CustomCodeManager()