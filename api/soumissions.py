# api/soumissions.py
from flask import jsonify, request, send_file,session
from io import BytesIO, StringIO
import csv
import os
from datetime import datetime
from db import db, TP, Question, ReponseEtudiant, EtudiantTP, Utilisateur
from utils.decorators import login_required
from utils.audit_logger import audit_logger
from controllers.notification_manager import (
    envoyer_notifications_tp_creer,
    envoyer_notifications_tp_modifie,
    envoyer_notifications_tp_complete
)

def register_soumission_routes(app):
    """Enregistrer toutes les routes liées aux soumissions"""
    
    @app.route('/api/soumissions', methods=['GET'])
    @login_required
    def get_soumissions():
        """API pour récupérer les soumissions avec filtres"""
        try:
            utilisateur = db.session.get(Utilisateur, session.get('user_id'))
            
            if utilisateur is None:
                return jsonify({'success': False, 'message': 'Session expirée, veuillez vous reconnecter'}), 401
            
            # Paramètres de filtrage
            tp_id = request.args.get('tp_id', 'all')
            search = request.args.get('search', '').strip().lower()
            statut = request.args.get('statut', 'all')
            page = int(request.args.get('page', 1))
            per_page = int(request.args.get('per_page', 10))
            
            # Récupérer les TP créés par cet enseignant
            tps_query = TP.query.filter_by(created_by=utilisateur.id)
            if tp_id != 'all':
                tps_query = tps_query.filter_by(id=int(tp_id))
            
            tps = tps_query.all()
            
            soumissions_data = []
            
            for tp in tps:
                # Récupérer les étudiants inscrits
                inscriptions = EtudiantTP.query.filter_by(tp_id=tp.id).all()
                
                for inscription in inscriptions:
                    etudiant = db.session.get(Utilisateur, inscription.etudiant_id)
                    etudiant_supprime = etudiant is None
                    
                    if etudiant_supprime:
                        print(f"⚠️ Etudiant introuvable (id={inscription.etudiant_id}) pour le TP {tp.id} - affiché comme compte supprimé")
                    
                    # Valeurs à utiliser pour la suite, que le compte existe encore ou non
                    etudiant_id_reel = inscription.etudiant_id
                    etudiant_nom = etudiant.nom if etudiant else "Étudiant"
                    etudiant_prenom = etudiant.prenom if etudiant else "(compte supprimé)"
                    etudiant_matricule = etudiant.matricule if etudiant else "N/A"
                    etudiant_email = etudiant.email if etudiant else "N/A"
                    
                    # Filtrer par recherche (un compte supprimé ne peut pas
                    # correspondre à une recherche par nom/matricule)
                    if search:
                        if etudiant_supprime:
                            continue
                        search_str = f"{etudiant_nom} {etudiant_prenom} {etudiant_matricule}".lower()
                        if search not in search_str:
                            continue
                    
                    # Compter les réponses
                    reponses = ReponseEtudiant.query.filter_by(
                        tp_id=tp.id,
                        etudiant_id=etudiant_id_reel
                    ).all()
                    
                    reponses_count = len(reponses)
                    
                    # Déterminer le statut
                    statut_etudiant = 'non_commence'
                    if reponses_count > 0:
                        if reponses_count == tp.nombre_questions:
                            statut_etudiant = 'soumis'
                        else:
                            statut_etudiant = 'en_cours'
                    
                    # Filtrer par statut
                    if statut != 'all':
                        if statut == 'soumis' and statut_etudiant != 'soumis':
                            continue
                        elif statut == 'en_cours' and statut_etudiant != 'en_cours':
                            continue
                        elif statut == 'non_commence' and statut_etudiant != 'non_commence':
                            continue
                    
                    # Calculer la note moyenne
                    note_moyenne = None
                    notes = [r.note for r in reponses if r.note is not None]
                    if notes:
                        note_moyenne = sum(notes) / len(notes)
                    
                    # Calculer la note totale (somme des notes obtenues)
                    note_totale = sum([r.note for r in reponses if r.note is not None]) if reponses else None
                    
                    # Calculer la note maximale possible (somme des points du TP)
                    questions = Question.query.filter_by(tp_id=tp.id).all()
                    note_max = sum([q.points for q in questions]) if questions else 0
                    
                    # Date de dernière soumission
                    date_soumission = None
                    if reponses:
                        date_soumission = max([r.date_soumission for r in reponses])
                    
                    # Durée estimée
                    duree = '0 min'
                    if reponses_count > 0:
                        duree_minutes = reponses_count * 5  # Estimation : 5 min par question
                        if duree_minutes > 60:
                            duree = f"{duree_minutes // 60}h {duree_minutes % 60}min"
                        else:
                            duree = f"{duree_minutes} min"
                    
                    soumissions_data.append({
                        'id': len(soumissions_data) + 1,
                        'tp_id': tp.id,
                        'tp_titre': tp.titre,
                        'tp_module': tp.module,
                        'etudiant_id': etudiant_id_reel,
                        'etudiant_nom': etudiant_nom,
                        'etudiant_prenom': etudiant_prenom,
                        'etudiant_matricule': etudiant_matricule,
                        'etudiant_email': etudiant_email,
                        'etudiant_supprime': etudiant_supprime,
                        'statut': statut_etudiant,
                        'reponses_count': reponses_count,
                        'questions_count': tp.nombre_questions,
                        'progression': f"{int((reponses_count / tp.nombre_questions) * 100) if tp.nombre_questions > 0 else 0}%",
                        'note': f"{note_moyenne:.1f}/20" if note_moyenne is not None else '-',
                        'note_valeur': note_totale,
                        'note_max': float(note_max),
                        'date_soumission': date_soumission.isoformat() if date_soumission else None,
                        'duree': duree
                    })
            
            # Trier par date de soumission (les plus récents d'abord)
            soumissions_data.sort(key=lambda x: x['date_soumission'] or '', reverse=True)
            
            # Pagination
            total = len(soumissions_data)
            total_pages = (total + per_page - 1) // per_page
            start_idx = (page - 1) * per_page
            end_idx = start_idx + per_page
            
            # Statistiques pour les filtres actuels
            stats_filtered = {
                'total': total,
                'soumis': len([s for s in soumissions_data if s['statut'] == 'soumis']),
                'en_cours': len([s for s in soumissions_data if s['statut'] == 'en_cours']),
                'non_commence': len([s for s in soumissions_data if s['statut'] == 'non_commence']),
                'moyenne_notes': None
            }
            
            # Calculer la moyenne des notes
            notes_valides = [s['note_valeur'] for s in soumissions_data if s['note_valeur'] is not None]
            if notes_valides:
                stats_filtered['moyenne_notes'] = sum(notes_valides) / len(notes_valides)
            
            return jsonify({
                'success': True,
                'soumissions': soumissions_data[start_idx:end_idx],
                'stats': stats_filtered,
                'pagination': {
                    'page': page,
                    'per_page': per_page,
                    'total': total,
                    'total_pages': total_pages
                }
            })
            
        except Exception as e:
            print(f"Erreur dans get_soumissions: {e}")
            return jsonify({
                'success': False,
                'message': str(e)
            }), 500
    
    @app.route('/api/soumissions/<int:tp_id>/<int:etudiant_id>', methods=['GET'])
    @login_required
    def get_soumission_details(tp_id, etudiant_id):
        """API pour récupérer les détails d'une soumission avec URLs de fichiers corrigées"""
        try:
            print("=" * 60)
            print("📥 DÉBUT GET /api/soumissions/{}/{}".format(tp_id, etudiant_id))
            print("=" * 60)
            
            # Récupérer les informations de session
            user_id = session.get('user_id')
            user_statut = session.get('user_statut')
            print(f"👤 User ID: {user_id}, Statut: {user_statut}")
            
            # Récupérer le TP
            tp = db.session.get(TP, tp_id)
            if not tp:
                print(f"❌ TP {tp_id} non trouvé")
                return jsonify({'success': False, 'message': 'TP non trouvé'}), 404
            
            print(f"📌 TP trouvé: {tp.titre}")
            print(f"📌 TP créé par: {tp.created_by}")
            
            # Vérifier les permissions
            can_access = False
            
            if tp.created_by == user_id:
                print("✅ Permission: créateur du TP")
                can_access = True
            elif str(user_id) == str(etudiant_id):
                print("✅ Permission: étudiant lui-même")
                can_access = True
            elif user_statut == 'admin':
                print("✅ Permission: administrateur")
                can_access = True
            
            if not can_access:
                print(f"❌ Permission refusée: user_id={user_id}, tp.created_by={tp.created_by}")
                return jsonify({'success': False, 'message': 'Non autorisé'}), 403
            
            # Récupérer l'étudiant
            etudiant = db.session.get(Utilisateur, etudiant_id)
            etudiant_supprime = etudiant is None
            if etudiant_supprime:
                print(f"⚠️ Étudiant {etudiant_id} introuvable (compte supprimé) - détails affichés quand même (notes/réponses conservées)")
            else:
                print(f"📌 Étudiant trouvé: {etudiant.prenom} {etudiant.nom}")
            
            # Récupérer les questions du TP
            questions = Question.query.filter_by(tp_id=tp_id).order_by(Question.ordre).all()
            print(f"📌 Questions trouvées: {len(questions)}")
            
            # Récupérer les réponses de l'étudiant
            reponses = ReponseEtudiant.query.filter_by(
                tp_id=tp_id,
                etudiant_id=etudiant_id
            ).all()
            print(f"📌 Réponses trouvées: {len(reponses)}")
            
            # Créer un dictionnaire pour accéder facilement aux réponses
            reponses_dict = {r.question_id: r for r in reponses}
            
            # Préparer les données des questions
            questions_data = []
            note_totale = 0
            note_max = 0
            
            for i, question in enumerate(questions):
                reponse = reponses_dict.get(question.id)
                
                # Ajouter les points de la question au maximum possible
                points_question = float(question.points) if question.points else 0
                note_max += points_question
                
                print(f"\n📝 Question {i+1} (ID: {question.id}):")
                print(f"   Points: {points_question}")
                print(f"   Type: {question.type_question}")
                print(f"   Réponse trouvée: {'Oui' if reponse else 'Non'}")
                
                # Gestion des fichiers uploadés
                fichier_url = None
                fichier_nom = None
                
                if reponse and reponse.fichier_path:
                    print(f"   📁 Fichier détecté: {reponse.fichier_path}")
                    
                    # Nettoyer le chemin de fichier
                    fichier_path = reponse.fichier_path.strip()
                    
                    # Supprimer les préfixes inutiles
                    prefixes_to_remove = ['uploads/', './uploads/', 'uploads\\', '.\\uploads\\']
                    for prefix in prefixes_to_remove:
                        if fichier_path.startswith(prefix):
                            fichier_path = fichier_path[len(prefix):]
                            print(f"   Chemin nettoyé (sans '{prefix}'): {fichier_path}")
                    
                    # Construire l'URL complète
                    base_url = request.host_url.rstrip('/')
                    fichier_url = f"{base_url}/uploads/{fichier_path}"
                    fichier_nom = os.path.basename(fichier_path)
                    
                    # Vérifier si le fichier existe
                    file_path_full = os.path.join(app.config['UPLOAD_FOLDER'], fichier_path)
                    if os.path.exists(file_path_full):
                        print(f"   ✅ Fichier existe: {file_path_full}")
                        print(f"   📏 Taille: {os.path.getsize(file_path_full)} bytes")
                    else:
                        print(f"   ⚠️  Fichier n'existe pas: {file_path_full}")
                
                # Récupérer le commentaire de correction (avec getattr pour compatibilité)
                commentaire_correction = None
                if reponse:
                    commentaire_correction = getattr(reponse, 'commentaire_correction', None)
                    if commentaire_correction:
                        print(f"   💬 Commentaire de correction: {commentaire_correction[:50]}...")
                
                # Calculer la note
                note_question = None
                if reponse and reponse.note is not None:
                    note_question = float(reponse.note)
                    note_totale += note_question
                    print(f"   📊 Note: {note_question}/{points_question}")
                
                # Construire l'objet question
                question_data = {
                    'id': question.id,
                    'enonce': question.enonce or '',
                    'type_question': question.type_question or 'qcm',
                    'points': points_question,
                    'ordre': question.ordre or i,
                    'reponse_correcte': question.reponse_correcte or '',
                    'reponse_etudiant': reponse.reponse if reponse else None,
                    'fichier_url': fichier_url,
                    'fichier_nom': fichier_nom,
                    'note': note_question,
                    'commentaire_correction': commentaire_correction,
                    'date_soumission': reponse.date_soumission.isoformat() if reponse and reponse.date_soumission else None,
                    'date_correction': reponse.date_correction.isoformat() if reponse and getattr(reponse, 'date_correction', None) else None
                }
                
                questions_data.append(question_data)
            
            # Récupérer l'inscription de l'étudiant au TP
            inscription = EtudiantTP.query.filter_by(
                tp_id=tp_id,
                etudiant_id=etudiant_id
            ).first()
            
            # Calculer la durée totale
            duree_totale = "0 min"
            duree_minutes = 0
            
            if reponses:
                # Filtrer les dates de soumission valides
                dates_soumission = [r.date_soumission for r in reponses if r.date_soumission]
                if dates_soumission:
                    date_debut = min(dates_soumission)
                    date_fin = max(dates_soumission)
                    duree_seconds = (date_fin - date_debut).total_seconds()
                    duree_minutes = duree_seconds / 60
                    
                    if duree_minutes > 60:
                        heures = int(duree_minutes // 60)
                        minutes = int(duree_minutes % 60)
                        duree_totale = f"{heures}h {minutes}min"
                    else:
                        duree_totale = f"{int(duree_minutes)} min"
                    
                    print(f"⏱️  Durée calculée: {duree_totale}")
            
            # Calculer le pourcentage de réussite
            pourcentage = 0
            if note_max > 0:
                pourcentage = (note_totale / note_max * 100)
            
            print(f"\n📊 STATISTIQUES FINALES:")
            print(f"   Note totale: {note_totale:.1f}")
            print(f"   Note maximale possible: {note_max:.1f}")
            print(f"   Pourcentage: {pourcentage:.1f}%")
            print(f"   Questions totales: {len(questions)}")
            print(f"   Questions répondues: {len(reponses)}")
            print(f"   Questions non répondues: {len(questions) - len(reponses)}")
            
            # Préparer la réponse
            response_data = {
                'success': True,
                'tp': {
                    'id': tp.id,
                    'titre': tp.titre or '',
                    'module': tp.module or '',
                    'description': tp.description or '',
                    'date_creation': tp.date_creation.isoformat() if tp.date_creation else None,
                    'date_limite': tp.date_limite.isoformat() if tp.date_limite else None,
                    'nombre_questions': tp.nombre_questions or 0,
                    'created_by': tp.created_by
                },
                'etudiant': {
                    'id': etudiant_id,
                    'nom': etudiant.nom if etudiant else 'Étudiant',
                    'prenom': etudiant.prenom if etudiant else '(compte supprimé)',
                    'matricule': etudiant.matricule if etudiant else 'N/A',
                    'email': etudiant.email if etudiant else 'N/A',
                    'organisation': etudiant.organisation if etudiant else '',
                    'compte_supprime': etudiant_supprime
                },
                'questions': questions_data,
                'statistiques': {
                    'note_totale': round(note_totale, 2),
                    'note_max': round(note_max, 2),
                    'questions_repondues': len(reponses),
                    'questions_total': len(questions),
                    'pourcentage': round(pourcentage, 2),
                    'date_inscription': inscription.date_inscription.isoformat() if inscription and inscription.date_inscription else None,
                    'duree_totale': duree_totale,
                    'duree_totale_minutes': round(duree_minutes, 2)
                }
            }
            
            print("\n✅ Données préparées avec succès!")
            print("=" * 60)
            
            return jsonify(response_data)
            
        except Exception as e:
            print(f"\n❌ ERREUR CRITIQUE dans get_soumission_details:")
            print(f"   Message: {str(e)}")
            print(f"   Type: {type(e).__name__}")
            import traceback
            traceback.print_exc()
            print("=" * 60)
            
            return jsonify({
                'success': False,
                'message': f'Erreur serveur: {str(e)}',
                'error_type': type(e).__name__
            }), 500
    
    @app.route('/api/soumissions/export_csv', methods=['GET'])
    @login_required
    def export_soumissions_csv():
        """Exporter les soumissions d'un TP en CSV"""
        try:
            # Récupérer les paramètres
            tp_id = request.args.get('tp_id')
            
            if not tp_id or tp_id == 'all':
                return jsonify({'success': False, 'message': 'Veuillez sélectionner un TP'}), 400
            
            # Vérifier que l'utilisateur est le créateur du TP
            utilisateur = db.session.get(Utilisateur, session.get('user_id'))
            tp = db.session.get(TP, int(tp_id))
            
            if not tp:
                return jsonify({'success': False, 'message': 'TP non trouvé'}), 404
            
            if tp.created_by != utilisateur.id:
                return jsonify({'success': False, 'message': 'Non autorisé'}), 403
            
            # Récupérer toutes les soumissions pour ce TP
            inscriptions = EtudiantTP.query.filter_by(tp_id=tp.id).all()
            
            # Créer le fichier CSV en mémoire avec StringIO (pas BytesIO)
            output = StringIO()
            writer = csv.writer(output, delimiter=';', quoting=csv.QUOTE_ALL)
            
            # En-têtes du CSV avec BOM UTF-8 pour Excel
            output.write('\ufeff')  # BOM UTF-8 pour Excel
            writer.writerow(['Nom', 'Prénom', 'Matricule', 'Note'])
            
            # Données
            for inscription in inscriptions:
                etudiant = db.session.get(Utilisateur, inscription.etudiant_id)
                
                # Récupérer toutes les réponses de l'étudiant pour ce TP
                reponses = ReponseEtudiant.query.filter_by(
                    tp_id=tp.id,
                    etudiant_id=etudiant.id
                ).all()
                
                # Calculer la note totale
                notes = [float(r.note) for r in reponses if r.note is not None]
                note_totale = sum(notes) if notes else 0
                
                # Écrire la ligne dans le CSV avec format français
                writer.writerow([
                    etudiant.nom or '',
                    etudiant.prenom or '',
                    etudiant.matricule or '',
                    str(note_totale).replace('.', ',')  # Format français avec virgule
                ])
            
            # Préparer la réponse avec encodage UTF-8
            output.seek(0)
            csv_data = output.getvalue()
            
            # Convertir en bytes pour send_file
            csv_bytes = BytesIO(csv_data.encode('utf-8-sig'))  # utf-8-sig pour inclure le BOM
            
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f'notes_{tp.titre.replace(" ", "_")}_{timestamp}.csv'
            
            return send_file(
                csv_bytes,
                mimetype='text/csv; charset=utf-8-sig',
                as_attachment=True,
                download_name=filename
            )
            
        except Exception as e:
            print(f"❌ Erreur export CSV: {e}")
            import traceback
            traceback.print_exc()
            return jsonify({'success': False, 'message': str(e)}), 500
    
    @app.route('/api/soumissions/<int:tp_id>/<int:etudiant_id>/export', methods=['GET'])
    @login_required
    def export_soumission_pdf(tp_id, etudiant_id):
        """Exporter une soumission en PDF"""
        try:
            # Vérifier que l'enseignant est le créateur du TP
            tp = db.session.get(TP, tp_id)
            user_id = session.get('user_id')
            
            if not tp or tp.created_by != user_id:
                # Vérifier aussi si c'est l'étudiant lui-même
                if str(user_id) != str(etudiant_id):
                    return jsonify({'success': False, 'message': 'Non autorisé'}), 403
            
            # Récupérer les données
            etudiant = db.session.get(Utilisateur, etudiant_id)
            questions = Question.query.filter_by(tp_id=tp_id).order_by(Question.ordre).all()
            reponses = ReponseEtudiant.query.filter_by(
                tp_id=tp_id,
                etudiant_id=etudiant_id
            ).all()
            
            if not questions:
                return jsonify({'success': False, 'message': 'Aucune question trouvée pour ce TP'}), 404
            
            reponses_dict = {r.question_id: r for r in reponses}
            
            # Calculer les statistiques
            notes = [r.note for r in reponses if r.note is not None]
            note_totale = sum(notes) if notes else 0
            note_max = sum([q.points for q in questions])
            
            # Générer le contenu HTML pour le PDF
            html_content = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="UTF-8">
                <title>Soumission TP - {tp.titre}</title>
                <style>
                    body {{ font-family: Arial, sans-serif; margin: 40px; }}
                    .header {{ text-align: center; border-bottom: 2px solid #333; padding-bottom: 20px; margin-bottom: 30px; }}
                    .info {{ margin-bottom: 30px; }}
                    .section {{ margin-bottom: 20px; }}
                    .question {{ margin-bottom: 25px; border-left: 3px solid #007bff; padding-left: 15px; }}
                    .question-number {{ font-weight: bold; color: #007bff; }}
                    .reponse {{ background-color: #f8f9fa; padding: 10px; border-radius: 5px; margin: 10px 0; }}
                    .note {{ color: #28a745; font-weight: bold; }}
                    .summary {{ background-color: #e9ecef; padding: 20px; border-radius: 5px; margin-top: 30px; }}
                    table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
                    th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
                    th {{ background-color: #f2f2f2; }}
                </style>
            </head>
            <body>
                <div class="header">
                    <h1>SOUMISSION DE TRAVAIL PRATIQUE</h1>
                    <h2>{tp.titre}</h2>
                    <p>Module: {tp.module or 'Non spécifié'}</p>
                </div>
                
                <div class="info">
                    <h3>Informations de l'étudiant</h3>
                    <table>
                        <tr><th>Nom complet:</th><td>{etudiant.prenom} {etudiant.nom}</td></tr>
                        <tr><th>Matricule:</th><td>{etudiant.matricule}</td></tr>
                        <tr><th>Email:</th><td>{etudiant.email}</td></tr>
                        <tr><th>Organisation:</th><td>{etudiant.organisation}</td></tr>
                    </table>
                    
                    <h3>Informations du TP</h3>
                    <table>
                        <tr><th>Titre:</th><td>{tp.titre}</td></tr>
                        <tr><th>Module:</th><td>{tp.module or 'Non spécifié'}</td></tr>
                        <tr><th>Date limite:</th><td>{tp.date_limite.strftime('%d/%m/%Y %H:%M') if tp.date_limite else 'Non définie'}</td></tr>
                        <tr><th>Nombre de questions:</th><td>{len(questions)}</td></tr>
                        <tr><th>Questions répondues:</th><td>{len(reponses)}</td></tr>
                    </table>
                </div>
                
                <div class="section">
                    <h3>Questions et réponses</h3>
            """
            
            for i, question in enumerate(questions, 1):
                reponse = reponses_dict.get(question.id)
                reponse_texte = reponse.reponse if reponse else "Non répondue"
                
                # Formater la réponse selon le type
                if reponse and reponse.fichier_path:
                    reponse_texte = f"Fichier joint: {os.path.basename(reponse.fichier_path)}"
                
                html_content += f"""
                    <div class="question">
                        <div class="question-number">Question {i} ({question.points} points)</div>
                        <div class="enonce">{question.enonce}</div>
                        <div class="reponse">
                            <strong>Réponse de l'étudiant:</strong><br>
                            {reponse_texte}
                        </div>
                        <div class="note">
                            Note: {reponse.note if reponse and reponse.note else 'Non notée'}/{question.points}
                        </div>
                    </div>
                """
            
            pourcentage = (note_totale / note_max * 100) if note_max > 0 else 0
            
            html_content += f"""
                </div>
                
                <div class="summary">
                    <h3>Récapitulatif de la notation</h3>
                    <table>
                        <tr><th>Note totale:</th><td>{note_totale:.1f}/{note_max:.1f}</td></tr>
                        <tr><th>Pourcentage:</th><td>{pourcentage:.1f}%</td></tr>
                        <tr><th>Questions totales:</th><td>{len(questions)}</td></tr>
                        <tr><th>Questions répondues:</th><td>{len(reponses)}</td></tr>
                        <tr><th>Date d'export:</th><td>{datetime.now().strftime('%d/%m/%Y à %H:%M')}</td></tr>
                    </table>
                </div>
            </body>
            </html>
            """
            
            # Essayer d'utiliser weasyprint si disponible, sinon générer un fichier texte
            try:
                # Essayer d'importer weasyprint
                from weasyprint import HTML
                
                # Générer le PDF
                pdf_file = BytesIO()
                HTML(string=html_content).write_pdf(pdf_file)
                pdf_file.seek(0)
                
                return send_file(
                    pdf_file,
                    mimetype='application/pdf',
                    as_attachment=True,
                    download_name=f'soumission_{tp.titre.replace(" ", "_")}_{etudiant.matricule}_{datetime.now().strftime("%Y%m%d")}.pdf'
                )
                
            except ImportError:
                # Si weasyprint n'est pas installé, générer un fichier HTML
                html_file = BytesIO()
                html_file.write(html_content.encode('utf-8'))
                html_file.seek(0)
                
                return send_file(
                    html_file,
                    mimetype='text/html',
                    as_attachment=True,
                    download_name=f'soumission_{tp.titre.replace(" ", "_")}_{etudiant.matricule}_{datetime.now().strftime("%Y%m%d")}.html'
                )
            
        except Exception as e:
            print(f"❌ Erreur export PDF: {e}")
            import traceback
            traceback.print_exc()
            
            # En cas d'erreur, générer un fichier texte simple
            error_content = f"Erreur lors de la génération du PDF: {str(e)}"
            output = BytesIO()
            output.write(error_content.encode('utf-8'))
            output.seek(0)
            
            return send_file(
                output,
                mimetype='text/plain',
                as_attachment=True,
                download_name='erreur_export.txt'
            )
    
    @app.route('/api/soumissions/stats', methods=['GET'])
    @login_required
    def get_soumissions_stats():
        """API pour récupérer les statistiques des soumissions"""
        try:
            utilisateur = db.session.get(Utilisateur, session.get('user_id'))
            
            # Récupérer tous les TP créés par cet enseignant
            tps = TP.query.filter_by(created_by=utilisateur.id).all()
            
            stats = {
                'tps': len(tps),
                'etudiants': 0,
                'soumis': 0,
                'en_cours': 0,
                'non_commence': 0,
                'moyenne_notes': 0
            }
            
            # Compter les statistiques
            for tp in tps:
                inscriptions = EtudiantTP.query.filter_by(tp_id=tp.id).all()
                stats['etudiants'] += len(inscriptions)
                
                for inscription in inscriptions:
                    reponses_count = ReponseEtudiant.query.filter_by(
                        tp_id=tp.id,
                        etudiant_id=inscription.etudiant_id
                    ).count()
                    
                    if reponses_count == tp.nombre_questions and tp.nombre_questions > 0:
                        stats['soumis'] += 1
                    elif reponses_count > 0:
                        stats['en_cours'] += 1
                    else:
                        stats['non_commence'] += 1
            
            # Calculer la moyenne des notes
            all_notes = []
            for tp in tps:
                reponses = ReponseEtudiant.query.filter_by(tp_id=tp.id).all()
                for reponse in reponses:
                    if reponse.note is not None:
                        all_notes.append(reponse.note)
            
            if all_notes:
                stats['moyenne_notes'] = sum(all_notes) / len(all_notes)
            
            return jsonify({
                'success': True,
                'stats': stats
            })
            
        except Exception as e:
            print(f"❌ Erreur dans get_soumissions_stats: {e}")
            import traceback
            traceback.print_exc()
            return jsonify({
                'success': False,
                'message': str(e)
            }), 500
    
    @app.route('/api/soumissions/correction', methods=['POST'])
    @login_required
    def sauvegarder_correction():
        """Sauvegarder la correction d'une soumission"""
        try:
            print("=" * 60)
            print("💾 DÉBUT SAUVEGARDE CORRECTION")
            print("=" * 60)
            
            # Informations de l'utilisateur
            user_id = session.get('user_id')
            user_statut = session.get('user_statut')
            print(f"👤 User ID: {user_id}, Statut: {user_statut}")
            
            # Vérifier le Content-Type
            content_type = request.headers.get('Content-Type', '')
            print(f"📋 Content-Type: {content_type}")
            
            if not content_type or 'application/json' not in content_type:
                print("❌ Content-Type incorrect. Requis: application/json")
                return jsonify({
                    'success': False, 
                    'message': 'Content-Type doit être application/json'
                }), 400
            
            # Lire les données JSON
            try:
                data = request.get_json()
                if not data:
                    print("❌ Aucune donnée JSON reçue")
                    return jsonify({'success': False, 'message': 'Aucune donnée reçue'}), 400
                    
                print("✅ Données JSON reçues avec succès")
            except Exception as json_error:
                print(f"❌ Erreur parsing JSON: {json_error}")
                raw_data = request.get_data(as_text=True)
                print(f"📦 Données brutes (500 premiers caractères): {raw_data[:500]}...")
                return jsonify({
                    'success': False, 
                    'message': f'Données JSON invalides: {str(json_error)}'
                }), 400
            
            # Extraire les données
            tp_id = data.get('tp_id')
            etudiant_id = data.get('etudiant_id')
            corrections = data.get('corrections', [])
            commentaire = data.get('commentaire', '').strip()
            
            print(f"📌 TP ID: {tp_id}")
            print(f"📌 Étudiant ID: {etudiant_id}")
            print(f"📌 Nombre de corrections: {len(corrections)}")
            print(f"📌 Longueur commentaire: {len(commentaire)} caractères")
            
            # Validation des données requises
            if not tp_id or not etudiant_id:
                print("❌ TP ID ou Étudiant ID manquant")
                return jsonify({
                    'success': False, 
                    'message': 'TP ID et Étudiant ID sont requis'
                }), 400
            
            # Récupérer le TP
            tp = db.session.get(TP, tp_id)
            if not tp:
                print(f"❌ TP {tp_id} non trouvé")
                return jsonify({'success': False, 'message': 'TP non trouvé'}), 404
            
            print(f"📌 TP trouvé: {tp.titre}")
            print(f"📌 TP créé par: {tp.created_by}")
            
            # Vérifier les permissions
            can_correct = False
            permission_reason = ""
            
            if tp.created_by == user_id:
                can_correct = True
                permission_reason = "créateur du TP"
            elif user_statut == 'admin':
                can_correct = True
                permission_reason = "administrateur"
            
            if not can_correct:
                print(f"❌ Permission refusée: user_id={user_id}, tp.created_by={tp.created_by}")
                return jsonify({
                    'success': False, 
                    'message': 'Non autorisé à corriger ce TP. Seul le créateur du TP peut corriger.'
                }), 403
            
            print(f"✅ Permission accordée: {permission_reason}")
            
            # Récupérer l'étudiant
            etudiant = db.session.get(Utilisateur, etudiant_id)
            if not etudiant:
                print(f"⚠️ Étudiant {etudiant_id} introuvable (compte supprimé) - correction autorisée quand même")
            else:
                print(f"📌 Étudiant trouvé: {etudiant.prenom} {etudiant.nom}")
            
            # Vérifier si l'étudiant est inscrit au TP
            inscription = EtudiantTP.query.filter_by(
                tp_id=tp_id,
                etudiant_id=etudiant_id
            ).first()
            
            if not inscription:
                print(f"❌ Étudiant non inscrit à ce TP")
                return jsonify({
                    'success': False, 
                    'message': 'L\'étudiant n\'est pas inscrit à ce TP'
                }), 400
            
            # Traiter les corrections
            corrections_enregistrees = 0
            questions_corrigees = []
            erreurs_corrections = []
            
            print(f"\n📝 TRAITEMENT DES {len(corrections)} CORRECTIONS:")
            
            for i, correction in enumerate(corrections):
                question_id = correction.get('question_id')
                note = correction.get('note')
                
                print(f"\n  🔄 Correction {i+1}:")
                print(f"     Question ID: {question_id}")
                print(f"     Note proposée: {note}")
                
                # Validation de base
                if question_id is None:
                    erreur = "Question ID manquant"
                    print(f"     ❌ {erreur}")
                    erreurs_corrections.append(erreur)
                    continue
                
                if note is None:
                    erreur = f"Note manquante pour question {question_id}"
                    print(f"     ❌ {erreur}")
                    erreurs_corrections.append(erreur)
                    continue
                
                # Valider la note
                try:
                    note_float = float(note)
                    if note_float < 0:
                        erreur = f"Note négative pour question {question_id}: {note_float}"
                        print(f"     ❌ {erreur}")
                        erreurs_corrections.append(erreur)
                        continue
                except (ValueError, TypeError) as e:
                    erreur = f"Note invalide pour question {question_id}: '{note}' ({e})"
                    print(f"     ❌ {erreur}")
                    erreurs_corrections.append(erreur)
                    continue
                
                # Récupérer la réponse de l'étudiant
                reponse = ReponseEtudiant.query.filter_by(
                    tp_id=tp_id,
                    question_id=question_id,
                    etudiant_id=etudiant_id
                ).first()
                
                if not reponse:
                    erreur = f"Aucune réponse trouvée pour question {question_id}"
                    print(f"     ❌ {erreur}")
                    erreurs_corrections.append(erreur)
                    continue
                
                print(f"     ✅ Réponse trouvée (ID: {reponse.id})")
                
                # Récupérer la question pour vérifier les points max
                question = db.session.get(Question, question_id)
                if not question:
                    erreur = f"Question {question_id} non trouvée"
                    print(f"     ❌ {erreur}")
                    erreurs_corrections.append(erreur)
                    continue
                
                # Calculer les points maximum
                max_points = float(question.points) if question.points else 0
                note_valide = min(float(note_float), float(max_points))
                
                print(f"     📊 Points max: {max_points}")
                print(f"     📊 Note proposée: {note_float}")
                print(f"     📊 Note validée: {note_valide}")
                
                # Vérifier si la question a été répondue
                question_repondu = bool(reponse.reponse or reponse.fichier_path)
                if not question_repondu and note_valide > 0:
                    print(f"     ⚠️  Note attribuée à une question non répondue")
                
                # Enregistrer la correction
                reponse.note = note_valide
                
                # Ajouter le commentaire (avec getattr pour compatibilité)
                if commentaire and not getattr(reponse, 'commentaire_correction', None):
                    reponse.commentaire_correction = commentaire
                
                # Ajouter la date de correction (avec getattr pour compatibilité)
                if hasattr(reponse, 'date_correction'):
                    reponse.date_correction = datetime.now()
                
                corrections_enregistrees += 1
                questions_corrigees.append({
                    'question_id': question_id,
                    'note': note_valide,
                    'max': max_points,
                    'question_text': question.enonce[:50] + '...' if question.enonce and len(question.enonce) > 50 else question.enonce
                })
                
                print(f"     ✅ Correction enregistrée: {note_valide}/{max_points}")
            
            print(f"\n📊 RÉCAPITULATIF CORRECTIONS:")
            print(f"   Corrections traitées: {len(corrections)}")
            print(f"   Corrections enregistrées: {corrections_enregistrees}")
            print(f"   Erreurs: {len(erreurs_corrections)}")
            
            if corrections_enregistrees == 0:
                print("❌ Aucune correction valide à enregistrer")
                return jsonify({
                    'success': False, 
                    'message': 'Aucune note valide à enregistrer. Vérifiez que:',
                    'details': [
                        'Les notes sont des nombres positifs',
                        'Les questions existent',
                        'L\'étudiant a répondu aux questions'
                    ],
                    'erreurs': erreurs_corrections[:10]  # Limiter à 10 erreurs
                }), 400
            
            # Sauvegarder en base de données
            try:
                print(f"\n💾 Tentative de commit avec {corrections_enregistrees} corrections...")
                db.session.commit()
                print("✅ Commit réussi!")
            except Exception as commit_error:
                print(f"❌ Erreur lors du commit: {commit_error}")
                db.session.rollback()
                print("↩️  Rollback effectué")
                return jsonify({
                    'success': False,
                    'message': f'Erreur base de données: {str(commit_error)}'
                }), 500
            
            # Calculer les statistiques
            note_totale = sum(q['note'] for q in questions_corrigees)
            note_max_totale = sum(q['max'] for q in questions_corrigees)
            pourcentage_totale = (note_totale / note_max_totale * 100) if note_max_totale > 0 else 0
            
            print(f"\n STATISTIQUES FINALES:")
            print(f"   Note totale: {note_totale:.1f}/{note_max_totale:.1f}")
            print(f"   Pourcentage: {pourcentage_totale:.1f}%")
            print(f"   Commentaire ajouté: {'Oui' if commentaire else 'Non'}")
            
            # Log d'audit
            try:
                audit_logger.log(
                    event_type='CORRECTION_SAVED',
                    user_id=user_id,
                    connection_id=None,
                    details=f"Correction TP {tp_id} - Étudiant {etudiant_id} - {corrections_enregistrees} questions corrigées",
                    ip_address=request.remote_addr
                )
                print("📝 Log d'audit enregistré")
            except Exception as audit_error:
                print(f"⚠️  Erreur log audit: {audit_error}")
            
            # Préparer la réponse de succès
            response_data = {
                'success': True,
                'message': f'Correction enregistrée avec succès! {corrections_enregistrees} question(s) corrigée(s).',
                'corrections_enregistrees': corrections_enregistrees,
                'note_totale': round(note_totale, 2),
                'note_max': round(note_max_totale, 2),
                'pourcentage': round(pourcentage_totale, 2),
                'questions_corrigees': questions_corrigees,
                'commentaire_ajoute': bool(commentaire),
                'timestamp': datetime.now().isoformat(),
                'avertissements': erreurs_corrections if erreurs_corrections else None
            }
            
            print("\n✅ Correction sauvegardée avec succès!")
            print("=" * 60)
            
            return jsonify(response_data)
            
        except Exception as e:
            print(f"\n❌ ERREUR CRITIQUE dans sauvegarder_correction:")
            print(f"   Message: {str(e)}")
            print(f"   Type: {type(e).__name__}")
            import traceback
            traceback.print_exc()
            print("=" * 60)
            
            # Annuler les changements en cas d'erreur
            try:
                db.session.rollback()
                print("↩️  Rollback effectué")
            except:
                print("⚠️  Impossible d'effectuer le rollback")
            
            return jsonify({
                'success': False,
                'message': f'Erreur serveur: {str(e)}',
                'error_type': type(e).__name__
            }), 500
    
    @app.route('/api/soumissions/debug_correction', methods=['POST'])
    @login_required
    def debug_correction():
        """Route de debug pour voir les données reçues"""
        try:
            data = request.get_json()
            print("=== DEBUG CORRECTION ===")
            print("Données reçues:", data)
            print("Type de données:", type(data))
            
            # Log de session
            print("User ID session:", session.get('user_id'))
            
            return jsonify({
                'success': True,
                'debug': 'Données reçues',
                'data_received': data,
                'data_type': str(type(data))
            })
        except Exception as e:
            print(f"Erreur debug: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500