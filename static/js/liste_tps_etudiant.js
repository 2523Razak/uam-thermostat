/* ===== FICHIER JAVASCRIPT POUR LA LISTE DES TPS ÉTUDIANT ===== */

// ============================================================================
// CONFIGURATION
// ============================================================================

const CONFIG = {
    INTERVALLE_RAFRAICHISSEMENT: 30000, // 30 secondes
    URL_API_STATUTS: '/api/tps/statuts',
    URL_API_NOTES: '/api/notes_etudiant',
    EFFETS: {
        DUREE_SURBRILLANCE: 2000 // 2 secondes
    }
};

// ============================================================================
// VARIABLES GLOBALES
// ============================================================================

let intervalleMiseAJour = null;
let dernieresDonnees = {};

// ============================================================================
// INITIALISATION
// ============================================================================

document.addEventListener('DOMContentLoaded', function() {
    console.log('✅ Page liste_tps_etudiant.js chargée');
    
    // Initialiser les filtres
    initialiserFiltres();
    
    // Mettre à jour le compteur
    mettreAJourCompteur();
    
    // Marquer les TPs comme vus
    marquerTPsCommeVus();
    
    // Vérifier les nouveaux TPs
    checkNewTPs();
    
    // Ajouter classe 'soumis' aux TPs expirés avec date de soumission
    document.querySelectorAll('.carte-tp.expire[data-date-soumission]').forEach(carte => {
        if (carte.getAttribute('data-date-soumission')) {
            carte.classList.add('soumis');
        }
    });
    
    // DÉMARRER LA MISE À JOUR EN TEMPS RÉEL
    demarrerMiseAJourTempsReel();
    
    // Charger les notes initiales
    chargerNotesTPs();
});

// ============================================================================
// MISE À JOUR EN TEMPS RÉEL
// ============================================================================

function demarrerMiseAJourTempsReel() {
    console.log('🔄 Démarrage de la mise à jour en temps réel...');
    
    // Mise à jour immédiate
    miseAJourTempsReel();
    
    // Puis toutes les X secondes
    if (intervalleMiseAJour) {
        clearInterval(intervalleMiseAJour);
    }
    
    intervalleMiseAJour = setInterval(miseAJourTempsReel, CONFIG.INTERVALLE_RAFRAICHISSEMENT);
    
    // Nettoyer l'intervalle quand on quitte la page
    window.addEventListener('beforeunload', function() {
        if (intervalleMiseAJour) {
            clearInterval(intervalleMiseAJour);
        }
    });
}

function miseAJourTempsReel() {
    console.log('🔄 Mise à jour des données...', new Date().toLocaleTimeString());
    
    // Récupérer les statuts mis à jour
    fetch(CONFIG.URL_API_STATUTS, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            tps_ids: getListeTPIds()
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            mettreAJourStatutsTP(data.tps);
        }
    })
    .catch(error => {
        console.log('⚠️ Erreur mise à jour statuts:', error);
    });
    
    // Mettre à jour les notes
    fetch(CONFIG.URL_API_NOTES)
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                mettreAJourNotes(data.notes);
            }
        })
        .catch(error => {
            console.log('⚠️ Erreur mise à jour notes:', error);
        });
}

function getListeTPIds() {
    const cartes = document.querySelectorAll('.carte-tp');
    return Array.from(cartes).map(carte => carte.getAttribute('data-tp-id'));
}

function mettreAJourStatutsTP(tpsData) {
    tpsData.forEach(tpData => {
        const carte = document.querySelector(`.carte-tp[data-tp-id="${tpData.id}"]`);
        if (!carte) return;
        
        const ancienStatut = carte.getAttribute('data-statut');
        const ancienDateSoumission = carte.getAttribute('data-date-soumission');
        
        // Mettre à jour les attributs
        carte.setAttribute('data-statut', tpData.statut);
        if (tpData.date_soumission) {
            carte.setAttribute('data-date-soumission', tpData.date_soumission);
        }
        
        // Mettre à jour les classes CSS
        mettreAJourClassesCarte(carte, ancienStatut, tpData.statut);
        
        // Mettre à jour le badge de statut
        mettreAJourBadgeStatut(carte, tpData);
        
        // Mettre à jour les actions (boutons)
        mettreAJourActions(carte, tpData);
        
        // Effet visuel si changement
        if (ancienStatut !== tpData.statut) {
            effetChangement(carte);
        }
    });
}

