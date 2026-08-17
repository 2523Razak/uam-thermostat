// Variables globales
let formulaireMdpActif = false;
let formulaireEmailActif = false;

// Fonction pour générer un hash MD5 (nécessaire pour Gravatar)
function md5(str) {
    let hash = 0;
    for (let i = 0; i < str.length; i++) {
        const char = str.charCodeAt(i);
        hash = ((hash << 5) - hash) + char;
        hash = hash & hash;
    }
    return Math.abs(hash).toString(16);
}

// Fonction pour obtenir l'avatar Gravatar
function genererGravatar(email) {
    const hash = md5(email.trim().toLowerCase());
    const size = 140;
    return `https://www.gravatar.com/avatar/${hash}?s=${size}&d=identicon&r=pg`;
}

// Fonction pour mettre à jour l'affichage du statut
function mettreAJourStatut(statut) {
    const statutBadge = document.getElementById('statut-badge');
    
    // Déterminer le texte et l'icône selon le statut
    let texteStatut, iconeStatut, classeStatut;
    
    switch(statut) {
        case 'admin':
            texteStatut = 'ADMINISTRATEUR';
            iconeStatut = 'fas fa-crown';
            classeStatut = 'badge-statut-admin';
            break;
        case 'bloque':
            texteStatut = 'COMPTE BLOQUÉ';
            iconeStatut = 'fas fa-ban';
            classeStatut = 'badge-statut-bloque';
            break;
        case 'user':
        default:
            texteStatut = 'UTILISATEUR';
            iconeStatut = 'fas fa-user';
            classeStatut = 'badge-statut-user';
            break;
    }
    
    // Mettre à jour le badge
    statutBadge.className = `badge ${classeStatut}`;
    statutBadge.innerHTML = `<i class="${iconeStatut}"></i> Statut: <strong>${texteStatut}</strong>`;
    
    console.log(`Statut mis à jour: ${statut} -> ${texteStatut}`);
}

// Fonction pour charger les données utilisateur
function chargerDonneesUtilisateur() {
    const userEmail = document.getElementById('current-email').textContent;
    
    // Générer et afficher l'avatar Gravatar
    if (userEmail) {
        const avatarUrl = genererGravatar(userEmail);
        document.getElementById('gravatar-avatar').src = avatarUrl;
    }
    
    // Essayer d'abord de récupérer le statut depuis l'API
    fetch('/api/current_user_info')
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                const user = data.utilisateur;
                
                // Mettre à jour le statut avec les données de l'API
                mettreAJourStatut(user.statut);
                
                // Mettre à jour les 4 cartes d'informations
                document.getElementById('info-organisation').textContent = user.organisation || 'Non définie';
                document.getElementById('info-matricule').textContent = user.matricule || 'Non défini';
                
                // Formater la date de naissance si elle existe
                if (user.date_naissance && user.date_naissance !== 'Non définie') {
                    // Convertir le format de date si nécessaire
                    try {
                        const dateParts = user.date_naissance.split('/');
                        if (dateParts.length === 3) {
                            document.getElementById('info-date-naissance').textContent = 
                                `${dateParts[2]}/${dateParts[1]}/${dateParts[0]}`;
                        } else {
                            document.getElementById('info-date-naissance').textContent = user.date_naissance;
                        }
                    } catch (e) {
                        document.getElementById('info-date-naissance').textContent = user.date_naissance;
                    }
                } else {
                    document.getElementById('info-date-naissance').textContent = 'Non définie';
                }
                
                document.getElementById('info-lieu-naissance').textContent = user.lieu_naissance || 'Non défini';
                
            } else {
                // Si l'API échoue, utiliser le statut de la session
                const sessionStatut = document.body.dataset.userStatut || 'user';
                mettreAJourStatut(sessionStatut);
                console.warn('API échouée, utilisation du statut session:', sessionStatut);
            }
        })
        .catch(error => {
            console.error('Erreur lors du chargement des données:', error);
            
            // En cas d'erreur, utiliser le statut de la session
            const sessionStatut = document.body.dataset.userStatut || 'user';
            mettreAJourStatut(sessionStatut);
            
            // Valeurs par défaut en cas d'erreur
            document.getElementById('info-organisation').textContent = 'Non définie';
            document.getElementById('info-matricule').textContent = 'Non défini';
            document.getElementById('info-date-naissance').textContent = 'Non définie';
            document.getElementById('info-lieu-naissance').textContent = 'Non défini';
        });
}

