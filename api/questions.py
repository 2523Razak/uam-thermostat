# questions.py
from flask import jsonify, request, session, current_app, url_for, send_from_directory
from datetime import datetime, timedelta
import os
from werkzeug.utils import secure_filename
from db import db, TP, Question, ReponseEtudiant, Utilisateur,EtudiantTP
from utils.decorators import login_required
from controllers.notification_manager import envoyer_notifications_tp_complete, envoyer_notifications_tp_modifie

# Configuration pour les uploads
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def ensure_upload_folders():
    """S'assurer que les dossiers d'upload existent (uploads/questions)"""
    try:
        app_root = current_app.root_path
        upload_folder = os.path.join(app_root, 'uploads', 'questions')
        
        os.makedirs(upload_folder, exist_ok=True)
        print(f"✅ Dossier upload vérifié: {upload_folder}")
        return True
            
    except Exception as e:
        print(f"❌ Erreur création dossiers: {e}")
        return False

def clean_old_images():
    """Nettoyer les anciennes images (plus vieilles que 1 an)"""
    try:
        app_root = current_app.root_path
        upload_folder = os.path.join(app_root, 'uploads', 'questions')
        
        if not os.path.exists(upload_folder):
            return
        
        deleted_count = 0
        current_time = datetime.now()
        one_year_ago = current_time - timedelta(days=365)
        
        for filename in os.listdir(upload_folder):
            file_path = os.path.join(upload_folder, filename)
            
            if os.path.isfile(file_path):
                try:
                    mod_time = datetime.fromtimestamp(os.path.getmtime(file_path))
                    
                    if mod_time < one_year_ago:
                        os.remove(file_path)
                        deleted_count += 1
                        print(f"🗑️  Supprimé image ancienne ({mod_time.strftime('%Y-%m-%d')}): {filename}")
                        
                except Exception as e:
                    print(f"⚠️  Erreur traitement fichier {filename}: {e}")
        
        if deleted_count > 0:
            print(f"✅ Nettoyage terminé: {deleted_count} images supprimées")
                    
    except Exception as e:
        print(f"⚠️  Erreur nettoyage images: {e}")

