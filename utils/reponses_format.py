# utils/reponses_format.py
"""
Utilitaires partagés pour l'affichage lisible des réponses aux questions
QCM (choix unique) et "cases à cocher" (choix multiples).

Rappel du format de stockage (voir static/js/repondre_questions.js) :
- Question.reponse_correcte : chaîne JSON contenant la liste des options
  proposées, ex. '["Paris", "Lyon", "Marseille"]'
- ReponseEtudiant.reponse pour une question 'qcm'         : le TEXTE de
  l'option choisie, ex. "Paris" (PAS un index ni une lettre).
- ReponseEtudiant.reponse pour une question 'case_cocher' : une chaîne
  JSON contenant la liste des textes cochés, ex. '["Paris", "Lyon"]'.
"""
import json


def parse_options(reponse_correcte_brute):
    """Retourne la liste des textes d'options définies pour une question
    QCM/cases à cocher, à partir de Question.reponse_correcte."""
    if not reponse_correcte_brute:
        return []
    try:
        data = json.loads(reponse_correcte_brute)
        if isinstance(data, list):
            return [str(item) for item in data]
    except (ValueError, TypeError):
        pass
    return []


def selected_option_texts(type_question, reponse_brute):
    """Retourne la liste des textes d'options sélectionnées par l'étudiant,
    quel que soit le type de question (qcm ou case_cocher)."""
    if not reponse_brute:
        return []

    if type_question == 'case_cocher':
        try:
            data = json.loads(reponse_brute)
            if isinstance(data, list):
                return [str(item) for item in data if str(item).strip()]
        except (ValueError, TypeError):
            pass
        # Ancien format éventuel : texte simple séparé par des virgules
        return [item.strip() for item in reponse_brute.split(',') if item.strip()]

    if type_question == 'qcm':
        # La réponse stockée EST déjà le texte de l'option choisie.
        texte = str(reponse_brute).strip()
        return [texte] if texte else []

    return []


def format_student_answer(type_question, reponse_brute):
    """Retourne une chaîne lisible pour l'affichage (ex. dans un export CSV
    ou une correction), pour les types qcm / case_cocher. Pour les autres
    types, retourne le texte brut tel quel."""
    if type_question in ('qcm', 'case_cocher'):
        textes = selected_option_texts(type_question, reponse_brute)
        return ', '.join(textes) if textes else ''
    return reponse_brute or ''


def build_qcm_display(questions):
    """
    Construit, pour une liste de Question, un dictionnaire
    { question_id: {'options': [...], 'type': 'qcm'|'case_cocher'} }
    prêt à être passé à un template Jinja pour afficher les vraies options
    (au lieu de lettres A/B/C/D factices).
    """
    display = {}
    for question in questions:
        if question.type_question in ('qcm', 'case_cocher'):
            display[question.id] = {
                'options': parse_options(question.reponse_correcte),
                'type': question.type_question,
            }
    return display
