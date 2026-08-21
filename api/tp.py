# api/tp.py - Routes API pour les TP
from flask import jsonify, request, session, Blueprint, url_for, current_app
from utils.decorators import login_required
from db import db, TP, Question, ReponseEtudiant, EtudiantTP, Utilisateur
from datetime import datetime
import os
from werkzeug.utils import secure_filename

# Créer un Blueprint pour les routes API TP
tp_bp = Blueprint('tp_api', __name__, url_prefix='/api')

# Configuration pour les uploads
UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max file size

# Fonction utilitaire pour sauvegarder les fichiers
def save_uploaded_file(file, tp_id, etudiant_id, question_id=None):
    """Sauvegarde un fichier uploadé"""
    if file and file.filename:
        filename = secure_filename(file.filename)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        if question_id:
            # Pour les images de questions
            unique_filename = f"question_{question_id}_{timestamp}_{filename}"
            folder = 'questions'
        else:
            # Pour les réponses d'étudiants
            unique_filename = f"tp_{tp_id}_etudiant_{etudiant_id}_{timestamp}_{filename}"
            folder = 'reponses'
        
        # Créer le dossier s'il n'existe pas
        upload_path = os.path.join(current_app.root_path, UPLOAD_FOLDER, folder)
        os.makedirs(upload_path, exist_ok=True)
        
        file_path = os.path.join(upload_path, unique_filename)
        file.save(file_path)
        
        return os.path.join(folder, unique_filename)
    return None

# ===== ROUTES API =====

@tp_bp.route('/tp/<int:tp_id>/creer_questions', methods=['POST'])
@login_required
def creer_questions(tp_id):
    """API pour créer des questions pour un TP"""
    try:
        donnees = request.json
        questions = donnees.get('questions', [])
        
        tp = TP.query.get(tp_id)
        if not tp:
            return jsonify({'success': False, 'message': 'TP non trouvé'}), 404
        
        if tp.created_by != session.get('user_id'):
            return jsonify({'success': False, 'message': 'Non autorisé'}), 403
        
        # Supprimer les questions existantes
        Question.query.filter_by(tp_id=tp_id).delete()
        
        question_ids = []
        for i, q in enumerate(questions):
            question = Question(
                tp_id=tp_id,
                enonce=q.get('texte', ''),
                type_question=q.get('type_question', 'qcm'),
                points=float(q.get('points', 1.0)),
                ordre=q.get('ordre', i + 1),
                date_creation=datetime.now(),
                reponse_correcte=q.get('reponse_correcte', ''),
                image_url=q.get('image_url', None)  # NOUVEAU CHAMP
            )
            db.session.add(question)
            db.session.flush()
            question_ids.append(question.id)
        
        tp.nombre_questions = len(questions)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'{len(questions)} question(s) créée(s)',
            'count': len(questions),
            'questions_ids': question_ids
        })
        
    except Exception as e:
        db.session.rollback()
        print(f"Erreur création questions: {e}")
        return jsonify({'success': False, 'message': f'Erreur: {str(e)}'}), 500

@tp_bp.route('/tp/<int:tp_id>/etudiants')
@login_required
def get_etudiants_tp(tp_id):
    """API pour récupérer la liste des étudiants inscrits à un TP"""
    try:
        tp = TP.query.get(tp_id)
        if not tp:
            return jsonify({'success': False, 'message': 'TP non trouvé'}), 404
        
        if tp.created_by != session.get('user_id'):
            return jsonify({'success': False, 'message': 'Non autorisé'}), 403
        
        # jointure directe pour éviter les lectures N+1 et garantir que
        # la liste renvoyée reflète toujours l'état réel de la base.
        inscriptions = (
            db.session.query(EtudiantTP, Utilisateur)
            .join(Utilisateur, Utilisateur.id == EtudiantTP.etudiant_id)
            .filter(EtudiantTP.tp_id == tp_id)
            .all()
        )
        
        etudiants = []
        for _inscription, etudiant in inscriptions:
            identifiant = etudiant.matricule if etudiant.matricule else etudiant.email
            etudiants.append(identifiant)
        
        return jsonify({
            'success': True,
            'etudiants': etudiants,
            'count': len(etudiants)
        })
        
    except Exception as e:
        print(f"Erreur get_etudiants_tp: {e}")
        return jsonify({'success': False, 'message': 'Erreur serveur'}), 500

