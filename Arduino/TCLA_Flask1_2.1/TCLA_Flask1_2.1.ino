/*
  Code TCLab compatible - Capteur TMP36 + Contrôle PI/PID externe
  Version compatible avec contrôle PI/PID Flask
*/

// Pin definitions - TCLab standard
const int pinTMP36 = A0;       // TMP36 sur A0 (T1 du TCLab)
const int pinMOSFET = 9;       // MOSFET sur Pin 9 (Q1 du TCLab)  
const int pinLED = 3;          // LED sur Pin 3 (LED1 du TCLab)

// Configuration constants
const long baud = 115200;
const String vers = "3.2.0";   // 3.2.0 : watchdog réel (HB), verrou après coupure, commande ARM, pas de chauffe au démarrage

// Safety limits - TCLab standard
const float limTemperature = 90.0;  // Limite sécurité TCLab
const int limPWM = 255;             // Limite PWM complète pour contrôle externe

// Variables globales
float currentConsigne = 0.0;   // Consigne de température
float currentTemperature = 0.0; // Température actuelle
int currentPWM = 0;            // Valeur PWM actuelle (ENTIER)
bool controleActif = false;    // Contrôle actif ou non
int powerLimit = limPWM;       // Limite de puissance
String currentMode = "none";   // Mode reçu de Flask: "none", "pi", "pid"
bool externalControl = false;  // Contrôle externe actif (PWM du serveur)
unsigned long lastDataSent = 0; // Dernier envoi de données
const unsigned long dataInterval = 1000; // Intervalle d'envoi (1s)

// --- Watchdog de communication série ---
// Coupe automatiquement le chauffage si aucune commande valide n'est reçue
// pendant watchdogTimeout ms. Protège en cas de panne locale (PC qui plante,
// port USB qui se déconnecte, Flask qui crash...), indépendamment de tout
// ce qui se passe côté internet/tunnel/étudiants - cette liaison Arduino<->PC
// est en USB local, donc jamais affectée par la latence internet.
//
// RÈGLE (v3.2.0) : seules les commandes de RÉGULATION valides relancent le
// watchdog : PWM:xxx, SET:xx, Q1 xx et HB (battement de cœur envoyé par le
// SERVEUR). PING, TEMP, STATUS, T1, SCAN, VER, MODE ne le relancent PAS : l'agent
// local envoie PING toutes les 3 s, il ne doit pas masquer une panne du serveur
// ou d'Internet.
// Valeur de compilation (pas de variable d'environnement sur Arduino).
// Doit rester > 3 x l'intervalle de HB du serveur (HEARTBEAT_REGULATION_S = 2 s).
#define WATCHDOG_TIMEOUT_MS 10000UL
const unsigned long watchdogTimeout = WATCHDOG_TIMEOUT_MS;
unsigned long lastCommandeRecue = 0;
bool watchdogDeclenche = false;

// Verrou de sécurité : après un watchdog (ou une surchauffe) le chauffage reste
// à 0 et PWM/SET sont REFUSÉS jusqu'à une commande ARM explicite.
bool verrouille = false;
// Une consigne (SET) valide doit avoir été reçue avant tout chauffage en boucle
// ouverte : pas de chauffe à la mise sous tension ni au simple changement de mode.
bool consigneRecue = false;

// Prototypes (nécessaires pour compiler hors IDE Arduino, sans effet dans l'IDE)
void sendTemperatureData();
void processCommand(String command);
void readTMP36Temperature();
void applyControleContinual();
void setHeater(int pwmValue);
void updateLEDStatus();
void checkWatchdog();
void checkSafety();
void verrouiller(const char* statut);
void relancerWatchdog();

void setup() {
  Serial.begin(baud);
  pinMode(pinMOSFET, OUTPUT);
  pinMode(pinLED, OUTPUT);
  
  // Initialisation TCLab style
  setHeater(0);
  analogWrite(pinLED, 10); // LED faible comme TCLab
  
  Serial.println("TCLab TMP36 - Systeme pret (v" + vers + ")");
  Serial.println("Commandes: SET:XX, TEMP, STOP, MODE:XX, STATUS, Q1 XX, PWM:XXX, HB, ARM");
  Serial.println("STATUS: READY");
  
  // Démarrage SANS chauffage : le contrôle n'est activé qu'après réception
  // d'une consigne (SET) ou d'un PWM valide d'un utilisateur connecté.
  controleActif = false;
  externalControl = false;
  consigneRecue = false;
  currentConsigne = 25.0; // Consigne affichée par défaut (sans effet tant que consigneRecue = false)
  lastDataSent = millis();
  lastCommandeRecue = millis(); // Démarrage du watchdog
}

