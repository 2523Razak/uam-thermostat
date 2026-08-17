// Variables globales pour stocker les données des popups
let utilisateurEnCours = {
    id: null,
    nom: '',
    statut: '',
    action: ''
};

// Variables pour les filtres
let filtreOrganisationActif = 'tous';
let filtreStatutActif = 'tous';
let termeRechercheActif = '';

// Initialisation
document.addEventListener('DOMContentLoaded', function() {
    initialiserDate();
    initialiserRecherche();
    initialiserPopups();
});

// ========== FONCTIONS D'INITIALISATION ==========

function initialiserDate() {
    const maintenant = new Date();
    const options = { day: '2-digit', month: '2-digit', year: 'numeric' };
    const dateFormatee = maintenant.toLocaleDateString('fr-FR', options);
    
    const elementDate = document.getElementById('date-actuelle');
    if (elementDate) {
        elementDate.textContent = dateFormatee;
    }
    
    const totalInscrits = document.getElementById('total-inscrits');
    if (totalInscrits && totalInscrits.textContent === '') {
        totalInscrits.textContent = '0';
    }
}

function initialiserRecherche() {
    const champRecherche = document.getElementById('champRecherche');
    
    if (champRecherche) {
        champRecherche.addEventListener('input', function() {
            termeRechercheActif = this.value.toLowerCase().trim();
            appliquerFiltres();
        });
    }
}

function initialiserPopups() {
    // Fermer les popups en cliquant à l'extérieur
    document.querySelectorAll('.popup-overlay').forEach(overlay => {
        overlay.addEventListener('click', function(e) {
            if (e.target === this) {
                fermerPopup(this.id);
            }
        });
    });
    
    // Fermer les popups avec la touche Échap
    document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape') {
            fermerPopup('popupConfirmation');
            fermerPopup('popupBlocage');
            fermerPopup('popupSuppression');
            fermerCustomConfirm();
        }
    });
}

// ========== FONCTIONS DE GESTION DES POPUPS ==========

function afficherPopup(popupId) {
    const popup = document.getElementById(popupId);
    if (popup) {
        popup.classList.add('active');
        document.body.style.overflow = 'hidden';
    }
}

function fermerPopup(popupId) {
    const popup = document.getElementById(popupId);
    if (popup) {
        popup.classList.remove('active');
        document.body.style.overflow = '';
        
        if (popupId === 'popupBlocage') {
            document.getElementById('raisonBlocage').value = '';
        }
    }
}

// ========== FONCTIONS DE NOTIFICATION ==========

function afficherNotification(message, type = 'success') {
    const notification = document.getElementById('notification');
    if (notification) {
        notification.textContent = message;
        notification.className = `notification ${type} show`;
        
        setTimeout(() => {
            notification.classList.remove('show');
        }, 4000);
    }
}

// ========== FONCTIONS DE POPUPS SPÉCIFIQUES ==========

function afficherPopupConfirmation(idUtilisateur, statut, nomUtilisateur) {
    utilisateurEnCours.id = idUtilisateur;
    utilisateurEnCours.statut = statut;
    utilisateurEnCours.nom = nomUtilisateur;
    utilisateurEnCours.action = 'changerStatut';
    
    let actionText = '';
    let titre = '';
    
    switch(statut) {
        case 'admin':
            actionText = 'nommer Administrateur';
            titre = 'Nommer Administrateur';
            break;
        case 'bloque':
            actionText = 'bloquer';
            titre = 'Bloquer l\'utilisateur';
            break;
        default:
            actionText = 'définir comme Utilisateur standard';
            titre = 'Définir comme Utilisateur';
    }
    
    document.getElementById('popupConfirmationTitre').textContent = titre;
    document.getElementById('popupConfirmationMessage').innerHTML = `
        <strong>Êtes-vous sûr de vouloir ${actionText} cet utilisateur ?</strong><br><br>
        👤 <strong>Utilisateur :</strong> ${nomUtilisateur}<br>
        🆔 <strong>ID :</strong> ${idUtilisateur}<br><br>
        <span style="color: #28a745;">✅ Un email de notification sera automatiquement envoyé à l'utilisateur.</span>
    `;
    
    afficherPopup('popupConfirmation');
}

