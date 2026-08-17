from datetime import datetime
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class Utilisateur(db.Model):
    __tablename__ = 'utilisateurs'
    
    id = db.Column(db.Integer, primary_key=True)
    nom = db.Column(db.String(100), nullable=False)
    prenom = db.Column(db.String(100), nullable=False)
    date_naissance = db.Column(db.Date, nullable=False)
    lieu_naissance = db.Column(db.String(200), nullable=False)
    organisation = db.Column(db.String(200), nullable=False)
    matricule = db.Column(db.String(50), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    statut = db.Column(db.String(20), default='pending', nullable=False)  # pending, user, admin, bloque
    email_verifie = db.Column(db.Boolean, default=False, nullable=False)
    token_verification = db.Column(db.String(200), nullable=True)
    token_expiration = db.Column(db.DateTime, nullable=True)
    date_verification = db.Column(db.DateTime, nullable=True)
    date_inscription = db.Column(db.DateTime, default=datetime.now, nullable=False)
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Assurer les valeurs par défaut
        if self.statut is None:
            self.statut = 'pending'
        if self.email_verifie is None:
            self.email_verifie = False
        if self.date_inscription is None:
            self.date_inscription = datetime.now()
    
    def __repr__(self):
        return f'<Utilisateur {self.prenom} {self.nom}>'
    
    def to_dict(self):
        """Convertir l'utilisateur en dictionnaire"""
        return {
            'id': self.id,
            'nom': self.nom,
            'prenom': self.prenom,
            'email': self.email,
            'matricule': self.matricule,
            'organisation': self.organisation,
            'statut': self.statut,
            'email_verifie': self.email_verifie,
            'date_inscription': self.date_inscription.isoformat() if self.date_inscription else None,
            'date_verification': self.date_verification.isoformat() if self.date_verification else None
        }

class TP(db.Model):
    __tablename__ = 'tps'
    
    id = db.Column(db.Integer, primary_key=True)
    titre = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    module = db.Column(db.String(100), nullable=True)
    date_creation = db.Column(db.DateTime, default=datetime.now, nullable=False)
    date_limite = db.Column(db.DateTime, nullable=True)
    created_by = db.Column(db.Integer, db.ForeignKey('utilisateurs.id'), nullable=True)
    nombre_questions = db.Column(db.Integer, default=0, nullable=False)
    nombre_etudiants = db.Column(db.Integer, default=0, nullable=False)
    actif = db.Column(db.Boolean, default=True, nullable=False)
    
    def __repr__(self):
        return f'<TP {self.titre}>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'titre': self.titre,
            'description': self.description,
            'module': self.module,
            'date_creation': self.date_creation.isoformat() if self.date_creation else None,
            'date_limite': self.date_limite.isoformat() if self.date_limite else None,
            'created_by': self.created_by,
            'nombre_questions': self.nombre_questions,
            'nombre_etudiants': self.nombre_etudiants,
            'actif': self.actif
        }

class Question(db.Model):
    __tablename__ = 'questions'
    
    id = db.Column(db.Integer, primary_key=True)
    tp_id = db.Column(db.Integer, db.ForeignKey('tps.id'), nullable=False)
    enonce = db.Column(db.Text, nullable=False)
    type_question = db.Column(db.String(50), default='qcm', nullable=False)  # qcm, ouverte, case_cocher, image
    points = db.Column(db.Float, default=1.0, nullable=False)
    ordre = db.Column(db.Integer, default=0, nullable=False)
    reponse_correcte = db.Column(db.Text, nullable=True)  # Pour les QCM, la réponse correcte
    image_url = db.Column(db.String(500), nullable=True) 
    date_creation = db.Column(db.DateTime, default=datetime.now)
    date_modification = db.Column(db.DateTime, default=datetime.now, nullable=False)
    
    def __repr__(self):
        return f'<Question {self.id} pour TP {self.tp_id}>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'tp_id': self.tp_id,
            'enonce': self.enonce,
            'type_question': self.type_question,
            'points': self.points,
            'ordre': self.ordre,
            'reponse_correcte': self.reponse_correcte
        }

class ReponseEtudiant(db.Model):
    __tablename__ = 'reponses_etudiants'
    
    id = db.Column(db.Integer, primary_key=True)
    tp_id = db.Column(db.Integer, db.ForeignKey('tps.id'), nullable=False)
    question_id = db.Column(db.Integer, db.ForeignKey('questions.id'), nullable=False)
    etudiant_id = db.Column(db.Integer, db.ForeignKey('utilisateurs.id'), nullable=False)
    reponse = db.Column(db.Text, nullable=True)
    fichier_path = db.Column(db.String(500), nullable=True)
    note = db.Column(db.Float, nullable=True)
    commentaire_correction = db.Column(db.Text, nullable=True)  # NOUVELLE COLONNE
    date_soumission = db.Column(db.DateTime, default=datetime.now, nullable=False)
    date_correction = db.Column(db.DateTime, nullable=True)  # NOUVELLE COLONNE
    
    def __repr__(self):
        return f'<ReponseEtudiant TP:{self.tp_id} Question:{self.question_id} Etudiant:{self.etudiant_id}>'
    
    def to_dict(self):
        """Convertir la réponse en dictionnaire"""
        return {
            'id': self.id,
            'tp_id': self.tp_id,
            'question_id': self.question_id,
            'etudiant_id': self.etudiant_id,
            'reponse': self.reponse,
            'fichier_path': self.fichier_path,
            'note': self.note,
            'commentaire_correction': self.commentaire_correction,  # AJOUT
            'date_soumission': self.date_soumission.isoformat() if self.date_soumission else None,
            'date_correction': self.date_correction.isoformat() if self.date_correction else None  # AJOUT
        }

class EtudiantTP(db.Model):
    __tablename__ = 'etudiants_tps'
    
    id = db.Column(db.Integer, primary_key=True)
    tp_id = db.Column(db.Integer, db.ForeignKey('tps.id'), nullable=False)
    etudiant_id = db.Column(db.Integer, db.ForeignKey('utilisateurs.id'), nullable=False)
    date_inscription = db.Column(db.DateTime, default=datetime.now, nullable=False)
    
    def __repr__(self):
        return f'<EtudiantTP TP:{self.tp_id} Etudiant:{self.etudiant_id}>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'tp_id': self.tp_id,
            'etudiant_id': self.etudiant_id,
            'date_inscription': self.date_inscription.isoformat() if self.date_inscription else None
        }

class Notification(db.Model):
    __tablename__ = 'notifications'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('utilisateurs.id'), nullable=False)
    type_notification = db.Column(db.String(50), nullable=False)  # systeme, nouveau_tp, tp_modifie, rappel_tp, correction
    titre = db.Column(db.String(200), nullable=False)
    message = db.Column(db.Text, nullable=False)
    donnees = db.Column(db.Text, nullable=True)  # JSON avec données supplémentaires
    lue = db.Column(db.Boolean, default=False, nullable=False)
    date_creation = db.Column(db.DateTime, default=datetime.now, nullable=False)
    date_lecture = db.Column(db.DateTime, nullable=True)
    
    def __repr__(self):
        return f'<Notification {self.titre} pour User:{self.user_id}>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'type_notification': self.type_notification,
            'titre': self.titre,
            'message': self.message,
            'donnees': self.donnees,
            'lue': self.lue,
            'date_creation': self.date_creation.isoformat() if self.date_creation else None,
            'date_lecture': self.date_lecture.isoformat() if self.date_lecture else None
        }