void loop() {
  // Lecture des commandes série
  if (Serial.available() > 0) {
    String command = Serial.readStringUntil('\n');
    command.trim();
    // Le watchdog n'est PLUS relancé ici : c'est processCommand() qui le relance,
    // uniquement pour les commandes de régulation valides.
    processCommand(command);
  }
  
  // Lecture température TMP36 régulière
  static unsigned long lastRead = 0;
  if (millis() - lastRead > 500) { // Lecture plus fréquente
    readTMP36Temperature();
    lastRead = millis();
    
    // Envoyer automatiquement la température au serveur
    if (millis() - lastDataSent > dataInterval) {
      sendTemperatureData();
      lastDataSent = millis();
    }
  }
  
  // Application du contrôle si actif (mode "none" seulement)
  if (controleActif && consigneRecue && !verrouille && currentMode == "none" && !externalControl) {
    applyControleContinual();
  }
  // En mode PI/PID, le contrôle est externe, on attend les commandes PWM
  
  checkSafety();
  checkWatchdog();
  updateLEDStatus();
  delay(100);
}

void sendTemperatureData() {
  // Envoyer la température au format compatible avec le serveur
  // FORMAT: DATA:temperature:consigne:pwm:mode
  Serial.print("DATA:");
  Serial.print(currentTemperature, 2);  // Température avec 2 décimales
  Serial.print(":");
  Serial.print(currentConsigne, 2);     // Consigne avec 2 décimales
  Serial.print(":");
  Serial.print(currentPWM);             // PWM actuelle (entier)
  Serial.print(":");
  Serial.println(currentMode);          // Mode actuel
}