function afficherPopupBlocage(idUtilisateur, nomUtilisateur) {
    utilisateurEnCours.id = idUtilisateur;
    utilisateurEnCours.statut = 'bloque';
    utilisateurEnCours.nom = nomUtilisateur;
    utilisateurEnCours.action = 'bloquer';
    
    document.getElementById('popupBlocageMessage').innerHTML = `
        <strong>Veuillez saisir la raison du blocage (optionnel) :</strong><br><br>
        👤 <strong>Utilisateur :</strong> ${nomUtilisateur}<br>
        🆔 <strong>ID :</strong> ${idUtilisateur}
    `;
    
    document.getElementById('raisonBlocage').value = '';
    afficherPopup('popupBlocage');
}

function confirmerChangementStatut() {
    if (utilisateurEnCours.statut === 'bloque') {
        afficherPopupBlocage(utilisateurEnCours.id, utilisateurEnCours.nom);
    } else {
        executerChangementStatut(utilisateurEnCours.id, utilisateurEnCours.statut);
    }
    fermerPopup('popupConfirmation');
}

function confirmerBlocage() {
    const raison = document.getElementById('raisonBlocage').value.trim();
    executerChangementStatut(utilisateurEnCours.id, 'bloque', raison);
    fermerPopup('popupBlocage');
}

function supprimerUtilisateur(idUtilisateur, nomUtilisateur) {
    utilisateurEnCours.id = idUtilisateur;
    utilisateurEnCours.nom = nomUtilisateur;
    utilisateurEnCours.action = 'supprimer';
    
    document.getElementById('popupSuppressionMessage').innerHTML = `
        <strong>Êtes-vous sûr de vouloir supprimer définitivement cet utilisateur ?</strong><br><br>
        👤 <strong>Utilisateur :</strong> ${nomUtilisateur}<br>
        🆔 <strong>ID :</strong> ${idUtilisateur}
    `;
    
    afficherPopup('popupSuppression');
}

function confirmerSuppression() {
    fermerPopup('popupSuppression');
    
    fetch('/api/supprimer_utilisateur', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            id_utilisateur: utilisateurEnCours.id
        })
    })
    .then(response => {
        if (!response.ok) {
            throw new Error('Erreur réseau');
        }
        return response.json();
    })
    .then(data => {
        console.log('Réponse API:', data);
        
        if (data.success) {
            // Supprimer la ligne du tableau
            const ligne = document.querySelector(`.ligne-utilisateur[data-user-id="${utilisateurEnCours.id}"]`);
            if (ligne) {
                ligne.remove();
                
                // Mettre à jour le compteur total des inscrits
                const totalInscrits = document.getElementById('total-inscrits');
                if (totalInscrits) {
                    const nouveauTotal = parseInt(totalInscrits.textContent) - 1;
                    totalInscrits.textContent = Math.max(0, nouveauTotal);
                }
            }
            
            afficherNotification(`✅ ${data.message}`);
            
            // Vérification si plus d'utilisateurs
            setTimeout(() => {
                const lignesRestantes = document.querySelectorAll('.ligne-utilisateur').length;
                if (lignesRestantes === 0) {
                    window.location.reload();
                } else {
                    appliquerFiltres();
                }
            }, 500);
        } else {
            afficherNotification(`❌ ${data.message}`, 'error');
        }
    })
    .catch(error => {
        console.error('Erreur:', error);
        afficherNotification('Erreur de connexion au serveur', 'error');
    });
}

// ========== FONCTIONS DE FILTRAGE ==========

function filtrerParOrganisation(organisation) {
    filtreOrganisationActif = organisation;
    const champRecherche = document.getElementById('champRecherche');
    if (champRecherche) {
        champRecherche.value = '';
    }
    termeRechercheActif = '';
    appliquerFiltres();
}

