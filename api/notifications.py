# api/notifications.py
from flask import jsonify, request, session
from datetime import datetime
import json
from db import db, Notification
from utils.decorators import login_required

def register_notification_routes(app):
    """Enregistrer toutes les routes liées aux notifications"""
    
    @app.route('/api/notifications', methods=['GET'])
    @login_required
    def get_notifications():
        """Récupérer les notifications de l'utilisateur"""
        try:
            user_id = session.get('user_id')
            
            # Récupérer les notifications non lues en premier
            notifications = Notification.query.filter_by(user_id=user_id)\
                .order_by(Notification.lue, Notification.date_creation.desc())\
                .limit(20).all()
            
            notifications_data = []
            for notif in notifications:
                notifications_data.append(notif.to_dict())
            
            return jsonify({
                'success': True,
                'notifications': notifications_data,
                'count': len(notifications_data)
            })
            
        except Exception as e:
            return jsonify({'success': False, 'message': str(e)})
    
    @app.route('/api/notifications/<int:notification_id>/read', methods=['POST'])
    @login_required
    def mark_notification_read(notification_id):
        """Marquer une notification comme lue"""
        try:
            user_id = session.get('user_id')
            notification = Notification.query.filter_by(
                id=notification_id, 
                user_id=user_id
            ).first()
            
            if notification:
                notification.lue = True
                notification.date_lecture = datetime.now()
                db.session.commit()
                
                return jsonify({
                    'success': True,
                    'message': 'Notification marquée comme lue'
                })
            else:
                return jsonify({'success': False, 'message': 'Notification non trouvée'}), 404
                
        except Exception as e:
            db.session.rollback()
            return jsonify({'success': False, 'message': str(e)}), 500
    
    @app.route('/api/notifications/read_all', methods=['POST'])
    @login_required
    def mark_all_notifications_read():
        """Marquer toutes les notifications comme lues"""
        try:
            user_id = session.get('user_id')
            
            notifications = Notification.query.filter_by(
                user_id=user_id,
                lue=False
            ).all()
            
            for notification in notifications:
                notification.lue = True
                notification.date_lecture = datetime.now()
            
            db.session.commit()
            
            return jsonify({
                'success': True,
                'message': f'Toutes les notifications ({len(notifications)}) ont été marquées comme lues'
            })
            
        except Exception as e:
            db.session.rollback()
            return jsonify({'success': False, 'message': str(e)}), 500
    
    @app.route('/api/notifications/count', methods=['GET'])
    @login_required
    def get_unread_notification_count():
        """Récupérer le nombre de notifications non lues"""
        try:
            user_id = session.get('user_id')
            
            count = Notification.query.filter_by(
                user_id=user_id,
                lue=False
            ).count()
            
            return jsonify({
                'success': True,
                'count': count
            })
            
        except Exception as e:
            return jsonify({'success': False, 'message': str(e)})
    
    @app.route('/api/notifications/test', methods=['GET'])
    @login_required
    def test_notification():
        """Créer une notification de test"""
        try:
            user_id = session.get('user_id')
            
            notification = Notification(
                user_id=user_id,
                type_notification='systeme',
                titre='Test de notification',
                message='Ceci est une notification de test pour vérifier que le système fonctionne correctement.',
                donnees=json.dumps({
                    'test': True,
                    'timestamp': datetime.now().isoformat()
                })
            )
            
            db.session.add(notification)
            db.session.commit()
            
            return jsonify({
                'success': True,
                'message': 'Notification de test créée avec succès'
            })
            
        except Exception as e:
            db.session.rollback()
            return jsonify({'success': False, 'message': str(e)})