@tp_bp.route('/tp/<int:tp_id>/update_etudiants', methods=['POST'])
@login_required
def update_etudiants_tp(tp_id):
    """API pour mettre à jour la liste des étudiants d'un TP"""
    try:
        tp = TP.query.get(tp_id)
        if not tp:
            return jsonify({'success': False, 'message': 'TP non trouvé'}), 404
        
        if tp.created_by != session.get('user_id'):
            return jsonify({'success': False, 'message': 'Non autorisé'}), 403
        
        data = request.get_json(silent=True) or {}
        nouveaux_etudiants = data.get('etudiants', [])
        
        print(f"=== MISE À JOUR ÉTUDIANTS TP {tp_id} ===")
        print(f"Identifiants reçus: {nouveaux_etudiants}")
        
        from sqlalchemy import func
        
        added_count = 0
        etudiants_ajoutes = []
        introuvables = []
        deja_traites = set()  # évite les doublons dans la liste envoyée
        etudiants_ids_valides = []
        
        for identifiant_brut in nouveaux_etudiants:
            if not identifiant_brut:
                continue
            identifiant = str(identifiant_brut).strip()
            
            if not identifiant:
                continue
            
            cle_dedup = identifiant.lower()
            if cle_dedup in deja_traites:
                continue
            deja_traites.add(cle_dedup)
            
            # Recherche insensible à la casse et aux espaces superflus, par
            # matricule OU email : un simple problème de majuscules ne doit
            # plus faire échouer silencieusement l'ajout d'un étudiant.
            etudiant = Utilisateur.query.filter(
                (func.lower(func.trim(Utilisateur.matricule)) == identifiant.lower()) |
                (func.lower(func.trim(Utilisateur.email)) == identifiant.lower())
            ).first()
            
            if not etudiant:
                introuvables.append(identifiant)
                continue
            
            # Ne pas ajouter les admins ou le créateur du TP
            if etudiant.statut == 'admin' or etudiant.id == tp.created_by:
                introuvables.append(f"{identifiant} (compte enseignant/admin, ignoré)")
                continue
            
            etudiants_ids_valides.append(etudiant.id)
            etudiants_ajoutes.append(f"{etudiant.prenom} {etudiant.nom}")
        
        # On ne supprime/recrée les inscriptions QUE si la recherche s'est
        # déroulée sans erreur, pour ne jamais vider la liste existante par
        # accident (ex : requête réseau tronquée envoyant un tableau vide).
        EtudiantTP.query.filter_by(tp_id=tp_id).delete()
        
        for etudiant_id in etudiants_ids_valides:
            db.session.add(EtudiantTP(tp_id=tp_id, etudiant_id=etudiant_id))
        
        added_count = len(etudiants_ids_valides)
        tp.nombre_etudiants = added_count
        db.session.commit()
        
        print(f"Étudiants ajoutés: {added_count} | Introuvables: {introuvables}")
        
        if introuvables:
            message = (
                f'{added_count} étudiant(s) enregistré(s). '
                f'{len(introuvables)} identifiant(s) non trouvé(s) : ' + ', '.join(introuvables)
            )
        else:
            message = f'{added_count} étudiant(s) enregistré(s) avec succès'
        
        return jsonify({
            'success': True,
            'message': message,
            'count': added_count,
            'added_count': added_count,
            'etudiants_ajoutes': etudiants_ajoutes,
            'introuvables': introuvables
        })
        
    except Exception as e:
        db.session.rollback()
        print(f"Erreur update_etudiants_tp: {e}")
        return jsonify({'success': False, 'message': f'Erreur serveur: {str(e)}'}), 500

@tp_bp.route('/tp/<int:tp_id>/update_date_limite', methods=['POST'])
@login_required
def update_date_limite_tp(tp_id):
    """API pour mettre à jour la date limite d'un TP"""
    try:
        tp = TP.query.get(tp_id)
        if not tp:
            return jsonify({'success': False, 'message': 'TP non trouvé'}), 404
        
        if tp.created_by != session.get('user_id'):
            return jsonify({'success': False, 'message': 'Non autorisé'}), 403
        
        data = request.get_json()
        date_limite_str = data.get('date_limite', '')
        
        if date_limite_str:
            try:
                date_limite_dt = datetime.strptime(date_limite_str, '%Y-%m-%dT%H:%M')
                tp.date_limite = date_limite_dt
                message = 'Date limite mise à jour'
            except ValueError:
                return jsonify({'success': False, 'message': 'Format de date invalide'}), 400
        else:
            tp.date_limite = None
            message = 'Date limite supprimée'
        
        db.session.commit()
        
        date_formattee = ''
        if tp.date_limite:
            date_formattee = tp.date_limite.strftime('%d/%m/%Y %H:%M')
        
        return jsonify({
            'success': True,
            'message': message,
            'date_limite': tp.date_limite.strftime('%Y-%m-%dT%H:%M') if tp.date_limite else '',
            'date_limite_formatted': date_formattee
        })
        
    except Exception as e:
        db.session.rollback()
        print(f"Erreur update_date_limite_tp: {e}")
        return jsonify({'success': False, 'message': 'Erreur serveur'}), 500