function filtrerParStatut(statut) {
    filtreStatutActif = statut;
    const champRecherche = document.getElementById('champRecherche');
    if (champRecherche) {
        champRecherche.value = '';
    }
    termeRechercheActif = '';
    appliquerFiltres();
}

function appliquerFiltres() {
    const lignes = document.querySelectorAll('.ligne-utilisateur');
    
    lignes.forEach(ligne => {
        const nomUtilisateur = ligne.querySelector('.nom-utilisateur').textContent.toLowerCase();
        const email = ligne.querySelector('.cellule-donnee:nth-child(6)').textContent.toLowerCase();
        const matricule = ligne.querySelector('.cellule-donnee:nth-child(2)').textContent.toLowerCase();
        const organisation = ligne.getAttribute('data-organisation').toLowerCase(); 
        const statutLigne = ligne.getAttribute('data-statut');

        // 1. Filtrer par Recherche
        const correspondRecherche = (
            nomUtilisateur.includes(termeRechercheActif) ||
            email.includes(termeRechercheActif) ||
            matricule.includes(termeRechercheActif) ||
            organisation.includes(termeRechercheActif) ||
            termeRechercheActif === ''
        );
        
        // 2. Filtrer par Statut
        const correspondStatut = (
            filtreStatutActif === 'tous' || 
            statutLigne === filtreStatutActif
        );

        // 3. Filtrer par Organisation
        const correspondOrganisation = (
            filtreOrganisationActif === 'tous' ||
            organisation === filtreOrganisationActif.toLowerCase()
        );
        
        // Afficher la ligne si toutes les conditions sont remplies
        if (correspondRecherche && correspondStatut && correspondOrganisation) {
            ligne.style.display = '';
        } else {
            ligne.style.display = 'none';
        }
    });
}

// ========== FONCTIONS D'API ==========

function executerChangementStatut(idUtilisateur, nouveauStatut, raison = '') {
    let donnees = {
        id_utilisateur: idUtilisateur,
        statut: nouveauStatut
    };
    
    if (raison !== '') {
        donnees.raison = raison;
    }
    
    fetch('/api/changer_statut', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(donnees)
    })
    .then(response => {
        if (!response.ok) {
            throw new Error('Erreur réseau');
        }
        return response.json();
    })
    .then(data => {
        console.log('Réponse API:', data);
        
        if (data.success) {
            // Mettre à jour l'affichage sans recharger la page
            const ligne = document.querySelector(`.ligne-utilisateur[data-user-id="${idUtilisateur}"]`);
            if (ligne) {
                // Mettre à jour l'attribut data-statut
                ligne.setAttribute('data-statut', nouveauStatut);
                
                // Mettre à jour le badge de statut
                mettreAJourBadgeStatut(ligne, nouveauStatut);
                
                // Mettre à jour les styles de la ligne
                if (nouveauStatut === 'bloque') {
                    ligne.style.background = 'linear-gradient(135deg, #fdeaea, #f8d7da)';
                    ligne.style.borderLeft = '4px solid #dc3545';
                } else if (nouveauStatut === 'admin') {
                    ligne.style.background = 'linear-gradient(135deg, #fff9e6, #fff3cd)';
                    ligne.style.borderLeft = '4px solid #ffc107';
                } else {
                    ligne.style.background = 'white';
                    ligne.style.borderLeft = '4px solid transparent';
                }
            }
            
            // Message avec info sur l'email
            let message = `✅ ${data.message}`;
            if (data.email_envoye) {
                message += " 📧 Email envoyé";
            }
            
            afficherNotification(message);
            
            // Réappliquer les filtres
            setTimeout(() => appliquerFiltres(), 500);
        } else {
            afficherNotification(`❌ ${data.message}`, 'error');
        }
    })
    .catch(error => {
        console.error('Erreur:', error);
        afficherNotification('Erreur de connexion au serveur', 'error');
    });
}

// ========== ACTIVATION MANUELLE DE COMPTE ==========

