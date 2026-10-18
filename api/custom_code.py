# api/custom_code.py - Routes API pour le code personnalisé
from flask import jsonify, request, session
from utils.decorators import login_required
import sys
import os

def register_custom_code_routes(app, arduino_controller):
    """Enregistre toutes les routes API pour le code personnalisé"""
    
    # Import du gestionnaire de code personnalisé
    try:
        from controllers.code_personnalise import custom_code_manager
        # Lier le contrôleur Arduino au CustomCodeManager
        custom_code_manager.set_arduino_controller(arduino_controller)
        print("✅ CustomCodeManager chargé et lié à ArduinoController")
    except ImportError as e:
        print(f"❌ Erreur chargement CustomCodeManager: {e}")
        return
    
    @app.route('/api/custom_code/save', methods=['POST'])
    @login_required
    def save_custom_code():
        """API pour sauvegarder un code personnalisé avec ID utilisateur"""
        try:
            donnees = request.json
            connection_id = donnees.get('connection_id')
            code_type = donnees.get('code_type')  # 'pi', 'pid', 'mpc'
            code = donnees.get('code')
            name = donnees.get('name', 'Code personnalisé')
            description = donnees.get('description', '')
            
            # Récupérer l'ID utilisateur depuis la session
            user_id = session.get('user_id')
            
            if not all([user_id, connection_id, code_type, code]):
                return jsonify({
                    'success': False,
                    'message': 'Données manquantes (user_id, connection_id, code_type, code requis)'
                })
            
            result = custom_code_manager.save_user_code(
                user_id, connection_id, code_type, code, name, description
            )
            
            return jsonify(result)
            
        except Exception as e:
            print(f"❌ Erreur sauvegarde code personnalisé: {e}")
            return jsonify({
                'success': False,
                'message': f'Erreur: {str(e)}'
            })
    
    @app.route('/api/custom_code/activate', methods=['POST'])
    @login_required
    def activate_custom_code():
        """API pour activer un code personnalisé"""
        try:
            donnees = request.json
            connection_id = donnees.get('connection_id')
            code_type = donnees.get('code_type')
            
            # Récupérer l'ID utilisateur depuis la session
            user_id = session.get('user_id')
            
            if not all([user_id, connection_id, code_type]):
                return jsonify({
                    'success': False,
                    'message': 'Données manquantes (user_id requis)'
                })
            
            result = custom_code_manager.activate_user_code(user_id, connection_id, code_type)
            
            return jsonify(result)
            
        except Exception as e:
            print(f"❌ Erreur activation code: {e}")
            return jsonify({
                'success': False,
                'message': f'Erreur: {str(e)}'
            })
    
    @app.route('/api/custom_code/deactivate', methods=['POST'])
    @login_required
    def deactivate_custom_code():
        """API pour désactiver un code personnalisé"""
        try:
            donnees = request.json
            connection_id = donnees.get('connection_id')
            code_type = donnees.get('code_type')
            
            # Récupérer l'ID utilisateur depuis la session
            user_id = session.get('user_id')
            
            if not all([user_id, connection_id, code_type]):
                return jsonify({
                    'success': False,
                    'message': 'Données manquantes'
                })
            
            result = custom_code_manager.deactivate_user_code(user_id, connection_id, code_type)
            
            return jsonify(result)
            
        except Exception as e:
            print(f"❌ Erreur désactivation code: {e}")
            return jsonify({
                'success': False,
                'message': f'Erreur: {str(e)}'
            })
    
    @app.route('/api/custom_code/execute', methods=['POST'])
    @login_required
    def execute_custom_code():
        """API pour exécuter un code personnalisé (test avec paramètres actuels)"""
        try:
            donnees = request.json
            connection_id = donnees.get('connection_id')
            code_type = donnees.get('code_type')
            user_id = session.get('user_id')
            
            if not all([user_id, connection_id, code_type]):
                return jsonify({
                    'success': False,
                    'message': 'Données manquantes'
                })
            
            print(f"🔧 Exécution code personnalisé {code_type} pour {connection_id} (user: {user_id})")
            
            # Extraire les paramètres d'entrée de base
            inputs = {}
            for key in ['error', 'dt', 'last_error', 'integral_state', 'state_history']:
                if key in donnees:
                    inputs[key] = donnees[key]
            
            # Récupérer les paramètres actuels du contrôleur
            controller_params = custom_code_manager._get_actual_controller_params(connection_id, code_type)
            inputs.update(controller_params)
            
            print(f"📤 Paramètres envoyés à execute_control_code: {inputs}")
            
            # Exécuter le code avec l'ID utilisateur
            result, metadata = custom_code_manager.execute_control_code(
                user_id=user_id, 
                connection_id=connection_id, 
                code_type=code_type, 
                **inputs
            )
            
            return jsonify({
                'success': metadata['success'],
                'result': result,
                'metadata': metadata,
                'message': metadata.get('message', 'Exécution réussie'),
                'controller_params': metadata.get('controller_params', {})
            })
            
        except Exception as e:
            print(f"❌ Erreur exécution code: {e}")
            import traceback
            traceback.print_exc()
            return jsonify({
                'success': False,
                'result': 0,
                'message': f'Erreur: {str(e)}'
            })
    
    @app.route('/api/custom_code/list', methods=['GET'])
    @login_required
    def list_custom_codes():
        """API pour lister les codes personnalisés d'un utilisateur"""
        try:
            connection_id = request.args.get('connection_id')
            user_id = session.get('user_id')
            
            if not all([user_id, connection_id]):
                return jsonify({
                    'success': False,
                    'message': 'user_id et connection_id requis'
                })
            
            result = custom_code_manager.get_user_codes(user_id, connection_id)
            
            return jsonify(result)
            
        except Exception as e:
            print(f"❌ Erreur liste codes: {e}")
            return jsonify({
                'success': False,
                'message': f'Erreur: {str(e)}'
            })
    
    @app.route('/api/custom_code/delete', methods=['DELETE'])
    @login_required
    def delete_custom_code():
        """API pour supprimer un code personnalisé"""
        try:
            donnees = request.json
            connection_id = donnees.get('connection_id')
            code_type = donnees.get('code_type')
            user_id = session.get('user_id')
            
            if not all([user_id, connection_id, code_type]):
                return jsonify({
                    'success': False,
                    'message': 'Données manquantes'
                })
            
            result = custom_code_manager.delete_user_code(user_id, connection_id, code_type)
            
            return jsonify(result)
            
        except Exception as e:
            print(f"❌ Erreur suppression code: {e}")
            return jsonify({
                'success': False,
                'message': f'Erreur: {str(e)}'
            })
    
    @app.route('/api/custom_code/reset', methods=['POST'])
    @login_required
    def reset_custom_code():
        """API pour réinitialiser à la configuration par défaut"""
        try:
            donnees = request.json
            connection_id = donnees.get('connection_id')
            code_type = donnees.get('code_type')
            user_id = session.get('user_id')
            
            if not all([user_id, connection_id, code_type]):
                return jsonify({
                    'success': False,
                    'message': 'Données manquantes'
                })
            
            result = custom_code_manager.reset_to_default(user_id, connection_id, code_type)
            
            return jsonify(result)
            
        except Exception as e:
            print(f"❌ Erreur réinitialisation: {e}")
            return jsonify({
                'success': False,
                'message': f'Erreur: {str(e)}'
            })
    
    @app.route('/api/custom_code/default_examples', methods=['GET'])
    @login_required
    def get_default_examples():
        """API pour obtenir les exemples de code par défaut"""
        try:
            code_type = request.args.get('code_type')
            
            if code_type and code_type in custom_code_manager.default_codes:
                example = custom_code_manager.default_codes[code_type].copy()
                example['code_type'] = code_type
                return jsonify({
                    'success': True,
                    'example': example
                })
            
            # Retourner tous les exemples
            return jsonify({
                'success': True,
                'examples': custom_code_manager.default_codes
            })
            
        except Exception as e:
            print(f"❌ Erreur récupération exemples: {e}")
            return jsonify({
                'success': False,
                'message': f'Erreur: {str(e)}'
            })
    
    @app.route('/api/custom_code/validate', methods=['POST'])
    @login_required
    def validate_custom_code():
        """API pour valider la syntaxe et la sécurité d'un code"""
        try:
            donnees = request.json
            code = donnees.get('code', '')
            
            if not code:
                return jsonify({
                    'success': False,
                    'message': 'Code vide'
                })
            
            is_valid, message = custom_code_manager.validate_code_security(code)
            
            return jsonify({
                'success': is_valid,
                'message': message,
                'is_valid': is_valid
            })
            
        except Exception as e:
            print(f"❌ Erreur validation code: {e}")
            return jsonify({
                'success': False,
                'message': f'Erreur: {str(e)}',
                'is_valid': False
            })
    
    @app.route('/api/custom_code/status', methods=['GET'])
    @login_required
    def get_custom_code_status():
        """API pour obtenir le statut du code personnalisé"""
        try:
            connection_id = request.args.get('connection_id')
            code_type = request.args.get('code_type')
            user_id = session.get('user_id')
            
            if not all([user_id, connection_id, code_type]):
                return jsonify({
                    'success': False,
                    'message': 'Paramètres manquants'
                })
            
            code_info = custom_code_manager.get_active_code(user_id, connection_id, code_type)
            
            if code_info:
                return jsonify({
                    'success': True,
                    'is_active': code_info.get('is_active', False),
                    'is_custom': code_info.get('is_custom', False),
                    'source': code_info.get('source', 'default'),
                    'name': code_info.get('name', 'Code par défaut'),
                    'code_hash': code_info.get('code_hash'),
                    'controller_params': code_info.get('controller_params', {})
                })
            
            return jsonify({
                'success': True,
                'is_active': False,
                'is_custom': False,
                'source': 'default',
                'name': 'Code par défaut',
                'controller_params': {}
            })
            
        except Exception as e:
            print(f"❌ Erreur statut code: {e}")
            return jsonify({
                'success': False,
                'message': f'Erreur: {str(e)}'
            })
    
    @app.route('/api/custom_code/get_controller_params', methods=['GET'])
    @login_required
    def get_controller_params():
        """API pour obtenir les paramètres actuels du contrôleur"""
        try:
            connection_id = request.args.get('connection_id')
            code_type = request.args.get('code_type')
            
            if not connection_id or not code_type:
                return jsonify({
                    'success': False,
                    'message': 'Paramètres manquants'
                })
            
            result = custom_code_manager.get_controller_params_for_test(connection_id, code_type)
            
            return jsonify(result)
            
        except Exception as e:
            print(f"❌ Erreur récupération paramètres contrôleur: {e}")
            return jsonify({
                'success': False,
                'message': f'Erreur: {str(e)}',
                'params': {}
            })
    
    @app.route('/api/custom_code/test_with_params', methods=['POST'])
    @login_required
    def test_code_with_params():
        """API pour tester un code avec des paramètres spécifiques"""
        try:
            donnees = request.json
            code = donnees.get('code', '')
            code_type = donnees.get('code_type', 'pi')
            test_params = donnees.get('params', {})
            
            if not code:
                return jsonify({
                    'success': False,
                    'message': 'Code vide'
                })
            
            # Valider la sécurité du code
            is_valid, message = custom_code_manager.validate_code_security(code)
            if not is_valid:
                return jsonify({
                    'success': False,
                    'message': f'Code non sécurisé: {message}'
                })
            
            # Préparer l'environnement de test
            exec_globals = custom_code_manager.sandbox_globals.copy()
            
            # Ajouter les paramètres de test
            exec_globals.update(test_params)
            
            # Ajouter les paramètres par défaut selon le type de code
            defaults = {
                'pi': {'kp': 1.5, 'ki': 0.05, 'setpoint': 25.0},
                'pid': {'kp': 2.0, 'ki': 0.08, 'kd': 0.1, 'setpoint': 25.0},
                'mpc': {'kp': 2.0, 'ki': 0.05, 'setpoint': 25.0, 'prediction_horizon': 5, 'control_horizon': 2}
            }
            
            if code_type in defaults:
                for key, value in defaults[code_type].items():
                    if key not in exec_globals:
                        exec_globals[key] = value
            
            # Exécuter le code
            try:
                code_obj = compile(code, '<test_code>', 'exec')
                exec(code_obj, exec_globals)
                
                if 'control' not in exec_globals:
                    return jsonify({
                        'success': False,
                        'message': "La fonction 'control' n'est pas définie dans le code"
                    })
                
                # Tester avec des valeurs par défaut
                control_func = exec_globals['control']
                
                # Préparer les arguments de test
                test_inputs = {
                    'error': 2.0,
                    'dt': 0.1,
                    'last_error': 1.5,
                    'integral_state': 0.0,
                    'state_history': []
                }
                
                # Ajouter les paramètres spécifiques
                import inspect
                sig = inspect.signature(control_func)
                
                func_args = {}
                for param_name in sig.parameters:
                    if param_name in test_params:
                        func_args[param_name] = test_params[param_name]
                    elif param_name in test_inputs:
                        func_args[param_name] = test_inputs[param_name]
                    elif param_name == 'kwargs':
                        func_args[param_name] = {**test_params, **test_inputs}
                
                result = control_func(**func_args)
                
                return jsonify({
                    'success': True,
                    'result': result,
                    'message': 'Test réussi',
                    'used_params': {**test_params, **defaults.get(code_type, {})}
                })
                
            except Exception as e:
                return jsonify({
                    'success': False,
                    'message': f'Erreur d\'exécution: {str(e)}'
                })
            
        except Exception as e:
            print(f"❌ Erreur test code: {e}")
            return jsonify({
                'success': False,
                'message': f'Erreur: {str(e)}'
            })
    
    @app.route('/api/custom_code/get_user_code', methods=['GET'])
    @login_required
    def get_user_custom_code():
        """API pour récupérer le code personnalisé d'un utilisateur"""
        try:
            connection_id = request.args.get('connection_id')
            code_type = request.args.get('code_type')
            user_id = session.get('user_id')
            
            if not all([user_id, connection_id, code_type]):
                return jsonify({
                    'success': False,
                    'message': 'Paramètres manquants'
                })
            
            # Vérifier si l'utilisateur a un code sauvegardé
            user_key = f"user_{user_id}_{connection_id}"
            
            if (user_key in custom_code_manager.user_codes and 
                code_type in custom_code_manager.user_codes[user_key]):
                
                code_info = custom_code_manager.user_codes[user_key][code_type]
                
                return jsonify({
                    'success': True,
                    'code': code_info['code'],
                    'name': code_info['name'],
                    'description': code_info['description'],
                    'code_hash': code_info['code_hash'],
                    'is_active': code_info['is_active'],
                    'created_at': code_info['created_at'],
                    'last_modified': code_info['last_modified']
                })
            
            return jsonify({
                'success': True,
                'code': None,
                'message': 'Aucun code personnalisé trouvé'
            })
            
        except Exception as e:
            print(f"❌ Erreur récupération code utilisateur: {e}")
            return jsonify({
                'success': False,
                'message': f'Erreur: {str(e)}'
            })