function mettreAJourClassesCarte(carte, ancienStatut, nouveauStatut) {
    // Retirer les anciennes classes de statut
    carte.classList.remove(ancienStatut);
    
    // Ajouter la nouvelle classe
    carte.classList.add(nouveauStatut);
    
    // Gérer la classe 'soumis' pour les expirés soumis
    const dateSoumission = carte.getAttribute('data-date-soumission');
    if (nouveauStatut === 'expire' && dateSoumission) {
        carte.classList.add('soumis');
    } else if (nouveauStatut !== 'expire') {
        carte.classList.remove('soumis');
    }
}

function mettreAJourBadgeStatut(carte, tpData) {
    const badge = carte.querySelector('.badge-statut');
    if (!badge) return;
    
    // Déterminer la classe du badge
    let badgeClass = '';
    let badgeIcon = '';
    let badgeText = '';
    
    if (tpData.statut === 'expire' && tpData.date_soumission) {
        badgeClass = 'badge-soumis-expire';
        badgeIcon = 'fa-check-circle';
        badgeText = 'Terminé (Note disponible)';
    } else if (tpData.statut === 'expire') {
        badgeClass = 'badge-expire';
        badgeIcon = 'fa-ban';
        badgeText = 'Expiré';
    } else if (tpData.statut === 'disponible') {
        badgeClass = 'badge-disponible';
        badgeIcon = 'fa-play-circle';
        badgeText = 'Disponible';
    } else if (tpData.statut === 'en_cours') {
        badgeClass = 'badge-en_cours';
        badgeIcon = 'fa-clock';
        badgeText = 'En cours';
    } else if (tpData.statut === 'soumis') {
        badgeClass = 'badge-soumis';
        badgeIcon = 'fa-check-circle';
        badgeText = 'Soumis';
    }
    
    // Mettre à jour le badge
    badge.className = `badge-statut ${badgeClass}`;
    badge.innerHTML = `<i class="fas ${badgeIcon}"></i> ${badgeText}`;
}

function mettreAJourActions(carte, tpData) {
    const actionsDiv = carte.querySelector('.actions-etudiant');
    if (!actionsDiv) return;
    
    // Sauvegarder le bouton "Détails" car il est toujours présent
    const boutonDetails = actionsDiv.querySelector('.bouton-action.details');
    const detailsHtml = boutonDetails ? boutonDetails.outerHTML : '';
    
    // Reconstruire les actions
    let actionsHtml = '';
    
    if (tpData.statut === 'disponible') {
        actionsHtml += `<a href="/tp/${tpData.id}/commencer" class="bouton-action commencer"><i class="fas fa-play"></i> Commencer</a>`;
    }
    
    if (tpData.statut === 'en_cours') {
        actionsHtml += `<a href="/tp/${tpData.id}/continuer" class="bouton-action continuer"><i class="fas fa-forward"></i> Continuer</a>`;
    }
    
    if (tpData.statut === 'soumis') {
        actionsHtml += `<a href="/tp/${tpData.id}/correction" class="bouton-action correction"><i class="fas fa-eye"></i> Voir ma note</a>`;
    }
    
    if (tpData.statut === 'expire') {
        if (tpData.date_soumission) {
            actionsHtml += `<a href="/tp/${tpData.id}/correction" class="bouton-action correction"><i class="fas fa-star"></i> Voir ma note</a>`;
        } else {
            actionsHtml += `<button class="bouton-action expire" disabled><i class="fas fa-ban"></i> Expiré</button>`;
        }
    }
    
    // Ajouter le bouton Détails
    actionsHtml += detailsHtml;
    
    // Remplacer le contenu
    actionsDiv.innerHTML = actionsHtml;
}

