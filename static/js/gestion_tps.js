// ===== VARIABLES GLOBALES =====
let currentTpId = null;
let currentEtudiants = [];
let tpToDelete = {
    id: null,
    titre: null
};

// ===== FONCTIONS UTILITAIRES =====
function showToast(message, type = 'info') {
    // Supprimer les anciens toasts
    document.querySelectorAll('.toast').forEach(toast => {
        toast.style.animation = 'slideOut 0.3s ease-out';
        setTimeout(() => toast.remove(), 300);
    });
    
    // Créer le toast
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.innerHTML = `
        <i class="fas fa-${type === 'success' ? 'check-circle' : type === 'error' ? 'exclamation-circle' : 'info-circle'}"></i>
        <span>${message}</span>
    `;
    
    // Ajouter les styles
    toast.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        background: ${type === 'success' ? '#28a745' : type === 'error' ? '#dc3545' : '#17a2b8'};
        color: white;
        padding: 12px 20px;
        border-radius: 8px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        z-index: 9999;
        display: flex;
        align-items: center;
        gap: 10px;
        animation: slideIn 0.3s ease-out;
        max-width: 350px;
    `;
    
    document.body.appendChild(toast);
    
    // Ajouter l'animation CSS si elle n'existe pas
    if (!document.querySelector('#toast-animations')) {
        const style = document.createElement('style');
        style.id = 'toast-animations';
        style.textContent = `
            @keyframes slideIn {
                from { transform: translateX(100%); opacity: 0; }
                to { transform: translateX(0); opacity: 1; }
            }
            @keyframes slideOut {
                from { transform: translateX(0); opacity: 1; }
                to { transform: translateX(100%); opacity: 0; }
            }
        `;
        document.head.appendChild(style);
    }
    
    // Supprimer après 4 secondes
    setTimeout(() => {
        toast.style.animation = 'slideOut 0.3s ease-out';
        setTimeout(() => toast.remove(), 300);
    }, 4000);
}

// ===== INITIALISATION =====
document.addEventListener('DOMContentLoaded', function() {
    // Mettre à jour la date actuelle
    const maintenant = new Date();
    const options = { 
        weekday: 'long', 
        year: 'numeric', 
        month: 'long', 
        day: 'numeric' 
    };
    const dateFormatee = maintenant.toLocaleDateString('fr-FR', options);
    
    const elementDate = document.getElementById('date-actuelle');
    if (elementDate) {
        elementDate.textContent = dateFormatee;
    }
    
    // Initialiser les événements
    initEventListeners();
    
    console.log('Gestion TPs initialisé');
});

function initEventListeners() {
    // Entrée pour ajouter étudiant
    const etudiantInput = document.getElementById('new-etudiant-input');
    if (etudiantInput) {
        etudiantInput.addEventListener('keypress', function(e) {
            if (e.key === 'Enter') {
                e.preventDefault();
                addEtudiant();
            }
        });
    }
    
    // Fermer les modals en cliquant à l'extérieur
    document.querySelectorAll('.modal-overlay').forEach(overlay => {
        overlay.addEventListener('click', function(e) {
            if (e.target === this) {
                const modalId = this.id;
                switch(modalId) {
                    case 'modal-etudiants':
                        closeEtudiantsModal();
                        break;
                    case 'modal-date-limite':
                        closeDateLimiteModal();
                        break;
                    case 'modal-confirmation':
                        closeConfirmationModal();
                        break;
                }
            }
        });
    });
    
    // Gestion de la touche Échap
    document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape') {
            const modals = ['modal-confirmation', 'modal-etudiants', 'modal-date-limite'];
            for (const modalId of modals) {
                const modal = document.getElementById(modalId);
                if (modal && modal.style.display === 'flex') {
                    switch(modalId) {
                        case 'modal-confirmation':
                            closeConfirmationModal();
                            break;
                        case 'modal-etudiants':
                            closeEtudiantsModal();
                            break;
                        case 'modal-date-limite':
                            closeDateLimiteModal();
                            break;
                    }
                    break;
                }
            }
        }
    });
}

// ===== GESTION DES ÉTUDIANTS =====
function openEtudiantsModal(tpId, tpTitre) {
    console.log(`Ouverture modal étudiants pour TP ${tpId}: ${tpTitre}`);
    currentTpId = tpId;
    document.getElementById('modal-etudiants-title').textContent = 'Étudiants - ' + tpTitre;
    document.getElementById('new-etudiant-input').value = '';
    
    // Afficher un indicateur de chargement
    document.getElementById('etudiants-list').innerHTML = `
        <div style="text-align: center; padding: 40px;">
            <i class="fas fa-spinner fa-spin" style="font-size: 2rem; color: #1a237e;"></i>
            <p style="margin-top: 10px; color: #6c757d;">Chargement...</p>
        </div>
    `;
    
    document.getElementById('modal-etudiants').style.display = 'flex';
    loadEtudiants(tpId);
}

function closeEtudiantsModal() {
    document.getElementById('modal-etudiants').style.display = 'none';
    document.getElementById('new-etudiant-input').value = '';
    currentEtudiants = [];
}

function loadEtudiants(tpId) {
    fetch('/api/tp/' + tpId + '/etudiants')
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            if (data.success) {
                currentEtudiants = data.etudiants || [];
                updateEtudiantsList();
            } else {
                showToast('Erreur: ' + data.message, 'error');
                closeEtudiantsModal();
            }
        })
        .catch(error => {
            console.error('Erreur:', error);
            showToast('Erreur de connexion: ' + error.message, 'error');
            closeEtudiantsModal();
        });
}

function updateEtudiantsList() {
    const etudiantsList = document.getElementById('etudiants-list');
    
    if (currentEtudiants.length === 0) {
        etudiantsList.innerHTML = `
            <div style="text-align: center; padding: 40px; color: #6c757d;">
                <i class="fas fa-user-graduate" style="font-size: 2rem; margin-bottom: 10px;"></i>
                <p>Aucun étudiant inscrit</p>
            </div>
        `;
        return;
    }
    
    let html = '';
    currentEtudiants.forEach((etudiant, index) => {
        html += `
            <div class="etudiant-item" style="display: flex; justify-content: space-between; align-items: center; padding: 10px; margin: 5px 0; background: #f8f9fa; border-radius: 4px;">
                <span class="etudiant-identifiant" style="display: flex; align-items: center;">
                    <i class="fas fa-user-graduate" style="color: #1a237e; margin-right: 8px;"></i>
                    ${etudiant}
                </span>
                <button class="btn-remove-etudiant" onclick="removeEtudiant(${index})" title="Retirer cet étudiant" style="background: none; border: none; color: #dc3545; cursor: pointer; padding: 5px;">
                    <i class="fas fa-times"></i>
                </button>
            </div>
        `;
    });
    
    etudiantsList.innerHTML = html;
}

function addEtudiant() {
    const input = document.getElementById('new-etudiant-input');
    const identifiant = input.value.trim();
    
    if (!identifiant) {
        showToast('Veuillez saisir un identifiant', 'warning');
        return;
    }
    
    // Validation simple
    if (identifiant.length < 3) {
        showToast('Identifiant trop court', 'warning');
        return;
    }
    
    if (currentEtudiants.includes(identifiant)) {
        showToast('Cet étudiant est déjà dans la liste', 'warning');
        return;
    }
    
    currentEtudiants.push(identifiant);
    updateEtudiantsList();
    input.value = '';
    input.focus();
    showToast('Étudiant ajouté à la liste', 'success');
}

function removeEtudiant(index) {
    currentEtudiants.splice(index, 1);
    updateEtudiantsList();
    showToast('Étudiant retiré de la liste', 'info');
}

function saveEtudiants() {
    if (!currentTpId) {
        showToast('Aucun TP sélectionné', 'error');
        return;
    }
    
    const saveBtn = document.querySelector('#modal-etudiants .bouton-principal');
    const originalText = saveBtn.innerHTML;
    saveBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Enregistrement...';
    saveBtn.disabled = true;
    
    fetch('/api/tp/' + currentTpId + '/update_etudiants', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ etudiants: currentEtudiants })
    })
    .then(response => {
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }
        return response.json();
    })
    .then(data => {
        if (data.success) {
            showToast(data.message, 'success');
            
            // Mettre à jour le compteur dans la carte
            setTimeout(() => {
                const carte = document.querySelector('[data-tp-id="' + currentTpId + '"]');
                if (carte) {
                    const countElement = carte.querySelector('.etudiants-count');
                    if (countElement) {
                        countElement.textContent = data.count + ' étudiant(s)';
                    }
                }
            }, 500);
            
            // Fermer le modal
            setTimeout(() => closeEtudiantsModal(), 1500);
        } else {
            showToast('Erreur: ' + data.message, 'error');
        }
    })
    .catch(error => {
        console.error('Erreur:', error);
        showToast('Erreur de connexion: ' + error.message, 'error');
    })
    .finally(() => {
        saveBtn.innerHTML = originalText;
        saveBtn.disabled = false;
    });
}

// ===== GESTION DATE LIMITE =====
function openDateLimiteModal(tpId, tpTitre, currentDate) {
    currentTpId = tpId;
    document.getElementById('modal-date-limite-title').textContent = 'Date limite - ' + tpTitre;
    document.getElementById('date-limite-input').value = currentDate;
    document.getElementById('modal-date-limite').style.display = 'flex';
}

function closeDateLimiteModal() {
    document.getElementById('modal-date-limite').style.display = 'none';
}

function saveDateLimite() {
    if (!currentTpId) return;
    
    const saveBtn = document.querySelector('#modal-date-limite .bouton-principal');
    const originalText = saveBtn.innerHTML;
    saveBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Enregistrement...';
    saveBtn.disabled = true;
    
    const newDate = document.getElementById('date-limite-input').value;
    
    fetch('/api/tp/' + currentTpId + '/update_date_limite', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ date_limite: newDate })
    })
    .then(response => {
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }
        return response.json();
    })
    .then(data => {
        if (data.success) {
            showToast(data.message, 'success');
            
            // Mettre à jour l'affichage
            const carte = document.querySelector('[data-tp-id="' + currentTpId + '"]');
            if (carte) {
                const dateElement = carte.querySelector('.date-limite-text');
                if (dateElement) {
                    dateElement.textContent = newDate ? 
                        'Limite: ' + data.date_limite_formatted : 
                        'Limite: Non définie';
                }
            }
            
            closeDateLimiteModal();
        } else {
            showToast('Erreur: ' + data.message, 'error');
        }
    })
    .catch(error => {
        console.error('Erreur:', error);
        showToast('Erreur de connexion: ' + error.message, 'error');
    })
    .finally(() => {
        saveBtn.innerHTML = originalText;
        saveBtn.disabled = false;
    });
}

// ===== GESTION SUPPRESSION TP =====
function confirmerSuppression(tpId, tpTitre) {
    console.log('Confirmation suppression TP:', tpId, tpTitre);
    
    tpToDelete.id = tpId;
    tpToDelete.titre = tpTitre;
    
    document.getElementById('modal-confirmation-title').textContent = 'Supprimer le TP : ' + tpTitre;
    document.getElementById('confirmation-message').textContent = `Êtes-vous sûr de vouloir supprimer le TP "${tpTitre}" ?`;
    document.getElementById('confirmation-details').textContent = `ID: ${tpId} • Action irréversible`;
    
    document.getElementById('modal-confirmation').style.display = 'flex';
}

function closeConfirmationModal() {
    document.getElementById('modal-confirmation').style.display = 'none';
    tpToDelete.id = null;
    tpToDelete.titre = null;
}

function executerSuppression() {
    if (!tpToDelete.id) {
        showToast('Aucun TP sélectionné', 'error');
        return;
    }
    
    const deleteBtn = document.getElementById('confirm-delete-btn');
    const originalText = deleteBtn.innerHTML;
    deleteBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Suppression...';
    deleteBtn.disabled = true;
    
    console.log('Début suppression TP:', tpToDelete.id);
    
    // D'abord essayer DELETE
    fetch('/api/tp/' + tpToDelete.id + '/supprimer', {
        method: 'DELETE',
        headers: {'Content-Type': 'application/json'},
        credentials: 'same-origin'
    })
    .then(response => {
        console.log('Réponse DELETE:', response.status, response.statusText);
        
        // Si DELETE échoue (405 Method Not Allowed), essayer POST
        if (response.status === 405 || response.status === 404) {
            console.log('Méthode DELETE non supportée, essai avec POST...');
            return fetch('/api/tp/' + tpToDelete.id + '/supprimer_post', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                credentials: 'same-origin'
            });
        }
        return response;
    })
    .then(response => {
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        return response.json();
    })
    .then(data => {
        console.log('Données reçues:', data);
        
        if (data.success) {
            showToast(data.message, 'success');
            
            // Fermer le modal
            closeConfirmationModal();
            
            // Supprimer la carte visuellement
            const carte = document.querySelector(`[data-tp-id="${tpToDelete.id}"]`);
            if (carte) {
                carte.style.opacity = '0.5';
                carte.style.transform = 'scale(0.95)';
                carte.style.transition = 'all 0.3s ease';
                
                setTimeout(() => {
                    carte.style.display = 'none';
                    
                    // Mettre à jour le compteur
                    const statElement = document.querySelector('.cartes-stats .nombre-stat:first-child');
                    if (statElement) {
                        const currentCount = parseInt(statElement.textContent) || 0;
                        statElement.textContent = Math.max(0, currentCount - 1);
                    }
                    
                    // Vérifier si plus de TP
                    const tpsRestants = document.querySelectorAll('.carte-tp:not([style*="display: none"])').length;
                    if (tpsRestants === 0) {
                        setTimeout(() => location.reload(), 1000);
                    }
                }, 300);
            } else {
                // Recharger la page si la carte n'est pas trouvée
                setTimeout(() => location.reload(), 1000);
            }
        } else {
            showToast('Erreur: ' + (data.message || 'Échec de la suppression'), 'error');
            deleteBtn.innerHTML = originalText;
            deleteBtn.disabled = false;
        }
    })
    .catch(error => {
        console.error('Erreur complète:', error);
        showToast('Erreur de connexion: ' + error.message, 'error');
        deleteBtn.innerHTML = originalText;
        deleteBtn.disabled = false;
    });
}
// ===== GESTION DES QUESTIONS =====
function sauvegarderToutesQuestions(tpId) {
    if (!tpId) {
        showToast('Aucun TP sélectionné', 'error');
        return;
    }
    
    // Récupérer toutes les questions depuis le DOM
    const questions = collecterQuestions();
    
    if (questions.length === 0) {
        showToast('Aucune question à sauvegarder', 'warning');
        return;
    }
    
    const saveBtn = document.getElementById('btn-save-all-questions');
    if (saveBtn) {
        const originalText = saveBtn.innerHTML;
        saveBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Sauvegarde...';
        saveBtn.disabled = true;
    }
    
    // Envoyer les questions au serveur
    fetch('/api/tp/' + tpId + '/questions/sauvegarder', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ questions: questions })
    })
    .then(response => {
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        return response.json();
    })
    .then(data => {
        if (data.success) {
            showToast(data.message, 'success');
            
            // Mettre à jour le compteur dans la carte
            const carte = document.querySelector(`[data-tp-id="${tpId}"]`);
            if (carte) {
                const countElement = carte.querySelector('.info-item:nth-child(4) span');
                if (countElement) {
                    countElement.textContent = data.count + ' question(s)';
                }
            }
            
            // Recharger les questions depuis le serveur
            chargerQuestions(tpId);
        } else {
            showToast('Erreur: ' + data.message, 'error');
        }
    })
    .catch(error => {
        console.error('Erreur:', error);
        showToast('Erreur de connexion: ' + error.message, 'error');
    })
    .finally(() => {
        if (saveBtn) {
            saveBtn.innerHTML = originalText;
            saveBtn.disabled = false;
        }
    });
}

function collecterQuestions() {
    // Cette fonction collecte toutes les questions depuis le formulaire
    const questions = [];
    
    // Collecter depuis les éléments avec classe "question-item"
    document.querySelectorAll('.question-item').forEach((item, index) => {
        const enonce = item.querySelector('.question-enonce')?.value || '';
        const type = item.querySelector('.question-type')?.value || 'qcm';
        const points = parseFloat(item.querySelector('.question-points')?.value) || 1.0;
        const reponse = item.querySelector('.question-reponse')?.value || '';
        
        if (enonce.trim()) {
            questions.push({
                enonce: enonce.trim(),
                type_question: type,
                points: points,
                ordre: index,
                reponse_correcte: reponse
            });
        }
    });
    
    return questions;
}

function chargerQuestions(tpId) {
    // Charger les questions depuis le serveur
    fetch('/api/tp/' + tpId + '/questions')
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                afficherQuestions(data.questions);
            }
        })
        .catch(error => {
            console.error('Erreur:', error);
            showToast('Erreur de chargement: ' + error.message, 'error');
        });
}

function afficherQuestions(questions) {
    // Afficher les questions dans le formulaire
    const container = document.getElementById('questions-container');
    if (!container) return;
    
    container.innerHTML = '';
    
    questions.forEach((q, index) => {
        const questionHtml = `
            <div class="question-item" style="margin-bottom: 20px; padding: 15px; border: 1px solid #ddd; border-radius: 5px;">
                <div style="display: flex; justify-content: space-between; margin-bottom: 10px;">
                    <h4 style="margin: 0;">Question ${index + 1}</h4>
                    <button type="button" class="btn-remove-question" onclick="supprimerQuestion(${index})" style="background: #dc3545; color: white; border: none; padding: 5px 10px; border-radius: 3px; cursor: pointer;">
                        <i class="fas fa-trash"></i>
                    </button>
                </div>
                <div style="margin-bottom: 10px;">
                    <label>Énoncé:</label>
                    <textarea class="question-enonce form-control" rows="3" style="width: 100%;">${q.enonce || ''}</textarea>
                </div>
                <div style="display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 10px; margin-bottom: 10px;">
                    <div>
                        <label>Type:</label>
                        <select class="question-type form-control" style="width: 100%;">
                            <option value="qcm" ${q.type_question === 'qcm' ? 'selected' : ''}>QCM</option>
                            <option value="ouverte" ${q.type_question === 'ouverte' ? 'selected' : ''}>Question ouverte</option>
                            <option value="numerique" ${q.type_question === 'numerique' ? 'selected' : ''}>Réponse numérique</option>
                        </select>
                    </div>
                    <div>
                        <label>Points:</label>
                        <input type="number" class="question-points form-control" value="${q.points || 1.0}" step="0.5" min="0" style="width: 100%;">
                    </div>
                    <div>
                        <label>Réponse correcte:</label>
                        <input type="text" class="question-reponse form-control" value="${q.reponse_correcte || ''}" style="width: 100%;">
                    </div>
                </div>
            </div>
        `;
        container.innerHTML += questionHtml;
    });
}

// ===== FONCTIONS POUR GESTION_QUESTIONS.HTML =====
function ajouterQuestion() {
    const container = document.getElementById('questions-container');
    const index = container.children.length;
    
    const questionHtml = `
        <div class="question-item" style="margin-bottom: 20px; padding: 15px; border: 1px solid #ddd; border-radius: 5px;">
            <div style="display: flex; justify-content: space-between; margin-bottom: 10px;">
                <h4 style="margin: 0;">Nouvelle question ${index + 1}</h4>
                <button type="button" class="btn-remove-question" onclick="supprimerQuestion(${index})" style="background: #dc3545; color: white; border: none; padding: 5px 10px; border-radius: 3px; cursor: pointer;">
                    <i class="fas fa-trash"></i>
                </button>
            </div>
            <div style="margin-bottom: 10px;">
                <label>Énoncé:</label>
                <textarea class="question-enonce form-control" rows="3" style="width: 100%;" placeholder="Entrez l'énoncé de la question..."></textarea>
            </div>
            <div style="display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 10px; margin-bottom: 10px;">
                <div>
                    <label>Type:</label>
                    <select class="question-type form-control" style="width: 100%;">
                        <option value="qcm">QCM</option>
                        <option value="ouverte">Question ouverte</option>
                        <option value="numerique">Réponse numérique</option>
                    </select>
                </div>
                <div>
                    <label>Points:</label>
                    <input type="number" class="question-points form-control" value="1.0" step="0.5" min="0" style="width: 100%;">
                </div>
                <div>
                    <label>Réponse correcte:</label>
                    <input type="text" class="question-reponse form-control" style="width: 100%;" placeholder="Réponse attendue...">
                </div>
            </div>
        </div>
    `;
    
    container.innerHTML += questionHtml;
}

function supprimerQuestion(index) {
    const container = document.getElementById('questions-container');
    const items = container.querySelectorAll('.question-item');
    
    if (items[index]) {
        items[index].remove();
        
        // Renuméroter les questions
        renumberQuestions();
    }
}

function renumberQuestions() {
    const items = document.querySelectorAll('.question-item');
    items.forEach((item, index) => {
        const title = item.querySelector('h4');
        if (title) {
            title.textContent = `Question ${index + 1}`;
        }
    });
}

// ===== EXPORT DES NOUVELLES FONCTIONS =====
window.sauvegarderToutesQuestions = sauvegarderToutesQuestions;
window.ajouterQuestion = ajouterQuestion;
window.supprimerQuestion = supprimerQuestion;
window.renumberQuestions = renumberQuestions;
window.chargerQuestions = chargerQuestions;
window.afficherQuestions = afficherQuestions;
// ===== EXPORT DES FONCTIONS POUR L'HTML =====
window.confirmerSuppression = confirmerSuppression;
window.openEtudiantsModal = openEtudiantsModal;
window.closeEtudiantsModal = closeEtudiantsModal;
window.openDateLimiteModal = openDateLimiteModal;
window.closeDateLimiteModal = closeDateLimiteModal;
window.closeConfirmationModal = closeConfirmationModal;
window.addEtudiant = addEtudiant;
window.removeEtudiant = removeEtudiant;
window.saveEtudiants = saveEtudiants;
window.saveDateLimite = saveDateLimite;
window.executerSuppression = executerSuppression;