@tp_bp.route('/tp/<int:tp_id>/supprimer', methods=['DELETE'])
def _supprimer_tp_impl(tp_id):
    """
    Implémentation commune de la suppression d'un TP (suppression douce).

    On ne supprime plus jamais physiquement le TP, ses questions, ni les
    réponses/inscriptions des étudiants : cela permettrait de perdre les
    copies déjà soumises par des étudiants, qu'on doit pouvoir continuer à
    corriger et que l'étudiant doit continuer à voir avec sa note.

    Le TP est simplement marqué `supprime = True` :
    - il disparaît de la liste active "Gestion des Travaux Pratiques" et de
      la liste des TP à faire côté étudiant (pour ceux qui n'ont rien soumis),
    - il continue à apparaître, en lecture/correction seule, pour les
      étudiants qui avaient déjà soumis une réponse.
    """
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Non authentifié'}), 401

    tp = TP.query.get(tp_id)
    if not tp:
        return jsonify({'success': False, 'message': 'TP non trouvé'}), 404

    user_id = session.get('user_id')
    if tp.created_by != user_id:
        return jsonify({'success': False, 'message': 'Permission refusée: Vous devez être le créateur du TP'}), 403

    if tp.supprime:
        return jsonify({'success': False, 'message': 'Ce TP a déjà été supprimé'}), 400

    questions_count = Question.query.filter_by(tp_id=tp_id).count()
    reponses_count = ReponseEtudiant.query.filter_by(tp_id=tp_id).count()
    inscriptions_count = EtudiantTP.query.filter_by(tp_id=tp_id).count()
    etudiants_avec_soumission = (
        db.session.query(ReponseEtudiant.etudiant_id).filter_by(tp_id=tp_id).distinct().count()
    )

    tp.supprime = True
    tp.date_suppression = datetime.now()
    db.session.commit()

    message = f'TP "{tp.titre}" supprimé.'
    if etudiants_avec_soumission > 0:
        message += (
            f' {etudiants_avec_soumission} étudiant(s) avaient déjà soumis leur travail : '
            'leurs copies sont conservées, restent corrigeables, et ils continueront de voir '
            'leur note. Le TP disparaît uniquement pour les étudiants qui n\'avaient rien soumis.'
        )

    return jsonify({
        'success': True,
        'message': message,
        'soft_delete': True,
        'stats': {
            'questions': questions_count,
            'reponses': reponses_count,
            'inscriptions': inscriptions_count,
            'etudiants_avec_soumission': etudiants_avec_soumission
        }
    })