// Fonction pour évaluer la force du mot de passe
function evaluerForceMotDePasse(motDePasse) {
    let score = 0;
    const meter = document.getElementById('strength-meter');
    const label = document.getElementById('strength-label');
    
    if (!motDePasse) {
        meter.className = 'strength-meter';
        label.textContent = '';
        return;
    }
    
    // Longueur
    if (motDePasse.length >= 8) score++;
    if (motDePasse.length >= 12) score++;
    
    // Complexité
    if (/[A-Z]/.test(motDePasse)) score++;
    if (/[0-9]/.test(motDePasse)) score++;
    if (/[^A-Za-z0-9]/.test(motDePasse)) score++;
    
    // Déterminer la force
    if (score <= 2) {
        meter.className = 'strength-meter weak';
        label.textContent = 'Faible';
    } else if (score === 3) {
        meter.className = 'strength-meter fair';
        label.textContent = 'Moyen';
    } else if (score === 4) {
        meter.className = 'strength-meter good';
        label.textContent = 'Bon';
    } else {
        meter.className = 'strength-meter strong';
        label.textContent = 'Fort';
    }
}

// Fonction pour valider le formulaire de mot de passe
function validerFormulaireMdp() {
    const ancienMdp = document.getElementById('ancien-mdp').value;
    const nouveauMdp = document.getElementById('nouveau-mdp').value;
    const confirmationMdp = document.getElementById('confirmation-mdp').value;
    let isValid = true;
    
    // Réinitialiser les erreurs
    document.getElementById('ancien-mdp-error').style.display = 'none';
    document.getElementById('nouveau-mdp-error').style.display = 'none';
    document.getElementById('confirmation-mdp-error').style.display = 'none';
    
    // Valider ancien mot de passe
    if (!ancienMdp) {
        document.getElementById('ancien-mdp-error').textContent = 'Ce champ est obligatoire';
        document.getElementById('ancien-mdp-error').style.display = 'block';
        document.getElementById('ancien-mdp').classList.add('error');
        isValid = false;
    } else {
        document.getElementById('ancien-mdp').classList.remove('error');
    }
    
    // Valider nouveau mot de passe
    if (!nouveauMdp) {
        document.getElementById('nouveau-mdp-error').textContent = 'Ce champ est obligatoire';
        document.getElementById('nouveau-mdp-error').style.display = 'block';
        document.getElementById('nouveau-mdp').classList.add('error');
        isValid = false;
    } else if (nouveauMdp.length < 6) {
        document.getElementById('nouveau-mdp-error').textContent = 'Minimum 6 caractères';
        document.getElementById('nouveau-mdp-error').style.display = 'block';
        document.getElementById('nouveau-mdp').classList.add('error');
        isValid = false;
    } else {
        document.getElementById('nouveau-mdp').classList.remove('error');
    }
    
    // Valider confirmation
    if (!confirmationMdp) {
        document.getElementById('confirmation-mdp-error').textContent = 'Ce champ est obligatoire';
        document.getElementById('confirmation-mdp-error').style.display = 'block';
        document.getElementById('confirmation-mdp').classList.add('error');
        isValid = false;
    } else if (nouveauMdp && confirmationMdp !== nouveauMdp) {
        document.getElementById('confirmation-mdp-error').textContent = 'Les mots de passe ne correspondent pas';
        document.getElementById('confirmation-mdp-error').style.display = 'block';
        document.getElementById('confirmation-mdp').classList.add('error');
        isValid = false;
    } else if (confirmationMdp) {
        document.getElementById('confirmation-mdp').classList.remove('error');
        document.getElementById('confirmation-mdp').classList.add('success');
    }
    
    return isValid;
}