function activerCompteManuel(userId, nomUtilisateur) {
    // Créer la popup personnalisée
    const popupHTML = `
        <div id="customConfirmPopup" class="popup-overlay active" style="z-index: 3000;">
            <div class="popup" style="max-width: 450px;">
                <div class="popup-header confirmation" style="background: linear-gradient(135deg, #28a745, #20c997);">
                    <div class="popup-titre">
                        <i class="fas fa-check-circle"></i>
                        <span>Activation de compte</span>
                    </div>
                    <button class="popup-close" onclick="fermerCustomConfirm()">&times;</button>
                </div>
                <div class="popup-body">
                    <div class="popup-message">
                        <p><strong>Activer manuellement le compte de ${nomUtilisateur} ?</strong></p>
                        <p>L'utilisateur pourra se connecter immédiatement sans vérification email.</p>
                        <p>Un email de bienvenue sera envoyé automatiquement.</p>
                    </div>
                    <div class="popup-boutons" style="justify-content: center; gap: 15px;">
                        <button class="popup-bouton annuler" onclick="fermerCustomConfirm()">
                            <i class="fas fa-times"></i> Non
                        </button>
                        <button class="popup-bouton confirmer" onclick="confirmerActivation('${userId}', '${nomUtilisateur.replace(/'/g, "\\'")}')" style="background: #28a745;">
                            <i class="fas fa-check"></i> Oui
                        </button>
                    </div>
                </div>
            </div>
        </div>
    `;
    
    // Ajouter la popup au body
    document.body.insertAdjacentHTML('beforeend', popupHTML);
    document.body.style.overflow = 'hidden';
}

function fermerCustomConfirm() {
    const popup = document.getElementById('customConfirmPopup');
    if (popup) {
        popup.remove();
        document.body.style.overflow = '';
    }
}

function confirmerActivation(userId, nomUtilisateur) {
    // Fermer la popup de confirmation
    fermerCustomConfirm();
    
    // Trouver le bouton qui a été cliqué
    const buttons = document.querySelectorAll('.bouton-activer-manuel');
    let targetButton = null;
    for (let btn of buttons) {
        if (btn.getAttribute('onclick') && btn.getAttribute('onclick').includes(userId)) {
            targetButton = btn;
            break;
        }
    }
    
    if (targetButton) {
        // Sauvegarder le texte original et désactiver le bouton
        const originalText = targetButton.innerHTML;
        targetButton.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Activation...';
        targetButton.disabled = true;
    }
    
    fetch('/api/activer_compte_manuel', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            user_id: userId
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            afficherNotification(`✅ ${data.message}`, 'success');
            if (data.email_envoye) {
                afficherNotification(`📧 Un email de bienvenue a été envoyé à l'utilisateur`, 'info');
            }
            // Recharger la page pour mettre à jour l'affichage
            setTimeout(() => {
                location.reload();
            }, 1500);
        } else {
            afficherNotification(`❌ ${data.message}`, 'error');
            // Réactiver le bouton en cas d'erreur
            if (targetButton) {
                targetButton.innerHTML = originalText;
                targetButton.disabled = false;
            }
        }
    })
    .catch(error => {
        console.error('Erreur:', error);
        afficherNotification('❌ Erreur de connexion au serveur', 'error');
        if (targetButton) {
            targetButton.innerHTML = originalText;
            targetButton.disabled = false;
        }
    });
}

// ========== FONCTIONS UTILITAIRES ==========

function mettreAJourBadgeStatut(ligne, nouveauStatut) {
    const celluleStatut = ligne.querySelector('.cellule-donnee:nth-child(8)');
    let badgeHTML = '';
    
    switch(nouveauStatut) {
        case 'admin':
            badgeHTML = '<span class="badge badge-admin">👑Admin</span>';
            break;
        case 'bloque':
            badgeHTML = '<span class="badge badge-bloque">🚫Bloqué</span>';
            break;
        case 'pending':
            badgeHTML = '<span class="badge badge-pending">⏳En attente</span>';
            break;
        default:
            badgeHTML = '<span class="badge badge-succes">👤User</span>';
    }
    
    celluleStatut.innerHTML = badgeHTML;
}