@tp_bp.route('/tp/<int:tp_id>/supprimer', methods=['DELETE'])
@login_required
def supprimer_tp(tp_id):
    """API pour supprimer (suppression douce) un TP (méthode DELETE)"""
    try:
        return _supprimer_tp_impl(tp_id)
    except Exception as e:
        db.session.rollback()
        print(f"ERREUR suppression TP {tp_id}: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': f'Erreur serveur: {str(e)}'}), 500

@tp_bp.route('/tp/<int:tp_id>/supprimer_post', methods=['POST'])
@login_required
def supprimer_tp_post(tp_id):
    """API pour supprimer (suppression douce) un TP (méthode POST alternative)"""
    try:
        return _supprimer_tp_impl(tp_id)
    except Exception as e:
        db.session.rollback()
        print(f"ERREUR suppression TP {tp_id}: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': f'Erreur serveur: {str(e)}'}), 500

@tp_bp.route('/tp/<int:tp_id>/questions')
@login_required
def get_questions(tp_id):
    """API pour récupérer les questions existantes d'un TP"""
    try:
        tp = TP.query.get(tp_id)
        if not tp:
            return jsonify({'success': False, 'message': 'TP non trouvé'}), 404
        
        if tp.created_by != session.get('user_id'):
            return jsonify({'success': False, 'message': 'Non autorisé'}), 403
        
        questions = Question.query.filter_by(tp_id=tp_id).order_by(Question.ordre).all()
        
        questions_data = []
        for question in questions:
            questions_data.append({
                'id': question.id,
                'enonce': question.enonce,
                'type_question': question.type_question,
                'type': question.type_question,
                'texte': question.enonce,
                'points': question.points,
                'ordre': question.ordre,
                'reponse_correcte': question.reponse_correcte,
                'image_url': question.image_url  # AJOUTEZ CE CHAMP
            })
        
        return jsonify({
            'success': True,
            'questions': questions_data,
            'count': len(questions_data)
        })
        
    except Exception as e:
        print(f"Erreur récupération questions: {e}")
        return jsonify({'success': False, 'message': f'Erreur: {str(e)}', 'questions': []}), 500

@tp_bp.route('/tp/<int:tp_id>/info')
@login_required
def get_tp_info(tp_id):
    """API pour récupérer les informations d'un TP"""
    try:
        tp = TP.query.get(tp_id)
        if not tp:
            return jsonify({'success': False, 'message': 'TP non trouvé'}), 404
        
        if tp.created_by != session.get('user_id'):
            return jsonify({'success': False, 'message': 'Non autorisé'}), 403
        
        createur = Utilisateur.query.get(tp.created_by)
        inscriptions = EtudiantTP.query.filter_by(tp_id=tp_id).all()
        nombre_etudiants_reel = len(inscriptions)
        
        return jsonify({
            'success': True,
            'tp': {
                'id': tp.id,
                'titre': tp.titre,
                'description': tp.description,
                'module': tp.module,
                'date_creation': tp.date_creation.strftime('%d/%m/%Y %H:%M'),
                'date_limite': tp.date_limite.strftime('%Y-%m-%dT%H:%M') if tp.date_limite else '',
                'date_limite_formatted': tp.date_limite.strftime('%d/%m/%Y %H:%M') if tp.date_limite else 'Non définie',
                'actif': tp.actif,
                'nombre_questions': tp.nombre_questions,
                'nombre_etudiants': nombre_etudiants_reel,
                'createur': {
                    'nom': createur.nom,
                    'prenom': createur.prenom,
                    'email': createur.email
                }
            }
        })
        
    except Exception as e:
        print(f"Erreur get_tp_info: {e}")
        return jsonify({'success': False, 'message': 'Erreur serveur'}), 500

# ===== NOUVELLES ROUTES AJOUTÉES =====

@tp_bp.route('/tp/<int:tp_id>/soumettre', methods=['POST'])
@login_required
def soumettre_reponses(tp_id):
    """Soumettre les réponses d'un TP (AJAX)"""
    try:
        data = request.get_json()
        etudiant_id = session.get('user_id')
        
        # Vérifier si l'étudiant est inscrit
        inscription = EtudiantTP.query.filter_by(
            tp_id=tp_id, 
            etudiant_id=etudiant_id
        ).first()
        
        if not inscription:
            return jsonify({'success': False, 'message': 'Non inscrit à ce TP'}), 403
        
        tp = TP.query.get(tp_id)
        if tp and tp.supprime:
            return jsonify({'success': False, 'message': 'Ce TP a été supprimé par l\'enseignant et n\'accepte plus de soumissions'}), 403
        
        # Supprimer les anciennes réponses
        ReponseEtudiant.query.filter_by(
            tp_id=tp_id,
            etudiant_id=etudiant_id
        ).delete()
        
        # Enregistrer les nouvelles réponses
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
        print(f"Erreur soumission réponses: {e}")
        return jsonify({
            'success': False,
            'message': f'Erreur: {str(e)}'
        }), 500

@tp_bp.route('/tp/<int:tp_id>/sauvegarder_auto', methods=['POST'])
@login_required
def sauvegarder_auto(tp_id):
    """Sauvegarder automatiquement les réponses d'un TP avec fichiers"""
    try:
        etudiant_id = session.get('user_id')
        
        inscription = EtudiantTP.query.filter_by(
            tp_id=tp_id, 
            etudiant_id=etudiant_id
        ).first()
        
        if not inscription:
            return jsonify({'success': False, 'message': 'Non inscrit à ce TP'}), 403
        
        tp = db.session.get(TP, tp_id)
        if tp.date_limite and datetime.now() > tp.date_limite:
            return jsonify({'success': False, 'message': 'TP expiré'}), 403
        
        saved_count = 0
        
        print(f"💾 Sauvegarde auto pour TP {tp_id}, étudiant {etudiant_id}")
        print(f"📦 Form data keys: {list(request.form.keys())}")
        print(f"📦 Files keys: {list(request.files.keys())}")
        
        # Traiter les données de formulaire
        for key in request.form:
            if key.startswith('question_') and key.endswith('_id'):
                question_id = int(request.form.get(key))
                reponse_text = request.form.get(f'question_{question_id}_reponse', '')
                question_type = request.form.get(f'question_{question_id}_type', 'texte')
                
                fichier_path = None
                
                # Gérer l'upload de fichier si présent
                file_key = f'question_{question_id}_file'
                if file_key in request.files:
                    file = request.files[file_key]
                    if file and file.filename:
                        print(f"📁 Fichier reçu pour question {question_id}: {file.filename}")
                        # Sauvegarder le fichier
                        fichier_path = save_uploaded_file(file, tp_id, etudiant_id, question_id)
                        if fichier_path:
                            print(f"✅ Fichier sauvegardé: {fichier_path}")
                
                # Vérifier si la réponse existe déjà
                reponse_existante = ReponseEtudiant.query.filter_by(
                    tp_id=tp_id,
                    question_id=question_id,
                    etudiant_id=etudiant_id
                ).first()
                
                if reponse_existante:
                    # Mettre à jour la réponse existante
                    reponse_existante.reponse = reponse_text
                    if fichier_path:
                        reponse_existante.fichier_path = fichier_path
                    reponse_existante.date_soumission = datetime.now()
                    print(f"📝 Réponse mise à jour pour question {question_id}")
                else:
                    # Créer une nouvelle réponse
                    nouvelle_reponse = ReponseEtudiant(
                        tp_id=tp_id,
                        question_id=question_id,
                        etudiant_id=etudiant_id,
                        reponse=reponse_text,
                        fichier_path=fichier_path,
                        date_soumission=datetime.now()
                    )
                    db.session.add(nouvelle_reponse)
                    print(f"📝 Nouvelle réponse créée pour question {question_id}")
                
                saved_count += 1
        
        db.session.commit()
        
        print(f"✅ {saved_count} réponse(s) sauvegardée(s) avec succès")
        
        return jsonify({
            'success': True,
            'message': f'{saved_count} réponse(s) sauvegardée(s)',
            'sauvegardees': saved_count,
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        db.session.rollback()
        print(f"❌ Erreur sauvegarde auto: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'message': f'Erreur: {str(e)}'
        }), 500

@tp_bp.route('/tp/<int:tp_id>/reponses_sauvegardees', methods=['GET'])
@login_required
def get_reponses_sauvegardees(tp_id):
    """Récupérer les réponses sauvegardées d'un étudiant avec URL des fichiers"""
    try:
        etudiant_id = session.get('user_id')
        
        reponses = ReponseEtudiant.query.filter_by(
            tp_id=tp_id,
            etudiant_id=etudiant_id
        ).order_by(ReponseEtudiant.date_soumission.desc()).all()
        
        reponses_data = []
        for r in reponses:
            # Inclure l'URL du fichier si présent
            fichier_url = None
            if r.fichier_path:
                # Construire l'URL complète
                base_url = request.host_url.rstrip('/')
                fichier_url = f"{base_url}/uploads/{r.fichier_path}"
                print(f"📁 Génération URL pour réponse {r.id}: {fichier_url}")
            
            question = Question.query.get(r.question_id)
            reponses_data.append({
                'question_id': r.question_id,
                'reponse': r.reponse,
                'type': question.type_question if question else 'texte',
                'fichier_url': fichier_url,
                'fichier_nom': os.path.basename(r.fichier_path) if r.fichier_path else None,
                'date_soumission': r.date_soumission.isoformat() if r.date_soumission else None
            })
        
        return jsonify({
            'success': True,
            'reponses': reponses_data,
            'count': len(reponses_data),
            'last_save': reponses[0].date_soumission.isoformat() if reponses else None
        })
        
    except Exception as e:
        print(f"❌ Erreur get_reponses_sauvegardees: {e}")
        return jsonify({
            'success': False,
            'message': f'Erreur: {str(e)}'
        }), 500

# ===== ROUTE POUR UPLOAD D'IMAGE =====

@tp_bp.route('/upload_question_image', methods=['POST'])
@login_required
def upload_question_image():
    """API pour uploader une image pour une question"""
    try:
        # Vérifier si un fichier est présent
        if 'image' not in request.files:
            return jsonify({'success': False, 'message': 'Aucun fichier'}), 400
        
        file = request.files['image']
        
        if file.filename == '':
            return jsonify({'success': False, 'message': 'Aucun fichier sélectionné'}), 400
        
        # Vérifier l'extension
        allowed_extensions = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
        if not ('.' in file.filename and 
                file.filename.rsplit('.', 1)[1].lower() in allowed_extensions):
            return jsonify({'success': False, 'message': 'Format non supporté. Utilisez JPG, PNG ou GIF'}), 400
        
        # Vérifier la taille (5MB max)
        file.seek(0, os.SEEK_END)
        size = file.tell()
        file.seek(0)
        
        if size > 5 * 1024 * 1024:  # 5MB
            return jsonify({'success': False, 'message': 'Fichier trop volumineux (max 5MB)'}), 400
        
        # Récupérer les paramètres
        tp_id = request.form.get('tp_id')
        question_id = request.form.get('question_id')
        
        if not tp_id:
            return jsonify({'success': False, 'message': 'TP ID manquant'}), 400
        
        # Vérifier les permissions
        tp = db.session.get(TP, tp_id)
        if not tp:
            return jsonify({'success': False, 'message': 'TP non trouvé'}), 404
        
        if tp.created_by != session.get('user_id'):
            return jsonify({'success': False, 'message': 'Non autorisé'}), 403
        
        # Créer le dossier uploads s'il n'existe pas
        upload_folder = os.path.join(current_app.root_path, UPLOAD_FOLDER, 'questions')
        os.makedirs(upload_folder, exist_ok=True)
        
        # Générer un nom de fichier sécurisé et unique
        filename = secure_filename(file.filename)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        unique_filename = f"{tp_id}_{timestamp}_{filename}"
        
        # Sauvegarder le fichier
        file_path = os.path.join(upload_folder, unique_filename)
        file.save(file_path)
        
        print(f"✅ Image sauvegardée: {file_path}")
        
        # Retourner l'URL relative
        image_url = f"/static/uploads/questions/{unique_filename}"
        
        return jsonify({
            'success': True,
            'message': 'Image uploadée avec succès',
            'image_url': image_url,
            'filename': unique_filename
        })
        
    except Exception as e:
        print(f"❌ Erreur upload image: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': f'Erreur: {str(e)}'}), 500

# ===== ROUTE POUR LES QUESTIONS AVEC IMAGES =====

@tp_bp.route('/api/tp/<int:tp_id>/questions_api')
@login_required
def get_questions_api(tp_id):
    """API pour récupérer les questions existantes d'un TP (version API)"""
    try:
        tp = TP.query.get(tp_id)
        if not tp:
            return jsonify({'success': False, 'message': 'TP non trouvé'}), 404
        
        if tp.created_by != session.get('user_id'):
            return jsonify({'success': False, 'message': 'Non autorisé'}), 403
        
        questions = Question.query.filter_by(tp_id=tp_id).order_by(Question.ordre).all()
        
        questions_data = []
        for question in questions:
            questions_data.append({
                'id': question.id,
                'enonce': question.enonce,
                'type_question': question.type_question,
                'type': question.type_question,
                'texte': question.enonce,
                'points': question.points,
                'ordre': question.ordre,
                'reponse_correcte': question.reponse_correcte,
                'image_url': question.image_url  # AJOUTEZ CE CHAMP
            })
        
        return jsonify({
            'success': True,
            'questions': questions_data,
            'count': len(questions_data)
        })
        
    except Exception as e:
        print(f"Erreur récupération questions: {e}")
        return jsonify({'success': False, 'message': f'Erreur: {str(e)}', 'questions': []}), 500

# ===== FONCTION D'ENREGISTREMENT =====
def register_tp_routes(app):
    """Enregistre le Blueprint des routes TP dans l'application Flask"""
    app.register_blueprint(tp_bp)
    print("Routes TP API enregistrées avec succès")