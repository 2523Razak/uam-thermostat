# Résumé des correctifs — Master projet Flask/Arduino

## 1. Étudiant(s) qui ne s'ajoutaient pas / liste vide
**Cause** : la recherche par matricule/email était sensible à la casse et aux espaces.
**Fix** : `api/tp.py` — recherche insensible casse/espaces, retour des identifiants
introuvables, rafraîchissement de la liste et du compteur depuis le serveur après sauvegarde.

## 2. Commentaire de correction remplacé par le commentaire général
**Cause** : `sauvegarder_correction` enregistrait le commentaire général dans le champ
par question, et ignorait le vrai commentaire par question envoyé par le formulaire.
**Fix** : nouvelle colonne `EtudiantTP.commentaire_general` dédiée ; le commentaire par
question est maintenant correctement lu et sauvegardé dans `ReponseEtudiant.commentaire_correction`
sans écraser accidentellement les commentaires existants quand une interface (ex.
"Consulter Soumissions") n'envoie pas ce champ.

## 3. Suppression de TP qui effaçait les copies soumises
**Fix** : suppression douce (`TP.supprime`). Le TP disparaît de la liste active du prof
et des étudiants n'ayant rien soumis, mais reste visible en lecture/note pour les
étudiants ayant déjà soumis, et reste corrigeable par l'enseignant. Les nouvelles
soumissions sont bloquées sur un TP supprimé.

## 4. QCM / cases à cocher peu lisibles
**Fix** : affichage du vrai texte des options (au lieu de "Option A/B/C/D" factices)
dans `correction_tp.html`, et correction de `formatReponse()` dans
`consulter_soumissions.js` qui traitait les réponses comme des index numériques.

## 5. Dialogues stylisés
**Fix** : nouveau composant `static/js/dialogs.js` (`appConfirm()`/`appAlert()`) qui
remplace tous les `confirm()`/`alert()` natifs du navigateur dans toute l'application.

## 6. Sécurité (hébergement)
- Mots de passe hachés (migration transparente : les anciens mots de passe en clair
  continuent de fonctionner et sont ré-hachés automatiquement à la prochaine connexion).
- Protection CSRF (Flask-WTF) sur toute l'app, jeton injecté automatiquement dans tous
  les appels `fetch()` via `static/js/security.js`.
- En-têtes HTTP de sécurité, limiteur anti-bruteforce sur la connexion.
- Secrets (SECRET_KEY, AGENT_SHARED_SECRET, identifiants email) déplacés vers variables
  d'environnement — plus rien en dur dans le code.
- Migration de schéma automatique au démarrage (fonctionne aussi sous gunicorn).

## Variables d'environnement à définir sur votre serveur (Render/Railway/etc.)

| Variable | Obligatoire | Description |
|---|---|---|
| `SECRET_KEY` | Oui (prod) | Clé secrète Flask, générez avec `python -c "import secrets; print(secrets.token_hex(32))"` |
| `AGENT_SHARED_SECRET` | Oui (prod) | Secret partagé avec l'agent local Arduino |
| `MAIL_USERNAME` | Oui | Adresse email d'envoi (Gmail) |
| `MAIL_PASSWORD` | Oui | Mot de passe d'application Gmail (pas le mot de passe du compte) |
| `MAIL_DEFAULT_SENDER` | Non | Nom affiché comme expéditeur |
| `ADMIN_DEFAULT_PASSWORD` | Recommandé | Mot de passe du compte admin créé au premier démarrage (sinon un mot de passe aléatoire est généré et affiché dans les logs) |
| `DATABASE_URL` | Non | URL de connexion à la base (sinon SQLite local) |
| `FORCE_HTTPS_COOKIES` | Non | Mettre à `false` seulement si vous testez en HTTP local |

⚠️ Sans `SECRET_KEY` et `AGENT_SHARED_SECRET` définis, l'application refusera de démarrer
en environnement de production (Render/Railway détectés automatiquement).
