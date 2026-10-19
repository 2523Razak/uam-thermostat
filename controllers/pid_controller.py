# controllers/pid_controller.py - Contrôleurs PI/PID (version anti-dépassement)
#
# Mêmes classes, mêmes méthodes et mêmes attributs que l'ancienne version
# (update, reset, set_parameters, error, p_term, i_term, d_term, output, integral,
# last_error, last_time) : aucun autre fichier n'a besoin d'être modifié.
#
# Améliorations :
#  - dt borné (liaison internet lente : une mesure peut arriver 16 s après la précédente)
#  - anti-windup par « clamping » : l'intégrale ne grossit pas quand la sortie est saturée
#    dans le sens de l'erreur, et elle est bornée (i_term toujours dans 0..100 %)
#  - dépassement : si la température est au-dessus de la consigne, l'intégrale est
#    déchargée plus vite (DECHARGE_DEPASSEMENT x)
#  - dérivée sur la MESURE (pas de coup de dérivée à un changement de consigne) et filtrée
#    (le bruit du TMP36 n'est plus amplifié)
#
# Pour ne pas dépasser la consigne, le réglage des gains compte autant que le code : avec
# un Kp trop faible la sortie ne sature jamais, l'intégrale s'accumule pendant toute la
# montée et le dépassement est inévitable (voir docs/PID_REGLAGE.md).
import os
import time


def _env_float(nom, defaut):
    try:
        return float(os.environ.get(nom, defaut))
    except (TypeError, ValueError):
        return float(defaut)


DT_MAX_S = _env_float('PID_DT_MAX_S', 20.0)                 # dt maximal utilisé (couvre une liaison à ~16 s)
DECHARGE_DEPASSEMENT = _env_float('PID_DECHARGE_DEPASSEMENT', 3.0)  # vitesse de décharge si T > consigne
TAU_FILTRE_S = _env_float('PID_TAU_FILTRE_S', 5.0)          # constante de temps du filtre de la dérivée (s)
SORTIE_MIN = 0.0
SORTIE_MAX = 100.0


class _Base:
    """Calcul commun PI/PID. kd = 0 pour un PI."""

    def __init__(self, kp, ki, kd, setpoint):
        self.kp = kp
        self.ki = ki
        self.kd = kd
        self.setpoint = setpoint
        self.reset()

    def reset(self):
        """Réinitialise le contrôleur (intégrale et dérivée à zéro)."""
        self.last_error = 0
        self.integral = 0
        self.last_time = time.time()
        self.output = 0
        self.error = 0
        self.p_term = 0
        self.i_term = 0
        self.d_term = 0
        self._derniere_mesure = None
        self._derivee_filtree = 0.0

    def _calculer(self, mesure):
        maintenant = time.time()
        dt = maintenant - self.last_time
        if dt <= 0:
            return self.output
        dt_reel = dt                 # écart réel entre deux mesures (pour la vitesse de variation)
        dt = min(dt, DT_MAX_S)       # dt utilisé pour l'intégrale

        self.error = self.setpoint - mesure

        # --- Proportionnel
        self.p_term = self.kp * self.error

        # --- Dérivée sur la mesure, filtrée (signe : une mesure qui monte freine)
        if self._derniere_mesure is not None:
            brute = -(mesure - self._derniere_mesure) / dt_reel
            alpha = dt_reel / (TAU_FILTRE_S + dt_reel)   # filtre du 1er ordre, indépendant de dt
            self._derivee_filtree += alpha * (brute - self._derivee_filtree)
        else:
            self._derivee_filtree = 0.0
        self.d_term = self.kd * self._derivee_filtree

        # --- Intégrale
        if self.ki > 0:
            i_max = SORTIE_MAX / self.ki
            if self.error < 0:
                # Dépassement : décharge active de l'intégrale
                self.integral += self.error * dt * DECHARGE_DEPASSEMENT
            else:
                # Clamping : pas d'accumulation si la sortie est déjà saturée à 100 %
                sortie_sans_i = self.p_term + self.ki * self.integral + self.d_term
                if sortie_sans_i < SORTIE_MAX:
                    self.integral += self.error * dt
            self.integral = max(0.0, min(i_max, self.integral))
        self.i_term = self.ki * self.integral

        # --- Sortie bornée
        self.output = max(SORTIE_MIN, min(SORTIE_MAX, self.p_term + self.i_term + self.d_term))

        self._derniere_mesure = mesure
        self.last_error = self.error
        self.last_time = maintenant
        return self.output


class PIController(_Base):
    """Contrôleur Proportionnel-Intégral (PI)"""

    def __init__(self, kp=1.0, ki=0.1, setpoint=25.0):
        super().__init__(kp, ki, 0.0, setpoint)

    def update(self, current_value):
        """Calcule la sortie du contrôleur PI (0..100 %)"""
        return self._calculer(current_value)

    def set_parameters(self, kp, ki):
        """Définit les paramètres du contrôleur"""
        self.kp = kp
        self.ki = ki


class PIDController(_Base):
    """Contrôleur Proportionnel-Intégral-Dérivé (PID)"""

    def __init__(self, kp=1.0, ki=0.1, kd=0.05, setpoint=25.0):
        super().__init__(kp, ki, kd, setpoint)

    def update(self, current_value):
        """Calcule la sortie du contrôleur PID (0..100 %)"""
        return self._calculer(current_value)

    def set_parameters(self, kp, ki, kd):
        """Définit les paramètres du contrôleur"""
        self.kp = kp
        self.ki = ki
        self.kd = kd