function mettreAJourNotes(notes) {
    notes.forEach(noteData => {
        const carte = document.querySelector(`.carte-tp[data-tp-id="${noteData.tp_id}"]`);
        if (!carte) return;
        
        // Stocker les données dans des attributs
        carte.setAttribute('data-note-obtenue', noteData.note_obtenue);
        carte.setAttribute('data-points-totaux', noteData.points_totaux);
        carte.setAttribute('data-pourcentage', noteData.pourcentage);
        
        // Mettre à jour l'affichage
        afficherNoteDansCarte(carte, noteData);
    });
}
function afficherNoteDansCarte(carte, noteData) {
    // Supprimer l'ancien badge de note s'il existe
    const ancienBadge = carte.querySelector('.badge-note');
    if (ancienBadge) {
        ancienBadge.remove();
    }
    
    // Ajouter le nouveau badge de note
    const enTete = carte.querySelector('.en-tete-carte');
    if (enTete && noteData && noteData.note_obtenue !== undefined) {
        const badgeNote = document.createElement('span');
        badgeNote.className = 'badge-statut badge-soumis-expire badge-note';
        const noteObtenue = noteData.note_obtenue.toFixed(1);
        const pointsTotaux = noteData.points_totaux;
        const pourcentage = noteData.pourcentage.toFixed(1);
        
        // Remplacer le point par une virgule pour le format français
        const noteFormatee = noteObtenue.replace('.', ',');
        const pourcentageFormate = pourcentage.replace('.', ',');
        
        badgeNote.innerHTML = `<i class="fas fa-star"></i> ${noteFormatee}/${pourcentageFormate}%`;
        
        enTete.appendChild(badgeNote);
        
        // Effet visuel pour la nouvelle note
        badgeNote.style.animation = 'pulseNote 1s';
    }
}

function effetChangement(carte) {
    // Ajouter une classe de surbrillance
    carte.classList.add('carte-modifiee');
    
    // Jouer une petite animation
    carte.style.transition = 'all 0.3s ease';
    carte.style.transform = 'scale(1.02)';
    carte.style.boxShadow = '0 12px 30px rgba(0,0,0,0.2)';
    
    setTimeout(() => {
        carte.style.transform = 'scale(1)';
        carte.style.boxShadow = '';
    }, 300);
    
    setTimeout(() => {
        carte.classList.remove('carte-modifiee');
    }, CONFIG.EFFETS.DUREE_SURBRILLANCE);
}

// ============================================================================
// GESTION DES FILTRES
// ============================================================================

function initialiserFiltres() {
    const filtreStatut = localStorage.getItem('tpFiltreStatut') || 'tous';
    const filtreModule = localStorage.getItem('tpFiltreModule') || 'tous';
    
    const statutSelect = document.getElementById('filtre-statut');
    const moduleSelect = document.getElementById('filtre-module');
    
    if (statutSelect) statutSelect.value = filtreStatut;
    if (moduleSelect) moduleSelect.value = filtreModule;
    
    appliquerFiltres();
    
    if (statutSelect) statutSelect.addEventListener('change', appliquerFiltres);
    if (moduleSelect) moduleSelect.addEventListener('change', appliquerFiltres);
}

function appliquerFiltres() {
    const filtreStatut = document.getElementById('filtre-statut')?.value || 'tous';
    const filtreModule = document.getElementById('filtre-module')?.value || 'tous';
    
    localStorage.setItem('tpFiltreStatut', filtreStatut);
    localStorage.setItem('tpFiltreModule', filtreModule);
    
    const cartesTP = document.querySelectorAll('.carte-tp');
    let cartesVisibles = 0;
    
    cartesTP.forEach(carte => {
        const statut = carte.getAttribute('data-statut');
        const module = carte.getAttribute('data-module');
        const isNew = carte.getAttribute('data-nouveau') === 'true';
        const dateSoumission = carte.getAttribute('data-date-soumission');
        
        let afficher = true;
        
        if (filtreStatut !== 'tous') {
            if (filtreStatut === 'nouveau') {
                afficher = isNew;
            } else if (filtreStatut === 'soumis') {
                afficher = (statut === 'soumis') || (statut === 'expire' && dateSoumission);
            } else if (statut !== filtreStatut) {
                afficher = false;
            }
        }
        
        if (filtreModule !== 'tous' && module !== filtreModule) {
            afficher = false;
        }
        
        if (afficher) {
            carte.style.display = 'flex';
            carte.style.opacity = '1';
            cartesVisibles++;
        } else {
            carte.style.display = 'none';
            carte.style.opacity = '0';
        }
    });
    
    const compteur = document.getElementById('compteur-resultats');
    if (compteur) {
        compteur.textContent = cartesVisibles + ' résultat(s)';
    }
    
    const etatVide = document.querySelector('.etat-vide');
    if (cartesVisibles === 0 && cartesTP.length > 0) {
        if (etatVide) {
            etatVide.style.display = 'flex';
            const titreVide = etatVide.querySelector('.titre-vide');
            const texteVide = etatVide.querySelector('.texte-vide');
            if (titreVide) titreVide.textContent = 'Aucun résultat';
            if (texteVide) texteVide.textContent = 'Aucun TP ne correspond aux filtres sélectionnés.';
        }
    } else if (etatVide) {
        etatVide.style.display = 'none';
    }
}