void processCommand(String command) {
  // Commande SET:XX (format votre système Flask - mode "none")
  if (command.startsWith("SET:")) {
    String valueStr = command.substring(4);
    float newConsigne = valueStr.toFloat();
    
    if (verrouille && newConsigne > 0) {
      Serial.println("ERREUR: VERROUILLE (envoyer ARM)");
      Serial.println("STATUS: VERROUILLE");
    } else if (newConsigne >= 0 && newConsigne <= 100) {
      currentConsigne = newConsigne;
      
      // Ne pas activer le contrôle si on est en mode externe
      if (currentMode == "none" && !externalControl) {
        controleActif = true;
        consigneRecue = true;
      }
      if (!verrouille) relancerWatchdog(); // commande de régulation valide
      
      Serial.print("Consigne definie: ");
      Serial.print(currentConsigne);
      Serial.println("%");
      
      // Envoyer immédiatement les nouvelles données
      sendTemperatureData();
      
    } else {
      Serial.println("Erreur: Consigne 0-100%");
    }
  }
  
  // Commande PWM:XXX (envoyée par le serveur PI/PID)
  else if (command.startsWith("PWM:")) {
    String valueStr = command.substring(4);
    int pwmValue = valueStr.toInt();
    
    if (verrouille && pwmValue > 0) {
      // Verrou actif : seul PWM:0 (sans chauffe) est accepté, sans relancer le watchdog
      Serial.println("ERREUR: VERROUILLE (envoyer ARM)");
      Serial.println("STATUS: VERROUILLE");
    } else if (pwmValue >= 0 && pwmValue <= 255) {
      // Désactiver le contrôle interne, utiliser la PWM externe
      if (!verrouille) {
        externalControl = true;
        controleActif = false;
        relancerWatchdog(); // commande de régulation valide
      }
      setHeater(pwmValue);
      
      Serial.print("PWM recue: ");
      Serial.println(pwmValue);
      Serial.print("STATUS:");
      Serial.println(currentMode); // Confirmer le mode
    } else {
      Serial.println("Erreur: PWM 0-255");
    }
  }
  
  // Commande MODE:XXX (reçoit le mode de Flask)
  else if (command.startsWith("MODE:")) {
    String modeStr = command.substring(5);
    modeStr.toLowerCase();
    
    if (modeStr == "none" || modeStr == "pi" || modeStr == "pid") {
      String oldMode = currentMode;
      currentMode = modeStr;
      
      Serial.print("Mode change: ");
      Serial.print(oldMode);
      Serial.print(" -> ");
      Serial.println(currentMode);
      
      // Gérer la transition entre modes
      if (currentMode == "none") {
        // Mode boucle ouverte - contrôle local. Pas de chauffe tant qu'aucune
        // nouvelle consigne (SET) n'est reçue après le changement de mode.
        externalControl = false;
        controleActif = false;
        consigneRecue = false;
        // Arrêter toute PWM externe
        setHeater(0);
      } else {
        // Mode PI/PID - contrôle externe. Verrouillé : on n'active rien (chauffage à 0).
        // Sinon on démarre le watchdog à partir de maintenant : le serveur doit
        // envoyer PWM/HB dans le délai, sinon coupure + verrou.
        externalControl = !verrouille;
        controleActif = false;
        if (!verrouille) relancerWatchdog();
        // Arrêter le contrôle local, attendre les PWM du serveur
        setHeater(0);
      }
      
      // Confirmer le nouveau mode
      Serial.print("STATUS:");
      Serial.println(currentMode);
      
      // Envoyer les données avec le nouveau mode
      sendTemperatureData();
      
    } else {
      Serial.println("Erreur: Mode invalide (none, pi, pid)");
    }
  }
  
  // Commande STOP (arrêt)
  else if (command == "STOP") {
    controleActif = false;
    externalControl = false;
    consigneRecue = false;
    setHeater(0);
    currentMode = "none";
    Serial.println("Controle arrete");
    Serial.println("STATUS: STOPPED");
  }
  
  // Commande START (redémarrage contrôle)
  else if (command == "START") {
    if (currentMode == "none") {
      // START ne chauffe pas seul : il faut un SET valide (consigneRecue)
      controleActif = consigneRecue && !verrouille;
      externalControl = false;
      Serial.println("Controle local demarre");
      Serial.println("STATUS: none");
    } else {
      Serial.println("En attente de commandes PWM du serveur");
      Serial.print("STATUS:");
      Serial.println(currentMode);
    }
  }
  
  // Commande TEMP (lecture température)
  else if (command == "TEMP") {
    Serial.print("Temperature: ");
    Serial.print(currentTemperature);
    Serial.println("°C");
  }
  
  // Commande T1 (format TCLab original)
  else if (command == "T1") {
    Serial.println(currentTemperature, 3); // Format TCLab
  }
  
  // Commande Q1 XX (format TCLab original)
  else if (command.startsWith("Q1 ")) {
    String valueStr = command.substring(3);
    float newConsigne = valueStr.toFloat();
    
    if (verrouille && newConsigne > 0) {
      Serial.println("ERREUR: VERROUILLE (envoyer ARM)");
    } else if (newConsigne >= 0 && newConsigne <= 100) {
      currentConsigne = newConsigne;
      if (currentMode == "none" && !externalControl) {
        controleActif = true;
        consigneRecue = true;
      }
      if (!verrouille) relancerWatchdog(); // commande de régulation valide
      Serial.println(currentConsigne, 1); // Réponse format TCLab
    }
  }
  
  // Commande SCAN (format TCLab original)
  else if (command == "SCAN") {
    // Format: T1 T2 Q1 Q2 (comme TCLab)
    Serial.print(currentTemperature, 3);  // T1
    Serial.print(" ");
    Serial.print(0.0, 3);                // T2 (0 car 1 seul capteur)
    Serial.print(" ");
    Serial.print(currentConsigne, 1);     // Q1
    Serial.print(" ");
    Serial.println(0.0, 1);              // Q2 (0 car 1 seul chauffage)
  }
  
  // Commande STATUS (statut complet)
  else if (command == "STATUS") {
    Serial.println("=== STATUT TCLab TMP36 ===");
    Serial.print("Firmware: v");
    Serial.println(vers);
    Serial.print("Mode: ");
    Serial.println(currentMode);
    Serial.print("Controle: ");
    Serial.println(controleActif ? "ACTIF" : "INACTIF");
    Serial.print("Verrou: ");
    Serial.println(verrouille ? "OUI" : "NON");
    Serial.print("Controle externe: ");
    Serial.println(externalControl ? "ACTIF" : "INACTIF");
    Serial.print("Consigne: ");
    Serial.print(currentConsigne);
    Serial.println("%");
    Serial.print("Temperature: ");
    Serial.print(currentTemperature);
    Serial.println("°C");
    Serial.print("PWM: ");
    Serial.print(currentPWM);
    Serial.println("/255");
    Serial.println("========================");
  }
  
  // Commande VER (version)
  else if (command == "VER") {
    Serial.println("TCLab_TMP36_PI_PID v" + vers);
  }
  
  // Commande A (redémarrage)
  else if (command == "A") {
    // Redémarrage TCLab : remet à zéro SANS chauffer (une consigne SET est requise)
    controleActif = false;
    externalControl = false;
    consigneRecue = false;
    currentMode = "none";
    setHeater(0);
    Serial.println("Start");
  }
  
  // Commande X (arrêt TCLab)
  else if (command == "X") {
    controleActif = false;
    externalControl = false;
    consigneRecue = false;
    setHeater(0);
    Serial.println("Stop");
  }

  // Commande HB (battement de cœur de régulation, envoyé par le SERVEUR)
  // Ne relance le watchdog que si une régulation est en cours et non verrouillée.
  else if (command == "HB") {
    if (!verrouille && (controleActif || externalControl)) {
      relancerWatchdog();
    }
  }

  // Commande ARM : réarmement explicite après watchdog/surchauffe.
  // Lève le verrou mais NE chauffe PAS : il faut ensuite un SET ou PWM valide.
  else if (command == "ARM") {
    verrouille = false;
    watchdogDeclenche = false;
    controleActif = false;
    externalControl = false;
    consigneRecue = false;
    setHeater(0);
    lastCommandeRecue = millis();
    Serial.println("STATUS: ARMED");
  }
  
  // Commande PING (test connexion)
  else if (command == "PING") {
    Serial.println("PONG");
  }
  
  else if (command.length() > 0) {
    Serial.print("Commande inconnue: ");
    Serial.println(command);
  }
}