def register_question_routes(app):
    """Enregistrer toutes les routes liées aux questions"""
    
    @app.route('/uploads/questions/<filename>')
    def serve_question_image(filename):
        """Servir les images des questions depuis uploads/questions"""
        try:
            from flask import send_from_directory
            uploads_path = os.path.join(current_app.root_path, 'uploads', 'questions')
            
            file_path = os.path.join(uploads_path, filename)
            if not os.path.exists(file_path):
                print(f"❌ Image non trouvée: {filename}")
                return "Image non trouvée", 404
            
            print(f"✅ Image servie: {filename}")
            return send_from_directory(uploads_path, filename)
            
        except Exception as e:
            print(f"❌ Erreur service image {filename}: {e}")
            return str(e), 500
    
    @app.route('/api/tp/<int:tp_id>/upload_question_image', methods=['POST'])
    @login_required
    def upload_question_image(tp_id):
        """API pour uploader une image pour une question"""
        try:
            print(f"📤 Début upload image pour TP {tp_id}")
            
            if 'image' not in request.files:
                return jsonify({'success': False, 'message': 'Aucun fichier'}), 400
            
            file = request.files['image']
            
            if file.filename == '':
                return jsonify({'success': False, 'message': 'Aucun fichier sélectionné'}), 400
            
            if not allowed_file(file.filename):
                return jsonify({'success': False, 'message': 'Format non supporté. Utilisez JPG, PNG ou GIF'}), 400
            
            file.seek(0, os.SEEK_END)
            size = file.tell()
            file.seek(0)
            
            if size > MAX_FILE_SIZE:
                return jsonify({'success': False, 'message': 'Fichier trop volumineux (max 5MB)'}), 400
            
            tp = db.session.get(TP, tp_id)
            if not tp:
                return jsonify({'success': False, 'message': 'TP non trouvé'}), 404
            
            if tp.created_by != session.get('user_id'):
                return jsonify({'success': False, 'message': 'Non autorisé'}), 403
            
            if not ensure_upload_folders():
                return jsonify({'success': False, 'message': 'Erreur de configuration des dossiers'}), 500
            
            clean_old_images()
            
            filename = secure_filename(file.filename)
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
            unique_filename = f"{tp_id}_{timestamp}_{filename}"
            
            app_root = current_app.root_path
            upload_folder = os.path.join(app_root, 'uploads', 'questions')
            file_path = os.path.join(upload_folder, unique_filename)
            
            print(f"💾 Sauvegarde dans: {file_path}")
            
            file.save(file_path)
            
            if not os.path.exists(file_path):
                return jsonify({'success': False, 'message': 'Erreur de sauvegarde du fichier'}), 500
            
            saved_size = os.path.getsize(file_path)
            print(f"📏 Taille sauvegardée: {saved_size} bytes")
            
            image_url = f"/uploads/questions/{unique_filename}"
            
            print(f"✅ Image sauvegardée avec succès: {unique_filename}")
            print(f"🌐 URL: {image_url}")
            
            return jsonify({
                'success': True,
                'message': 'Image uploadée avec succès',
                'image_url': image_url,
                'filename': unique_filename,
                'file_size': saved_size
            })
            
        except Exception as e:
            print(f"❌ Erreur upload image: {e}")
            import traceback
            traceback.print_exc()
            return jsonify({'success': False, 'message': f'Erreur: {str(e)}'}), 500
    
    @app.route('/api/tp/<int:tp_id>/questions', methods=['GET', 'POST'])
    @login_required
    def gestion_questions_api(tp_id):
        """API pour gérer les questions d'un TP"""
        try:
            if request.method == 'GET':
                questions = Question.query.filter_by(tp_id=tp_id).order_by(Question.ordre).all()
                
                questions_data = []
                for q in questions:
                    image_exists = False
                    if q.image_url:
                        filename = q.image_url.split('/')[-1]
                        app_root = current_app.root_path
                        file_path = os.path.join(app_root, 'uploads', 'questions', filename)
                        image_exists = os.path.exists(file_path)
                        
                        if not image_exists:
                            print(f"⚠️  Image manquante dans le système de fichiers: {filename}")
                        else:
                            print(f"✅ Image trouvée: {filename}")
                    
                    questions_data.append({
                        'id': q.id,
                        'enonce': q.enonce,
                        'texte': q.enonce,
                        'type_question': q.type_question,
                        'type': q.type_question,
                        'points': float(q.points) if q.points else 1.0,
                        'ordre': q.ordre,
                        'reponse_correcte': q.reponse_correcte,
                        'image_url': q.image_url if image_exists else None
                    })
                
                print(f"📥 Envoi de {len(questions_data)} questions au frontend")
                return jsonify({
                    'success': True,
                    'questions': questions_data,
                    'count': len(questions_data)
                })
                
            elif request.method == 'POST':
                data = request.get_json()
                
                if not data:
                    return jsonify({'success': False, 'message': 'Aucune donnée reçue'}), 400
                
                questions = data.get('questions', [])
                
                tp = db.session.get(TP, tp_id)
                if not tp:
                    return jsonify({'success': False, 'message': 'TP non trouvé'}), 404
                
                if tp.created_by != session.get('user_id'):
                    return jsonify({'success': False, 'message': 'Non autorisé'}), 403
                
                print(f"📝 Sauvegarde de {len(questions)} questions pour TP {tp_id}")
                print("=" * 50)
                
                existing_questions = Question.query.filter_by(tp_id=tp_id).order_by(Question.ordre).all()
                existing_images = {}
                for i, eq in enumerate(existing_questions):
                    if eq.image_url:
                        existing_images[i] = eq.image_url
                        print(f"📸 Question {i} existante a l'image: {eq.image_url}")
                
                deleted_count = Question.query.filter_by(tp_id=tp_id).delete()
                print(f"🗑️  {deleted_count} anciennes questions supprimées")
                
                questions_ids = []
                for i, q_data in enumerate(questions):
                    type_question = q_data.get('type_question', 'qcm')
                    
                    if type_question not in ['qcm', 'ouverte', 'case_cocher', 'image_reponse', 'image_question']:
                        type_question = 'qcm'
                    
                    image_url = q_data.get('image_url', None)
                    
                    if not image_url and i in existing_images:
                        image_url = existing_images[i]
                        print(f"🔄 Conservation de l'image existante pour question {i}: {image_url}")
                    
                    question = Question(
                        tp_id=tp_id,
                        enonce=q_data.get('texte', q_data.get('enonce', '')),
                        type_question=type_question,
                        points=float(q_data.get('points', 1.0)),
                        ordre=q_data.get('ordre', i),
                        reponse_correcte=q_data.get('reponse_correcte', ''),
                        image_url=image_url
                    )
                    
                    db.session.add(question)
                    db.session.flush()
                    questions_ids.append(question.id)
                    
                    print(f"📝 Question {i} créée: type={type_question}, image={'oui' if image_url else 'non'}")
                
                tp.nombre_questions = len(questions)
                
                db.session.commit()
                
                print(f"✅ {len(questions)} questions créées avec succès pour TP {tp_id}")
                print("=" * 50)
                
                professeur = db.session.get(Utilisateur, session.get('user_id'))
                nombre_notifications = 0
                
                if len(questions) > 0:
                    if deleted_count <= 0:
                        nombre_notifications = envoyer_notifications_tp_complete(tp, professeur, db)
                        print(f"🔔 Notifications envoyées (nouveau TP): {nombre_notifications}")
                    else:
                        nombre_notifications = envoyer_notifications_tp_modifie(tp, professeur, db)
                        print(f"🔔 Notifications envoyées (TP modifié): {nombre_notifications}")
                
                return jsonify({
                    'success': True,
                    'message': f'{len(questions)} question(s) enregistrée(s) avec succès. {nombre_notifications} étudiants notifiés.',
                    'count': len(questions),
                    'questions_ids': questions_ids,
                    'notifications_envoyees': nombre_notifications
                })
                
        except Exception as e:
            db.session.rollback()
            print(f"❌ Erreur dans gestion_questions_api: {e}")
            import traceback
            traceback.print_exc()
            return jsonify({
                'success': False,
                'message': f'Erreur: {str(e)}'
            }), 500
    
    @app.route('/tp/<int:tp_id>/questions', methods=['GET'])
    @login_required
    def charger_questions_tp(tp_id):
        """Charger les questions d'un TP (AJAX)"""
        try:
            questions = Question.query.filter_by(tp_id=tp_id).order_by(Question.ordre).all()
            
            questions_data = []
            for q in questions:
                image_exists = False
                if q.image_url:
                    filename = q.image_url.split('/')[-1]
                    app_root = current_app.root_path
                    file_path = os.path.join(app_root, 'uploads', 'questions', filename)
                    image_exists = os.path.exists(file_path)
                
                questions_data.append({
                    'id': q.id,
                    'texte': q.enonce,
                    'type_question': q.type_question,
                    'type': q.type_question,
                    'points': float(q.points) if q.points else 1.0,
                    'ordre': q.ordre,
                    'reponse_correcte': q.reponse_correcte,
                    'image_url': q.image_url if image_exists else None
                })
            
            print(f"📤 Envoi de {len(questions_data)} questions via charger_questions_tp")
            return jsonify({
                'success': True,
                'questions': questions_data,
                'count': len(questions_data)
            })
        except Exception as e:
            print(f"❌ Erreur charger_questions_tp: {e}")
            return jsonify({'success': False, 'message': 'Erreur serveur'}), 500
    
    @app.route('/tp/<int:tp_id>/reponses_existantes', methods=['GET'])
    @login_required
    def reponses_existantes_tp(tp_id):
        """Récupérer les réponses existantes (AJAX)"""
        try:
            etudiant_id = session.get('user_id')
            
            reponses = ReponseEtudiant.query.filter_by(
                tp_id=tp_id,
                etudiant_id=etudiant_id
            ).all()
            
            reponses_data = []
            for r in reponses:
                reponses_data.append({
                    'question_id': r.question_id,
                    'reponse': r.reponse
                })
            
            return jsonify({
                'success': True,
                'reponses': reponses_data,
                'count': len(reponses_data)
            })
        except Exception as e:
            print(f"❌ Erreur reponses_existantes_tp: {e}")
            return jsonify({'success': False, 'message': 'Erreur serveur'}), 500
    
    @app.route('/tp/<int:tp_id>/creer_questions', methods=['POST'])
    @login_required
    def creer_questions(tp_id):
        """Créer des questions pour un TP (AJAX)"""
        try:
            data = request.get_json()
            
            if not data:
                return jsonify({'success': False, 'message': 'Aucune donnée reçue'}), 400
            
            questions = data.get('questions', [])
            
            tp = db.session.get(TP, tp_id)
            if not tp:
                return jsonify({'success': False, 'message': 'TP non trouvé'}), 404
            
            if tp.created_by != session.get('user_id'):
                return jsonify({'success': False, 'message': 'Non autorisé'}), 403
            
            print(f"📝 Création de {len(questions)} questions pour TP {tp_id}")
            
            existing_questions = Question.query.filter_by(tp_id=tp_id).order_by(Question.ordre).all()
            existing_images = {}
            for i, eq in enumerate(existing_questions):
                if eq.image_url:
                    existing_images[i] = eq.image_url
            
            Question.query.filter_by(tp_id=tp_id).delete()
            
            questions_ids = []
            for i, q_data in enumerate(questions):
                type_question = q_data.get('type_question', 'qcm')
                
                if type_question not in ['qcm', 'ouverte', 'case_cocher', 'image_reponse', 'image_question']:
                    type_question = 'qcm'
                
                image_url = q_data.get('image_url', None)
                if not image_url and i in existing_images:
                    image_url = existing_images[i]
                
                question = Question(
                    tp_id=tp_id,
                    enonce=q_data.get('texte', q_data.get('enonce', '')),
                    type_question=type_question,
                    points=float(q_data.get('points', 1.0)),
                    ordre=q_data.get('ordre', i),
                    reponse_correcte=q_data.get('reponse_correcte', ''),
                    image_url=image_url
                )
                
                db.session.add(question)
                db.session.flush()
                questions_ids.append(question.id)
            
            tp.nombre_questions = len(questions)
            
            db.session.commit()
            
            print(f"✅ {len(questions)} questions créées avec succès pour TP {tp_id}")
            
            professeur = db.session.get(Utilisateur, session.get('user_id'))
            nombre_notifications = 0
            
            if len(questions) > 0:
                anciennes_questions = len(existing_questions)
                if anciennes_questions <= 0:
                    nombre_notifications = envoyer_notifications_tp_complete(tp, professeur, db)
                else:
                    nombre_notifications = envoyer_notifications_tp_modifie(tp, professeur, db)
            
            return jsonify({
                'success': True,
                'message': f'{len(questions)} question(s) enregistrée(s) avec succès. {nombre_notifications} étudiants notifiés.',
                'count': len(questions),
                'questions_ids': questions_ids,
                'notifications_envoyees': nombre_notifications
            })
            
        except Exception as e:
            db.session.rollback()
            print(f"❌ Erreur dans creer_questions: {e}")
            import traceback
            traceback.print_exc()
            return jsonify({
                'success': False,
                'message': f'Erreur: {str(e)}'
            }), 500
    
    @app.route('/api/tp/<int:tp_id>/questions/sauvegarder', methods=['POST'])
    @login_required
    def sauvegarder_questions(tp_id):
        """API alternative pour sauvegarder les questions"""
        try:
            data = request.get_json()
            
            if not data:
                return jsonify({'success': False, 'message': 'Aucune donnée reçue'}), 400
            
            questions = data.get('questions', [])
            
            tp = db.session.get(TP, tp_id)
            if not tp:
                return jsonify({'success': False, 'message': 'TP non trouvé'}), 404
            
            if tp.created_by != session.get('user_id'):
                return jsonify({'success': False, 'message': 'Non autorisé'}), 403
            
            existing_questions = Question.query.filter_by(tp_id=tp_id).order_by(Question.ordre).all()
            existing_images = {}
            for i, eq in enumerate(existing_questions):
                if eq.image_url:
                    existing_images[i] = eq.image_url
            
            Question.query.filter_by(tp_id=tp_id).delete()
            
            for i, q_data in enumerate(questions):
                image_url = q_data.get('image_url', None)
                if not image_url and i in existing_images:
                    image_url = existing_images[i]
                
                question = Question(
                    tp_id=tp_id,
                    enonce=q_data.get('enonce', ''),
                    type_question=q_data.get('type_question', 'qcm'),
                    points=float(q_data.get('points', 1.0)),
                    ordre=q_data.get('ordre', i),
                    reponse_correcte=q_data.get('reponse_correcte', ''),
                    image_url=image_url
                )
                db.session.add(question)
            
            tp.nombre_questions = len(questions)
            
            db.session.commit()
            
            professeur = db.session.get(Utilisateur, session.get('user_id'))
            nombre_notifications = envoyer_notifications_tp_complete(tp, professeur, db)
            
            return jsonify({
                'success': True,
                'message': f'{len(questions)} question(s) sauvegardée(s) avec succès. {nombre_notifications} étudiants notifiés.',
                'count': len(questions)
            })
            
        except Exception as e:
            db.session.rollback()
            print(f"❌ Erreur dans sauvegarder_questions: {e}")
            return jsonify({
                'success': False,
                'message': f'Erreur: {str(e)}'
            }), 500
    
    # Route pour uploader une image de réponse
    @app.route('/api/tp/<int:tp_id>/upload_reponse_image', methods=['POST'])
    @login_required
    def upload_reponse_image(tp_id):
        try:
            question_id = request.form.get('question_id')
            file = request.files.get('file')
            etudiant_id = session.get('user_id')
            reponse_texte = request.form.get('reponse_texte', '')
            
            print(f"\n📤 Début upload réponse image pour TP {tp_id}, Question {question_id}")
            print(f"👤 Étudiant ID: {etudiant_id}")
            print(f"📝 Commentaire reçu: '{reponse_texte}'")
            print(f"📁 Fichier reçu: {file.filename if file else 'Aucun'}")
            
            if not file or not question_id:
                print("❌ Fichier ou question manquant")
                return jsonify({'success': False, 'message': 'Fichier ou question manquant'}), 400
            
            if not allowed_file(file.filename):
                print(f"❌ Format non supporté: {file.filename}")
                return jsonify({'success': False, 'message': 'Format non supporté. Utilisez PNG, JPG, JPEG, GIF'}), 400
            
            file.seek(0, os.SEEK_END)
            size = file.tell()
            file.seek(0)
            
            if size > 16 * 1024 * 1024:
                print(f"❌ Fichier trop volumineux: {size} bytes")
                return jsonify({'success': False, 'message': 'Fichier trop volumineux (max 16MB)'}), 400
            
            app_root = current_app.root_path
            upload_folder = os.path.join(app_root, 'uploads', 'tp_responses', str(tp_id))
            print(f"📁 Dossier destination: {upload_folder}")
            
            os.makedirs(upload_folder, exist_ok=True)
            print(f"✅ Dossier créé/vérifié")
            
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
            original_filename = secure_filename(file.filename)
            file_extension = os.path.splitext(original_filename)[1].lower()
            
            unique_filename = f"tp_{tp_id}_etudiant_{etudiant_id}_q{question_id}_{timestamp}{file_extension}"
            file_path = os.path.join(upload_folder, unique_filename)
            
            print(f"💾 Sauvegarde dans: {file_path}")
            
            file.save(file_path)
            
            if not os.path.exists(file_path):
                print(f"❌ Erreur: fichier non créé")
                return jsonify({'success': False, 'message': 'Erreur de sauvegarde du fichier'}), 500
            
            saved_size = os.path.getsize(file_path)
            print(f"✅ Fichier sauvegardé: {unique_filename} ({saved_size} bytes)")
            
            relative_path = os.path.join('tp_responses', str(tp_id), unique_filename)
            image_url = f"/uploads/{relative_path}"
            
            print(f"🌐 URL de l'image: {image_url}")
            print(f"🗂️ Chemin relatif: {relative_path}")
            
            reponse = ReponseEtudiant.query.filter_by(
                tp_id=tp_id,
                question_id=question_id,
                etudiant_id=etudiant_id
            ).first()
            
            if not reponse:
                print("📝 Création nouvelle réponse")
                reponse = ReponseEtudiant(
                    tp_id=tp_id,
                    question_id=question_id,
                    etudiant_id=etudiant_id,
                    reponse=reponse_texte,
                    fichier_path=relative_path,
                    date_soumission=datetime.now()
                )
                db.session.add(reponse)
            else:
                print("📝 Mise à jour réponse existante")
                if reponse.fichier_path:
                    old_path = os.path.join(app_root, 'uploads', reponse.fichier_path)
                    if os.path.exists(old_path):
                        os.remove(old_path)
                        print(f"🗑️ Ancien fichier supprimé: {old_path}")
                
                reponse.reponse = reponse_texte
                reponse.fichier_path = relative_path
                reponse.date_soumission = datetime.now()
            
            db.session.commit()
            print("✅ Base de données mise à jour")
            
            return jsonify({
                'success': True,
                'message': 'Image et commentaire sauvegardés avec succès',
                'image_url': image_url,
                'filename': unique_filename,
                'file_size': saved_size
            })
            
        except Exception as e:
            db.session.rollback()
            print(f"❌ Erreur upload réponse image: {e}")
            import traceback
            traceback.print_exc()
            return jsonify({'success': False, 'message': f'Erreur: {str(e)}'}), 500
    
    @app.route('/uploads/reponses/<int:tp_id>/<filename>')
    def serve_reponse_image(tp_id, filename):
        try:
            uploads_path = os.path.join(current_app.root_path, 'uploads', 'reponses', str(tp_id))
            return send_from_directory(uploads_path, filename)
        except Exception as e:
            print(f"❌ Erreur service image réponse: {e}")
            return "Image non trouvée", 404
    
    @app.route('/tp/<int:tp_id>/soumettre_final', methods=['POST'])
    @login_required
    def soumettre_final(tp_id):
        try:
            data = request.get_json()
            etudiant_id = session.get('user_id')
            
            reponses = ReponseEtudiant.query.filter_by(
                tp_id=tp_id,
                etudiant_id=etudiant_id
            ).all()
            
            for reponse in reponses:
                reponse.est_soumis = True
                reponse.date_soumission_finale = datetime.now()
            
            db.session.commit()
            
            return jsonify({
                'success': True,
                'message': 'TP soumis avec succès',
                'redirect': url_for('liste_tps_etudiant')
            })
            
        except Exception as e:
            db.session.rollback()
            print(f"❌ Erreur soumission finale: {e}")
            return jsonify({'success': False, 'message': str(e)}), 500
    
    @app.route('/tp/<int:tp_id>/soumettre_avec_images', methods=['POST'])
    @login_required
    def soumettre_avec_images(tp_id):
        """Soumettre les réponses avec gestion des fichiers images"""
        try:
            print(f"\n📤 Début soumission avec images pour TP {tp_id}")
            
            etudiant_id = session.get('user_id')
            print(f"👤 Étudiant ID: {etudiant_id}")
            
            tp = db.session.get(TP, tp_id)
            if not tp:
                return jsonify({'success': False, 'message': 'TP non trouvé'}), 404
            
            reponses_existantes = ReponseEtudiant.query.filter_by(
                tp_id=tp_id,
                etudiant_id=etudiant_id
            ).first()
            
            if reponses_existantes and getattr(reponses_existantes, 'est_soumis', False):
                return jsonify({'success': False, 'message': 'Ce TP a déjà été soumis'}), 400
            
            questions_reponse = []
            
            # Parcourir tous les champs du formulaire
            for key in request.form.keys():
                if key.startswith('question_'):
                    parts = key.split('_')
                    if len(parts) >= 3:
                        try:
                            question_id = int(parts[1])
                            champ_type = parts[2]
                        except (ValueError, IndexError):
                            continue
                        
                        question_entry = next((q for q in questions_reponse if q['question_id'] == question_id), None)
                        if not question_entry:
                            question_entry = {
                                'question_id': question_id,
                                'reponse_texte': '',
                                'fichier': None
                            }
                            questions_reponse.append(question_entry)
                        
                        if champ_type == 'reponse':
                            question_entry['reponse_texte'] = request.form[key]
                            print(f"📝 Commentaire pour question {question_id}: '{question_entry['reponse_texte']}'")
            
            # Traiter les fichiers uploadés
            app_root = current_app.root_path
            for key in request.files.keys():
                if key.startswith('question_'):
                    parts = key.split('_')
                    if len(parts) >= 3:
                        try:
                            question_id = int(parts[1])
                        except (ValueError, IndexError):
                            continue
                        
                        question_entry = next((q for q in questions_reponse if q['question_id'] == question_id), None)
                        if not question_entry:
                            question_entry = {
                                'question_id': question_id,
                                'reponse_texte': '',
                                'fichier': None
                            }
                            questions_reponse.append(question_entry)
                        
                        file = request.files[key]
                        if file and file.filename and allowed_file(file.filename):
                            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
                            filename = secure_filename(file.filename)
                            unique_filename = f"tp_{tp_id}_etudiant_{etudiant_id}_q{question_id}_{timestamp}_{filename}"
                            
                            upload_folder = os.path.join(app_root, 'uploads', 'tp_responses', str(tp_id))
                            os.makedirs(upload_folder, exist_ok=True)
                            
                            file_path = os.path.join(upload_folder, unique_filename)
                            file.save(file_path)
                            
                            if os.path.exists(file_path):
                                relative_path = os.path.join('tp_responses', str(tp_id), unique_filename)
                                question_entry['fichier'] = {
                                    'path': relative_path,
                                    'filename': unique_filename,
                                    'size': os.path.getsize(file_path)
                                }
                                print(f"✅ Fichier sauvegardé: {unique_filename}")
            
            print(f"📝 Nombre de questions traitées: {len(questions_reponse)}")
            
            # Sauvegarder les réponses dans la base de données
            for q in questions_reponse:
                reponse = ReponseEtudiant.query.filter_by(
                    tp_id=tp_id,
                    question_id=q['question_id'],
                    etudiant_id=etudiant_id
                ).first()
                
                if not reponse:
                    reponse = ReponseEtudiant(
                        tp_id=tp_id,
                        question_id=q['question_id'],
                        etudiant_id=etudiant_id,
                        reponse=q['reponse_texte'],
                        fichier_path=q['fichier']['path'] if q['fichier'] else None,
                        date_soumission=datetime.now()
                    )
                    db.session.add(reponse)
                    print(f"➕ Nouvelle réponse créée pour question {q['question_id']}")
                else:
                    # CORRECTION: Toujours mettre à jour le commentaire
                    if q['reponse_texte']:
                        reponse.reponse = q['reponse_texte']
                        print(f"✏️ Commentaire mis à jour pour question {q['question_id']}: '{q['reponse_texte']}'")
                    
                    # Mettre à jour le fichier si présent
                    if q['fichier']:
                        if reponse.fichier_path:
                            old_path = os.path.join(app_root, 'uploads', reponse.fichier_path)
                            if os.path.exists(old_path):
                                os.remove(old_path)
                                print(f"🗑️ Ancien fichier supprimé: {reponse.fichier_path}")
                        reponse.fichier_path = q['fichier']['path']
                        print(f"📁 Fichier mis à jour pour question {q['question_id']}")
                    
                    # Toujours mettre à jour la date de soumission
                    reponse.date_soumission = datetime.now()
                
                # Marquer comme soumis
                reponse.est_soumis = True
                reponse.date_soumission_finale = datetime.now()
            
            # Marquer l'inscription comme soumise
            inscription = EtudiantTP.query.filter_by(
                tp_id=tp_id,
                etudiant_id=etudiant_id
            ).first()
            
            if inscription:
                inscription.est_soumis = True
                inscription.date_soumission = datetime.now()
            
            db.session.commit()
            
            print(f"✅ TP {tp_id} soumis avec succès par l'étudiant {etudiant_id}")
            
            return jsonify({
                'success': True,
                'message': 'Votre travail a été soumis avec succès !',
                'questions_traitees': len(questions_reponse),
                'redirect': url_for('liste_tps_etudiant')
            })
            
        except Exception as e:
            db.session.rollback()
            print(f"❌ Erreur soumission avec images: {e}")
            import traceback
            traceback.print_exc()
            return jsonify({'success': False, 'message': f'Erreur: {str(e)}'}), 500
    
    @app.route('/uploads/tp_responses/<int:tp_id>/<filename>')
    @login_required
    def serve_tp_response_image(tp_id, filename):
        """Servir les images de réponses des TP"""
        try:
            print(f"\n📤 Service image réponse: TP {tp_id}, fichier {filename}")
            
            user_id = session.get('user_id')
            
            tp = db.session.get(TP, tp_id)
            if not tp:
                print("❌ TP non trouvé")
                return "TP non trouvé", 404
            
            can_access = False
            
            if tp.created_by == user_id:
                can_access = True
                print("✅ Permission: créateur du TP")
            else:
                if f"_etudiant_{user_id}_" in filename:
                    can_access = True
                    print("✅ Permission: étudiant propriétaire")
            
            if not can_access:
                print("❌ Permission refusée")
                return "Non autorisé", 403
            
            uploads_path = os.path.join(current_app.root_path, 'uploads', 'tp_responses', str(tp_id))
            file_path = os.path.join(uploads_path, filename)
            
            print(f"📁 Chemin recherché: {file_path}")
            
            if not os.path.exists(file_path):
                print(f"❌ Fichier non trouvé: {file_path}")
                
                if os.path.exists(uploads_path):
                    files = os.listdir(uploads_path)
                    print(f"📁 Fichiers disponibles: {files}")
                
                return "Image non trouvée", 404
            
            print(f"✅ Fichier trouvé, taille: {os.path.getsize(file_path)} bytes")
            
            mime_type = 'application/octet-stream'
            if filename.lower().endswith('.png'):
                mime_type = 'image/png'
            elif filename.lower().endswith(('.jpg', '.jpeg')):
                mime_type = 'image/jpeg'
            elif filename.lower().endswith('.gif'):
                mime_type = 'image/gif'
            elif filename.lower().endswith('.webp'):
                mime_type = 'image/webp'
            
            return send_from_directory(uploads_path, filename, mimetype=mime_type)
            
        except Exception as e:
            print(f"❌ Erreur service image: {e}")
            import traceback
            traceback.print_exc()
            return str(e), 500
    
    @app.route('/api/tp/<int:tp_id>/mettre_a_jour_commentaire', methods=['POST'])
    @login_required
    def mettre_a_jour_commentaire(tp_id):
        """Mettre à jour le commentaire d'une réponse existante"""
        try:
            data = request.get_json()
            question_id = data.get('question_id')
            commentaire = data.get('commentaire', '')
            etudiant_id = session.get('user_id')
            
            reponse = ReponseEtudiant.query.filter_by(
                tp_id=tp_id,
                question_id=question_id,
                etudiant_id=etudiant_id
            ).first()
            
            if not reponse:
                return jsonify({'success': False, 'message': 'Réponse non trouvée'}), 404
            
            reponse.reponse = commentaire
            reponse.date_soumission = datetime.now()
            
            db.session.commit()
            
            print(f"✅ Commentaire mis à jour pour question {question_id}: '{commentaire}'")
            
            return jsonify({
                'success': True,
                'message': 'Commentaire mis à jour'
            })
            
        except Exception as e:
            db.session.rollback()
            print(f"❌ Erreur mise à jour commentaire: {e}")
            return jsonify({'success': False, 'message': str(e)}), 500