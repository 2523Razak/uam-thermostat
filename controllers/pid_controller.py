# controllers/pid_controller.py - Contrôleurs PI/PID
import time

class PIController:
    """Contrôleur Proportionnel-Intégral (PI) - Fallback"""
    def __init__(self, kp=1.0, ki=0.1, setpoint=25.0):
        self.kp = kp
        self.ki = ki
        self.setpoint = setpoint
        self.last_error = 0
        self.integral = 0
        self.last_time = time.time()
        self.output = 0
        self.error = 0
        self.p_term = 0
        self.i_term = 0
        
    def update(self, current_value):
        """Calcule la sortie du contrôleur PI"""
        current_time = time.time()
        dt = current_time - self.last_time
        
        if dt <= 0:
            return self.output
        
        # Calcul de l'erreur
        self.error = self.setpoint - current_value
        
        # Terme proportionnel
        self.p_term = self.kp * self.error
        
        # Terme intégral avec anti-windup
        self.integral += self.error * dt
        self.i_term = self.ki * self.integral
        
        # Calcul de la sortie
        self.output = self.p_term + self.i_term
        
        # Anti-windup: limiter l'intégrale si la sortie est saturée
        if self.output >= 100 or self.output <= 0:
            self.integral -= self.error * dt
        
        # Limiter la sortie entre 0 et 100
        self.output = max(0, min(100, self.output))
        
        # Mise à jour pour la prochaine itération
        self.last_error = self.error
        self.last_time = current_time
        
        return self.output
    
    def reset(self):
        """Réinitialise le contrôleur"""
        self.last_error = 0
        self.integral = 0
        self.last_time = time.time()
        self.output = 0
        self.error = 0
        self.p_term = 0
        self.i_term = 0
    
    def set_parameters(self, kp, ki):
        """Définit les paramètres du contrôleur"""
        self.kp = kp
        self.ki = ki

class PIDController:
    """Contrôleur Proportionnel-Intégral-Dérivé (PID) - Fallback"""
    def __init__(self, kp=1.0, ki=0.1, kd=0.05, setpoint=25.0):
        self.kp = kp
        self.ki = ki
        self.kd = kd
        self.setpoint = setpoint
        self.last_error = 0
        self.integral = 0
        self.last_time = time.time()
        self.output = 0
        self.error = 0
        self.p_term = 0
        self.i_term = 0
        self.d_term = 0
    
    def update(self, current_value):
        """Calcule la sortie du contrôleur PID"""
        current_time = time.time()
        dt = current_time - self.last_time
        
        if dt <= 0:
            return self.output
        
        # Calcul de l'erreur
        self.error = self.setpoint - current_value
        
        # Terme proportionnel
        self.p_term = self.kp * self.error
        
        # Terme intégral avec anti-windup
        self.integral += self.error * dt
        self.i_term = self.ki * self.integral
        
        # Terme dérivé
        derivative = (self.error - self.last_error) / dt
        self.d_term = self.kd * derivative
        
        # Calcul de la sortie
        self.output = self.p_term + self.i_term + self.d_term
        
        # Anti-windup: limiter l'intégrale si la sortie est saturée
        if self.output >= 100 or self.output <= 0:
            self.integral -= self.error * dt
        
        # Limiter la sortie entre 0 et 100
        self.output = max(0, min(100, self.output))
        
        # Mise à jour pour la prochaine itération
        self.last_error = self.error
        self.last_time = current_time
        
        return self.output
    
    def reset(self):
        """Réinitialise le contrôleur"""
        self.last_error = 0
        self.integral = 0
        self.last_time = time.time()
        self.output = 0
        self.error = 0
        self.p_term = 0
        self.i_term = 0
        self.d_term = 0
    
    def set_parameters(self, kp, ki, kd):
        """Définit les paramètres du contrôleur"""
        self.kp = kp
        self.ki = ki
        self.kd = kd