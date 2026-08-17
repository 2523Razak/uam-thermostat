# utils/data_export.py - Export de données
import csv
import io
from datetime import datetime
from flask import Response

def exporter_donnees_csv(donnees, export_type='complet'):
    """Exporte les données en format CSV"""
    output = io.StringIO()
    writer = csv.writer(output, delimiter=';')
    
    if export_type == 'complet':
        writer.writerow([
            'Date', 'Heure', 'Timestamp', 'Température (°C)', 'Consigne (°C)', 
            'Valeur PWM', 'Mode contrôleur', 'Surveillance active',
            'Erreur (°C)', 'Terme P (%)', 'Terme I (%)', 'Terme D (%)', 'Sortie contrôleur (%)',
            'Kp', 'Ki', 'Kd', 'Consigne contrôleur (°C)'
        ])
        
        for donnee in donnees:
            dt_object = datetime.fromtimestamp(donnee['timestamp'])
            date_str = dt_object.strftime('%d/%m/%Y')
            heure_str = dt_object.strftime('%H:%M:%S')
            timestamp_str = str(donnee['timestamp'])
            
            # Gestion sécurisée de controller_data
            controller_data = donnee.get('controller_data') or {}
            error = controller_data.get('error', 0) if controller_data else 0
            p_term = controller_data.get('p_term', 0) if controller_data else 0
            i_term = controller_data.get('i_term', 0) if controller_data else 0
            d_term = controller_data.get('d_term', 0) if controller_data else 0
            output_ctrl = controller_data.get('output', 0) if controller_data else 0
            
            kp = donnee.get('kp', 0)
            ki = donnee.get('ki', 0)
            kd = donnee.get('kd', 0)
            
            writer.writerow([
                date_str,
                heure_str,
                timestamp_str,
                f"{donnee['temperature']:.2f}".replace('.', ','),
                f"{donnee['consigne']:.2f}".replace('.', ','),
                donnee.get('valeur_pwm', 0),
                donnee.get('type_controleur', 'aucun'),
                'Oui' if donnee.get('surveillance_active', False) else 'Non',
                f"{error:.4f}".replace('.', ','),
                f"{p_term:.4f}".replace('.', ','),
                f"{i_term:.4f}".replace('.', ','),
                f"{d_term:.4f}".replace('.', ','),
                f"{output_ctrl:.2f}".replace('.', ','),
                f"{kp:.4f}".replace('.', ','),
                f"{ki:.4f}".replace('.', ','),
                f"{kd:.4f}".replace('.', ','),
                f"{donnee.get('consigne', 0):.2f}".replace('.', ',')
            ])
    else:
        # Export résumé
        writer.writerow([
            'Date', 'Heure', 'Température (°C)', 'Consigne (°C)', 
            'Valeur PWM', 'Mode contrôleur', 'Surveillance active',
            'Erreur (°C)', 'Sortie contrôleur (%)', 'Kp', 'Ki', 'Kd'
        ])
    
    output.seek(0)
    return output

def creer_reponse_csv(output, filename):
    """Crée une réponse Flask avec fichier CSV"""
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={
            "Content-Disposition": f"attachment;filename={filename}",
            "Content-Type": "text/csv; charset=utf-8"
        }
    )