// Fonction pour valider le formulaire d'email
function validerFormulaireEmail() {
    const motDePasse = document.getElementById('mot-de-passe-email').value;
    const nouvelEmail = document.getElementById('nouvel-email').value;
    const confirmationEmail = document.getElementById('confirmation-email').value;
    let isValid = true;
    
    // Réinitialiser les erreurs
    document.getElementById('mot-de-passe-email-error').style.display = 'none';
    document.getElementById('nouvel-email-error').style.display = 'none';
    document.getElementById('confirmation-email-error').style.display = 'none';
    
    // Valider mot de passe
    if (!motDePasse) {
        document.getElementById('mot-de-passe-email-error').textContent = 'Ce champ est obligatoire';
        document.getElementById('mot-de-passe-email-error').style.display = 'block';
        document.getElementById('mot-de-passe-email').classList.add('error');
        isValid = false;
    } else {
        document.getElementById('mot-de-passe-email').classList.remove('error');
    }
    
    // Valider nouvel email
    if (!nouvelEmail) {
        document.getElementById('nouvel-email-error').textContent = 'Ce champ est obligatoire';
        document.getElementById('nouvel-email-error').style.display = 'block';
        document.getElementById('nouvel-email').classList.add('error');
        isValid = false;
    } else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(nouvelEmail)) {
        document.getElementById('nouvel-email-error').textContent = 'Format d\'email invalide';
        document.getElementById('nouvel-email-error').style.display = 'block';
        document.getElementById('nouvel-email').classList.add('error');
        isValid = false;
    } else {
        document.getElementById('nouvel-email').classList.remove('error');
        document.getElementById('nouvel-email').classList.add('success');
    }
    
    // Valider confirmation email
    if (!confirmationEmail) {
        document.getElementById('confirmation-email-error').textContent = 'Ce champ est obligatoire';
        document.getElementById('confirmation-email-error').style.display = 'block';
        document.getElementById('confirmation-email').classList.add('error');
        isValid = false;
    } else if (nouvelEmail && confirmationEmail !== nouvelEmail) {
        document.getElementById('confirmation-email-error').textContent = 'Les emails ne correspondent pas';
        document.getElementById('confirmation-email-error').style.display = 'block';
        document.getElementById('confirmation-email').classList.add('error');
        isValid = false;
    } else if (confirmationEmail) {
        document.getElementById('confirmation-email').classList.remove('error');
        document.getElementById('confirmation-email').classList.add('success');
    }
    
    return isValid;
}

// Fonction pour afficher un message
function afficherMessage(type, message, elementId) {
    const element = document.getElementById(elementId);
    element.textContent = message;
    element.className = `form-message ${type}`;
    element.style.display = 'block';
    
    // Masquer le message après 5 secondes
    setTimeout(() => {
        element.style.display = 'none';
    }, 5000);
}

// Fonction pour afficher le formulaire de changement de mot de passe
function afficherFormulaireMdp() {
    // Réinitialiser les formulaires
    fermerFormulaire();
    
    // Afficher overlay et formulaire
    document.getElementById('formulaire-overlay').style.display = 'block';
    document.getElementById('formulaire-mdp').style.display = 'block';
    formulaireMdpActif = true;
    
    // Réinitialiser les champs
    document.getElementById('ancien-mdp').value = '';
    document.getElementById('nouveau-mdp').value = '';
    document.getElementById('confirmation-mdp').value = '';
    document.getElementById('message-mdp').style.display = 'none';
    
    // Focus sur le premier champ
    setTimeout(() => {
        document.getElementById('ancien-mdp').focus();
    }, 100);
}

// Fonction pour afficher le formulaire de changement d'email
function afficherFormulaireEmail() {
    // Réinitialiser les formulaires
    fermerFormulaire();
    
    // Afficher overlay et formulaire
    document.getElementById('formulaire-overlay').style.display = 'block';
    document.getElementById('formulaire-email').style.display = 'block';
    formulaireEmailActif = true;
    
    // Réinitialiser les champs
    document.getElementById('mot-de-passe-email').value = '';
    document.getElementById('nouvel-email').value = '';
    document.getElementById('confirmation-email').value = '';
    document.getElementById('message-email').style.display = 'none';
    
    // Focus sur le premier champ
    setTimeout(() => {
        document.getElementById('mot-de-passe-email').focus();
    }, 100);
}

// Fonction pour fermer les formulaires
function fermerFormulaire() {
    document.getElementById('formulaire-overlay').style.display = 'none';
    document.getElementById('formulaire-mdp').style.display = 'none';
    document.getElementById('formulaire-email').style.display = 'none';
    formulaireMdpActif = false;
    formulaireEmailActif = false;
}

// Fonction pour changer le mot de passe
function changerMotDePasse() {
    // Validation
    if (!validerFormulaireMdp()) {
        return;
    }
    
    const ancienMdp = document.getElementById('ancien-mdp').value;
    const nouveauMdp = document.getElementById('nouveau-mdp').value;
    
    // Afficher l'indicateur de chargement
    const btnValider = document.getElementById('btn-valider-mdp');
    btnValider.classList.add('btn-loading');
    btnValider.disabled = true;
    
    // Appeler l'API pour changer le mot de passe
    fetch('/api/changer_mot_de_passe', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            ancien_mot_de_passe: ancienMdp,
            nouveau_mot_de_passe: nouveauMdp
        })
    })
    .then(response => response.json())
    .then(data => {
        // Réinitialiser le bouton
        btnValider.classList.remove('btn-loading');
        btnValider.disabled = false;
        
        if (data.success) {
            afficherMessage('success', '✅ Mot de passe changé avec succès!', 'message-mdp');
            
            // Réinitialiser le formulaire
            document.getElementById('ancien-mdp').value = '';
            document.getElementById('nouveau-mdp').value = '';
            document.getElementById('confirmation-mdp').value = '';
            document.getElementById('strength-meter').className = 'strength-meter';
            document.getElementById('strength-label').textContent = '';
            
            // Fermer le formulaire après 2 secondes
            setTimeout(() => {
                fermerFormulaire();
            }, 2000);
        } else {
            afficherMessage('error', '❌ Erreur: ' + data.message, 'message-mdp');
        }
    })
    .catch(error => {
        // Réinitialiser le bouton
        btnValider.classList.remove('btn-loading');
        btnValider.disabled = false;
        
        afficherMessage('error', '❌ Erreur lors du changement de mot de passe', 'message-mdp');
        console.error(error);
    });
}

