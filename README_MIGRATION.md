# Hébergement du site + cartes Arduino en local — Guide de migration

## 1. Ce qui a changé

**Avant :** Flask (avec les templates, la base de données, `arduino_controller.py`)
tournait sur ta machine locale, et un tunnel WebSocket (`ngrok-tunnel/client.py`
↔ `server_4.py` sur Render) exposait tout ça publiquement.

**Maintenant :** Flask (site + base de données + logique métier) tourne
directement sur le serveur hébergé (Render/Railway). Les cartes Arduino
restent branchées **en local**, gérées par un petit programme séparé :
`agent_local/agent_arduino.py`. Le serveur et l'agent communiquent via un
canal WebSocket permanent (Socket.IO, namespace `/agent`).

```
[Navigateur étudiant] ──HTTPS──▶ [Serveur Render : app.py + Socket.IO]
                                          ▲
                                          │ WebSocket (wss://.../socket.io)
                                          │ namespace /agent
                                          ▼
                          [Ta machine locale : agent_arduino.py]
                                          │
                                       USB série
                                          ▼
                                  [Cartes Arduino]
```

## 2. Fichiers modifiés / ajoutés

| Fichier | Changement |
|---|---|
| `controllers/arduino_controller.py` | Réécrit : ne touche plus pyserial, communique avec l'agent via Socket.IO. Mêmes structures de données (`connexions_arduino`, etc.), donc le reste de l'app n'a presque rien à changer. |
| `api/arduino.py` | Les 4 endroits qui écrivaient directement sur `port_serie` appellent maintenant `arduino_controller.envoyer_commande_brute(...)`. |
| `app.py` | Ajout de Flask-SocketIO, suppression du tunnel HTTP embarqué (devenu inutile), ajout du hub `/agent` et de la page `/admin/logs`. |
| `sockets/agent_hub.py` | **Nouveau.** Reçoit les connexions de l'agent local. |
| `utils/log_bus.py` | **Nouveau.** Journal d'événements en mémoire pour la page de supervision. |
| `api/admin_logs.py` + `templates/admin/logs.html` | **Nouveau.** Page `/admin/logs` : agents connectés, cartes détectées, journal en direct. |
| `agent_local/agent_arduino.py` | **Nouveau.** Le programme à lancer sur ta machine locale. |
| `requirements.txt` | Retiré : `pyserial`, FastAPI/uvicorn/websockets (plus utilisés côté serveur). Ajouté : `flask-socketio`, `eventlet`, `gunicorn`. |
| `Procfile` | **Nouveau.** Commande de démarrage Render. |

`tunnel_service.py`, `server_4.py` et le dossier `ngrok-tunnel/` ne sont plus
utilisés — je les ai laissés dans le projet pour référence, tu peux les
supprimer une fois que tu as confirmé que tout fonctionne.

## 3. Déploiement du serveur (Render)

1. Pousse ce dossier sur un dépôt Git (GitHub/GitLab), Render s'y connecte.
2. Crée un **Web Service** Render pointant sur ce dépôt.
3. Render détecte le `Procfile` automatiquement. Vérifie que la commande de
   démarrage est bien :
   ```
   gunicorn --worker-class eventlet -w 1 app:app --bind 0.0.0.0:$PORT --timeout 120
   ```
   ⚠️ **`-w 1` (un seul worker) est obligatoire** : les connexions Arduino et
   les agents sont gardés en mémoire, pas partagés entre plusieurs workers.
4. Variables d'environnement à définir dans Render (onglet *Environment*) :
   - `AGENT_SHARED_SECRET` → un jeton long et aléatoire (ex: généré avec
     `python -c "import secrets;print(secrets.token_hex(32))"`)
   - `PUBLIC_BASE_URL` → l'URL Render une fois connue, ex.
     `https://uam-thermostat.onrender.com`
   - (recommandé) déplace aussi `SECRET_KEY`, `MAIL_PASSWORD` dans des
     variables d'environnement plutôt que dans `app.py` en clair, puisque le
     code sera maintenant sur un vrai serveur public.
5. Déploie. Render assigne le plan gratuit à `sleep` après inactivité — si
   ça pose problème pour un labo en direct, prévois un plan payant "always on".

## 4. Mise en place de l'agent local (au labo, avec les cartes Arduino)

1. Copie le dossier `agent_local/` sur la machine où sont branchées les
   cartes (peut être différente de ta machine de dev).
2. Installe Python 3 si besoin, puis :
   ```
   pip install -r requirements_agent.txt
   ```
3. Double-clique `Demarrer_Agent_Local.bat` (Windows). Au premier lancement,
   il crée `config_agent.json` — édite-le :
   ```json
   {
     "server_url": "https://uam-thermostat.onrender.com",
     "agent_token": "LE_MEME_JETON_QUE_AGENT_SHARED_SECRET",
     "agent_id": null,
     "intervalle_scan_ports_s": 5,
     "intervalle_heartbeat_s": 10
   }
   ```
4. Relance `Demarrer_Agent_Local.bat`. La fenêtre doit rester ouverte tant
   que tu veux que les cartes soient utilisables sur le site (comme avant
   avec le tunnel). Tu peux réutiliser `Installer_Demarrage_Boot_Windows.bat`
   / le Planificateur de tâches Windows en l'adaptant pour lancer
   `agent_arduino.py` automatiquement au démarrage, comme tu le faisais déjà
   pour Thermostat UAM.

## 5. Page d'entretien / supervision

Une fois connecté en tant qu'administrateur : **`/admin/logs`**

- **Agents locaux** : en ligne / hors-ligne, nombre de cartes détectées,
  dernière activité.
- **Connexions Arduino actives** : qui est connecté, à quelle carte,
  température/consigne en direct.
- **Journal d'événements** : filtrable par niveau (info/warning/error) et
  par source (agent, arduino, controle, system), rafraîchi toutes les 5s.

C'est le premier endroit à regarder en cas de problème : si l'agent
apparaît hors-ligne, le souci est du côté de la machine locale ou de sa
connexion Internet ; s'il est en ligne mais qu'une carte ne répond pas,
regarde le journal pour l'événement `arduino` correspondant.

## 6. Points d'attention

- **Un seul worker gunicorn.** Si tu as besoin de scaler plus tard (plusieurs
  workers ou instances), il faudra déplacer l'état (connexions, agents,
  logs) vers Redis — pas nécessaire pour l'usage actuel.
- **`AGENT_SHARED_SECRET` doit être secret** : c'est ce qui empêche
  n'importe qui sur Internet de se faire passer pour ton agent et de
  piloter les cartes.
- **Reconnexion automatique** : si Internet coupe côté agent, il retente la
  connexion toutes les 2 à 15s (backoff) grâce à `python-socketio`. Le
  serveur marque alors les connexions Arduino correspondantes comme
  inactives après ~20s sans nouvelles de l'agent.
- Le fichier `agent_local/logs/agent_AAAAMM.log` garde un historique local
  sur la machine du labo — utile si tu dois diagnostiquer un problème
  matériel (carte débranchée, câble USB, etc.) sans accès Internet.