void readTMP36Temperature() {
  // LECTURE TMP36 avec moyennage (comme TCLab original)
  float degC = 0.0;
  int n = 5;  // 5 échantillons pour plus de rapidité
  
  for (int i = 0; i < n; i++) {
    int rawValue = analogRead(pinTMP36);
    
    // CONVERSION TMP36 - Formule TCLab originale
    float voltage = rawValue * (5.0 / 1023.0);
    degC += (voltage - 0.5) * 100; // Formule TMP36 standard
    
    delay(1);
  }
  
  float newTemp = degC / n;
  
  // Filtrage simple pour lisser les mesures
  static float filteredTemp = 0;
  filteredTemp = 0.7 * filteredTemp + 0.3 * newTemp;
  currentTemperature = filteredTemp;
}

void applyControleContinual() {
  // BOUCLE OUVERTE - Application directe comme TCLab
  int pwmValue = map(currentConsigne, 0, 100, 0, powerLimit);
  setHeater(pwmValue);
}

void setHeater(int pwmValue) {
  currentPWM = constrain(pwmValue, 0, powerLimit);
  analogWrite(pinMOSFET, currentPWM);
}

void updateLEDStatus() {
  // Gestion LED style TCLab
  if ((controleActif || externalControl) && currentPWM > 0) {
    analogWrite(pinLED, 60); // LED brillante quand chauffage actif
  } else {
    analogWrite(pinLED, 10); // LED faible quand inactif
  }
}

void relancerWatchdog() {
  lastCommandeRecue = millis();
  watchdogDeclenche = false;
}

void verrouiller(const char* statut) {
  // Coupe le chauffage et le garde à 0 jusqu'à une commande ARM explicite
  controleActif = false;
  externalControl = false;
  consigneRecue = false;
  setHeater(0);
  verrouille = true;
  Serial.print("STATUS: ");
  Serial.println(statut);
}

void checkWatchdog() {
  // Si aucune commande de RÉGULATION valide (PWM, SET, Q1, HB) n'est arrivée
  // depuis watchdogTimeout ms alors que le chauffage peut être actif, on
  // considère la liaison serveur rompue et on coupe. Le chauffage reste à 0
  // (verrou) jusqu'à une commande ARM explicite.
  if (!verrouille && (controleActif || externalControl || currentPWM > 0) &&
      (millis() - lastCommandeRecue > watchdogTimeout)) {
    if (!watchdogDeclenche) {
      Serial.println("ALERTE: Aucune commande de regulation recue - Watchdog active, chauffage coupe");
      watchdogDeclenche = true;
    }
    verrouiller("WATCHDOG");
  }
}

void checkSafety() {
  // Sécurité style TCLab : au-delà de limTemperature on coupe ET on verrouille
  if (currentTemperature > limTemperature) {
    if (!verrouille) {
      analogWrite(pinLED, 10); // LED faible
      Serial.println("ALERTE: Temperature > 90°C - Securite activee");
      verrouiller("SURCHAUFFE");
    }
  }
}