// Fonction pour changer l'email
function changerEmail() {
    // Validation
    if (!validerFormulaireEmail()) {
        return;
    }
    
    const motDePasse = document.getElementById('mot-de-passe-email').value;
    const nouvelEmail = document.getElementById('nouvel-email').value;
    
    // Afficher l'indicateur de chargement
    const btnValider = document.getElementById('btn-valider-email');
    btnValider.classList.add('btn-loading');
    btnValider.disabled = true;
    
    // Appeler l'API pour changer l'email
    fetch('/api/changer_email', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            mot_de_passe: motDePasse,
            nouvel_email: nouvelEmail
        })
    })
    .then(response => response.json())
    .then(data => {
        // Réinitialiser le bouton
        btnValider.classList.remove('btn-loading');
        btnValider.disabled = false;
        
        if (data.success) {
            afficherMessage('success', '✅ Email changé avec succès!', 'message-email');
            
            // Mettre à jour l'affichage de l'email
            document.getElementById('current-email').textContent = nouvelEmail;
            
            // Mettre à jour l'avatar Gravatar
            const avatarUrl = genererGravatar(nouvelEmail);
            document.getElementById('gravatar-avatar').src = avatarUrl;
            
            // Réinitialiser le formulaire
            document.getElementById('mot-de-passe-email').value = '';
            document.getElementById('nouvel-email').value = '';
            document.getElementById('confirmation-email').value = '';
            
            // Fermer le formulaire après 2 secondes
            setTimeout(() => {
                fermerFormulaire();
            }, 2000);
        } else {
            afficherMessage('error', '❌ Erreur: ' + data.message, 'message-email');
        }
    })
    .catch(error => {
        // Réinitialiser le bouton
        btnValider.classList.remove('btn-loading');
        btnValider.disabled = false;
        
        afficherMessage('error', '❌ Erreur lors du changement d\'email', 'message-email');
        console.error(error);
    });
}

// Initialisation de l'application
document.addEventListener('DOMContentLoaded', function() {
    // Charger le mode sombre s'il était activé
    if (localStorage.getItem('darkMode') === 'true') {
        document.body.classList.add("mode-sombre-actif");
    }
    
    // Charger les données utilisateur
    chargerDonneesUtilisateur();
    
    // Configurer les événements
    if (document.getElementById('nouveau-mdp')) {
        document.getElementById('nouveau-mdp').addEventListener('input', function(e) {
            evaluerForceMotDePasse(e.target.value);
        });
    }
    
    if (document.getElementById('confirmation-mdp')) {
        document.getElementById('confirmation-mdp').addEventListener('input', function() {
            validerFormulaireMdp();
        });
    }
    
    if (document.getElementById('nouvel-email')) {
        document.getElementById('nouvel-email').addEventListener('input', function() {
            validerFormulaireEmail();
        });
    }
    
    if (document.getElementById('confirmation-email')) {
        document.getElementById('confirmation-email').addEventListener('input', function() {
            validerFormulaireEmail();
        });
    }
    
    // Gestionnaire pour fermer avec la touche Échap
    document.addEventListener('keydown', function(event) {
        if (event.key === 'Escape') {
            fermerFormulaire();
        }
    });
    
    // Empêcher la fermeture en cliquant dans le modal
    document.querySelectorAll('.formulaire-modal').forEach(modal => {
        modal.addEventListener('click', function(event) {
            event.stopPropagation();
        });
    });
    
    // Ajouter l'attribut de statut utilisateur au body pour y accéder
    const statutElements = document.querySelectorAll('[data-user-statut]');
    if (statutElements.length > 0) {
        document.body.dataset.userStatut = statutElements[0].dataset.userStatut;
    }
});