function reinitialiserFiltres() {
    const statutSelect = document.getElementById('filtre-statut');
    const moduleSelect = document.getElementById('filtre-module');
    
    if (statutSelect) statutSelect.value = 'tous';
    if (moduleSelect) moduleSelect.value = 'tous';
    
    localStorage.removeItem('tpFiltreStatut');
    localStorage.removeItem('tpFiltreModule');
    
    appliquerFiltres();
}

function mettreAJourCompteur() {
    const cartesVisibles = document.querySelectorAll('.carte-tp:not([style*="display: none"])').length;
    const compteur = document.getElementById('compteur-resultats');
    if (compteur) {
        compteur.textContent = cartesVisibles + ' résultat(s)';
    }
}

// ============================================================================
// GESTION DES NOUVEAUX TPS
// ============================================================================

function marquerTPsCommeVus() {
    const cartesTP = document.querySelectorAll('.carte-tp');
    const tpsVus = JSON.parse(localStorage.getItem('tpsVus') || '[]');
    let nouveauxTPs = false;
    
    cartesTP.forEach(carte => {
        const tpId = carte.getAttribute('data-tp-id');
        if (tpId && !tpsVus.includes(tpId)) {
            tpsVus.push(tpId);
            nouveauxTPs = true;
            
            const statut = carte.getAttribute('data-statut');
            const dateSoumission = carte.getAttribute('data-date-soumission');
            
            if (statut === 'expire' && dateSoumission) {
                carte.classList.add('soumis');
            }
        }
    });
    
    if (nouveauxTPs) {
        localStorage.setItem('tpsVus', JSON.stringify(tpsVus));
    }
}

function checkNewTPs() {
    const nouveauxTPs = document.querySelectorAll('.carte-tp.nouveau');
    if (nouveauxTPs.length > 0) {
        const notification = document.createElement('div');
        notification.className = 'notification-nouveaux';
        notification.innerHTML = `
            <span>${nouveauxTPs.length} nouveau(x) TP(s) disponible(s)</span>
            <button onclick="this.parentElement.remove()">
                <i class="fas fa-times"></i>
            </button>
        `;
        notification.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            background: linear-gradient(135deg, #FF5722 0%, #E64A19 100%);
            color: white;
            padding: 12px 20px;
            border-radius: 8px;
            box-shadow: 0 4px 15px rgba(0,0,0,0.2);
            display: flex;
            align-items: center;
            gap: 15px;
            z-index: 10000;
            animation: slideIn 0.3s ease-out;
        `;
        
        notification.querySelector('button').style.cssText = `
            background: none;
            border: none;
            color: white;
            cursor: pointer;
            font-size: 1rem;
        `;
        
        const style = document.createElement('style');
        style.textContent = `
            @keyframes slideIn {
                from {
                    opacity: 0;
                    transform: translateY(-20px);
                }
                to {
                    opacity: 1;
                    transform: translateY(0);
                }
            }
            @keyframes slideOut {
                from {
                    opacity: 1;
                    transform: translateY(0);
                }
                to {
                    opacity: 0;
                    transform: translateY(-20px);
                }
            }
        `;
        document.head.appendChild(style);
        
        document.body.appendChild(notification);
        
        setTimeout(() => {
            if (notification.parentElement) {
                notification.style.animation = 'slideOut 0.3s ease-out';
                setTimeout(() => notification.remove(), 300);
            }
        }, 5000);
    }
}

// ============================================================================
// GESTION DES NOTES
// ============================================================================

function chargerNotesTPs() {
    fetch(CONFIG.URL_API_NOTES)
        .then(response => response.json())
        .then(data => {
            if (data.success && data.notes) {
                mettreAJourNotes(data.notes);
            }
        })
        .catch(error => {
            console.log('⚠️ API notes non disponible:', error);
        });
}

// ============================================================================
// EXPORT POUR LES TESTS
// ============================================================================

if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        demarrerMiseAJourTempsReel,
        miseAJourTempsReel,
        mettreAJourStatutsTP,
        appliquerFiltres,
        reinitialiserFiltres
    };
}