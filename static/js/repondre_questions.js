// Variables globales
let questionsData = [];
let reponsesData = {};
let questionCourante = 0;
let tempsRestant = 0;
let timerInterval = null;
let autoSaveInterval = null;
let tpId = '';
let etudiantId = '';
let estSoumissionEnCours = false;
let derniereSauvegarde = null;
let dernierSaveTime = new Date();
let dateLimiteDepassee = false;
let tpDejaSoumis = false;

// Fonction d'initialisation
function initialiserQuestionnaire(idTP, idEtudiant) {
    tpId = idTP;
    etudiantId = idEtudiant;
    
    verifierEtatSoumission();
    chargerQuestions();
    verifierDateLimite();
    mettreAJourProgression();
    configurerEvenements();
    demarrerAutoSave();
    mettreAJourTempsRestant();
}

// Vérifier si le TP est déjà soumis
async function verifierEtatSoumission() {
    try {
        const response = await fetch(`/api/tp/${tpId}/etat_soumission`);
        const data = await response.json();
        
        if (data.success && data.est_soumis) {
            tpDejaSoumis = true;
            desactiverInterfaceApresSoumission();
        }
    } catch (error) {
        console.error('Erreur vérification état soumission:', error);
    }
}

// Désactiver l'interface après soumission
function desactiverInterfaceApresSoumission() {
    const navButtons = document.querySelectorAll('#prev-question, #next-question, .jump-button, .submit-btn-header, .submit-btn-footer');
    navButtons.forEach(btn => {
        btn.disabled = true;
        btn.classList.add('disabled');
    });
    
    const textareas = document.querySelectorAll('.reponse-textarea');
    textareas.forEach(textarea => {
        textarea.disabled = true;
        textarea.placeholder = 'TP déjà soumis - Modification impossible';
    });
    
    const options = document.querySelectorAll('.option-item');
    options.forEach(option => {
        option.style.pointerEvents = 'none';
        option.style.opacity = '0.6';
    });
    
    const checkboxes = document.querySelectorAll('.option-checkbox');
    checkboxes.forEach(checkbox => {
        checkbox.style.pointerEvents = 'none';
    });
    
    const fileInputs = document.querySelectorAll('input[type="file"]');
    fileInputs.forEach(input => {
        input.disabled = true;
    });
    
    const submitButtons = document.querySelectorAll('.submit-btn-header, .submit-btn-footer');
    submitButtons.forEach(btn => {
        btn.innerHTML = '<i class="fas fa-check-circle"></i> Déjà soumis';
        btn.title = 'Ce TP a déjà été soumis';
    });
    
    const alertBanner = document.createElement('div');
    alertBanner.className = 'submission-alert-banner';
    alertBanner.innerHTML = `
        <div class="alert-content">
            <i class="fas fa-check-circle"></i>
            <div>
                <strong>TP déjà soumis</strong>
                <p>Vous avez déjà soumis ce TP. Vous pouvez consulter la correction.</p>
            </div>
        </div>
        <a href="/tp/${tpId}/correction" class="btn-correction">
            <i class="fas fa-eye"></i> Voir la correction
        </a>
    `;
    
    const container = document.querySelector('.question-container') || document.body;
    container.parentNode.insertBefore(alertBanner, container);
    
    if (autoSaveInterval) {
        clearInterval(autoSaveInterval);
        autoSaveInterval = null;
    }
}

// Vérifier la date limite du TP
async function verifierDateLimite() {
    try {
        const response = await fetch(`/api/tp/${tpId}/date_limite`);
        const data = await response.json();
        
        if (data.success && data.date_limite) {
            const dateLimite = new Date(data.date_limite);
            const maintenant = new Date();
            
            if (dateLimite < maintenant) {
                dateLimiteDepassee = true;
                afficherAlerteDateLimite();
                return false;
            }
            
            dateLimiteDepassee = false;
            tempsRestant = 0;
            
            const dateLimiteText = document.getElementById('temps-restant-text');
            if (dateLimiteText) {
                const diff = dateLimite - maintenant;
                const jours = Math.floor(diff / (1000 * 60 * 60 * 24));
                const heures = Math.floor((diff % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60));
                const minutes = Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60));
                
                if (jours > 0) {
                    dateLimiteText.textContent = `${jours} jour(s) restant(s)`;
                } else if (heures > 0) {
                    dateLimiteText.textContent = `${heures}h ${minutes}m restant(s)`;
                } else {
                    dateLimiteText.textContent = `${minutes} minute(s) restant(s)`;
                }
            }
            
            return true;
        }
    } catch (error) {
        console.error('Erreur vérification date limite:', error);
    }
    return true;
}

// Afficher alerte date limite dépassée
function afficherAlerteDateLimite() {
    const submitBtns = document.querySelectorAll('.submit-btn, #submit-final-btn');
    submitBtns.forEach(btn => {
        btn.disabled = true;
        btn.title = 'Date limite dépassée - soumission non disponible';
        btn.innerHTML = '<i class="fas fa-ban"></i> Soumission indisponible';
    });
    
    const alertDiv = document.createElement('div');
    alertDiv.className = 'time-expired-alert';
    alertDiv.innerHTML = `
        <i class="fas fa-exclamation-triangle"></i>
        <div>
            <strong>Date limite dépassée</strong>
            <p>Vous pouvez continuer à répondre, mais la soumission n'est plus possible.</p>
        </div>
        <button class="close-alert" onclick="this.parentElement.remove()">
            <i class="fas fa-times"></i>
        </button>
    `;
    
    document.body.appendChild(alertDiv);
    
    setTimeout(() => {
        if (alertDiv.parentNode) {
            alertDiv.style.opacity = '0';
            setTimeout(() => alertDiv.remove(), 300);
        }
    }, 15000);
}

// Charger les questions depuis le serveur
async function chargerQuestions() {
    try {
        const response = await fetch(`/tp/${tpId}/questions`);
        const data = await response.json();
        
        if (data.success && data.questions && data.questions.length > 0) {
            questionsData = data.questions;
            
            questionsData.forEach((question, index) => {
                const questionId = question.id || index;
                reponsesData[questionId] = {
                    type: question.type_question || question.type,
                    reponse: '',
                    fichier: null,
                    sauvegarde: false
                };
            });
            
            afficherQuestion(0);
            creerNavigation();
            chargerReponsesSauvegardees();
        }
    } catch (error) {
        console.error('Erreur chargement questions:', error);
    }
}

// Charger les réponses sauvegardées
async function chargerReponsesSauvegardees() {
    try {
        const response = await fetch(`/api/tp/${tpId}/reponses_sauvegardees`);
        const data = await response.json();
        
        if (data.success && data.reponses) {
            data.reponses.forEach(reponse => {
                const questionId = reponse.question_id;
                if (reponsesData[questionId]) {
                    reponsesData[questionId].reponse = reponse.reponse || '';
                    
                    if (reponse.fichier_url && (reponse.type === 'image' || reponse.type === 'image_reponse')) {
                        reponsesData[questionId].fichier = {
                            nom: reponse.fichier_nom || 'image.jpg',
                            url: reponse.fichier_url,
                            taille: reponse.fichier_taille || '',
                            type: reponse.fichier_type || 'image/jpeg'
                        };
                    }
                    
                    reponsesData[questionId].sauvegarde = true;
                }
            });
            
            mettreAJourProgression();
            mettreAJourNavigation();
            
            if (data.reponses.length > 0 && data.reponses[0].date_sauvegarde) {
                dernierSaveTime = new Date(data.reponses[0].date_sauvegarde);
                mettreAJourAffichageSauvegarde();
            }
            
            afficherQuestion(questionCourante);
        }
    } catch (error) {
        console.error('Erreur chargement réponses:', error);
    }
}

// Afficher une question spécifique
function afficherQuestion(index) {
    if (index < 0 || index >= questionsData.length) return;
    
    questionCourante = index;
    const question = questionsData[index];
    const questionId = question.id || index;
    
    document.getElementById('question-numero').textContent = `Question ${index + 1}/${questionsData.length}`;
    document.getElementById('question-texte').textContent = question.texte || question.enonce || '';
    document.getElementById('question-points').innerHTML = `<i class="fas fa-star"></i> ${question.points || 1.0} points`;
    
    const reponse = reponsesData[questionId];
    const statusElement = document.getElementById('question-status');
    if (reponse) {
        let isAnswered = false;
        
        if (reponse.type === 'case_cocher') {
            try {
                const parsed = JSON.parse(reponse.reponse || '[]');
                isAnswered = parsed.length > 0;
            } catch (e) {
                isAnswered = reponse.reponse && reponse.reponse.trim() !== '';
            }
        } else {
            isAnswered = reponse.reponse && reponse.reponse.trim() !== '';
        }
        
        const hasFileResponse = reponse.fichier !== null;
        isAnswered = isAnswered || hasFileResponse;
        
        if (isAnswered) {
            statusElement.innerHTML = '<i class="fas fa-check-circle"></i> Répondu';
            statusElement.classList.add('answered');
        } else {
            statusElement.innerHTML = '<i class="fas fa-circle"></i> Non répondu';
            statusElement.classList.remove('answered');
        }
    }
    
    afficherTypeReponse(question);
    chargerReponseExistante(questionId);
    mettreAJourNavigation();
    mettreAJourProgression();
}

// Afficher le type de réponse approprié
function afficherTypeReponse(question) {
    const type = question.type_question || question.type;
    const container = document.getElementById('reponse-container');
    const questionId = question.id || questionsData.indexOf(question);
    
    let html = '';
    const isDisabled = tpDejaSoumis ? 'disabled' : '';
    const disabledClass = tpDejaSoumis ? 'disabled-field' : '';
    
    switch(type) {
        case 'ouverte':
        case 'texte':
            html = `
                <div class="reponse-image-question ${disabledClass}">
                    <label for="reponse-texte-${questionId}" class="reponse-label">
                        <i class="fas fa-edit"></i> Votre réponse :
                    </label>
                    <textarea class="reponse-textarea" 
                              id="reponse-texte-${questionId}"
                              placeholder="${tpDejaSoumis ? 'TP déjà soumis - Modification impossible' : 'Tapez votre réponse ici...'}"
                              rows="6"
                              ${isDisabled}></textarea>
                    <div class="textarea-info">
                        <span class="char-count" id="char-count-${questionId}">0 caractères</span>
                    </div>
                </div>
            `;
            break;
            
        case 'qcm':
            let options = [];
            try {
                options = JSON.parse(question.reponse_correcte || '[]');
            } catch (e) {
                options = ['Option 1', 'Option 2', 'Option 3'];
            }
            
            const optionDisabledClass = tpDejaSoumis ? 'disabled-option' : '';
            html = '<div class="options-container">';
            options.forEach((option, idx) => {
                html += `
                    <div class="option-item ${optionDisabledClass}" onclick="${!tpDejaSoumis ? `selectionnerOption(${questionId}, ${idx})` : ''}" 
                         id="option-${questionId}-${idx}">
                        <div class="option-radio"></div>
                        <div class="option-text">${option}</div>
                    </div>
                `;
            });
            html += '</div>';
            break;
            
        case 'case_cocher':
            let checkboxes = [];
            try {
                checkboxes = JSON.parse(question.reponse_correcte || '[]');
            } catch (e) {
                checkboxes = ['Option 1', 'Option 2', 'Option 3', 'Option 4'];
            }
            
            const checkboxDisabledClass = tpDejaSoumis ? 'disabled-option' : '';
            html = '<div class="options-container">';
            checkboxes.forEach((checkbox, idx) => {
                html += `
                    <div class="option-item ${checkboxDisabledClass}" onclick="${!tpDejaSoumis ? `selectionnerCheckbox(${questionId}, ${idx})` : ''}"
                         id="checkbox-${questionId}-${idx}">
                        <div class="option-checkbox"></div>
                        <div class="option-text">${checkbox}</div>
                    </div>
                `;
            });
            html += '</div>';
            break;
            
        case 'image_question':
            let imageHtml = '';
            if (question.image_url) {
                imageHtml = `
                    <div class="question-image-container">
                        <h4><i class="fas fa-image"></i> Image de la question :</h4>
                        <div class="question-image-preview">
                            <img src="${question.image_url}" 
                                 alt="Image de la question" 
                                 class="question-image-display"
                                 onclick="agrandirImage('${question.image_url}')">
                            <div class="image-overlay">
                                <i class="fas fa-search-plus"></i>
                                <span>Cliquez pour agrandir</span>
                            </div>
                        </div>
                    </div>
                `;
            }
            
            html = `
                ${imageHtml}
                <div class="reponse-image-question ${disabledClass}">
                    <label for="reponse-texte-${questionId}" class="reponse-label">
                        <i class="fas fa-edit"></i> Votre réponse :
                    </label>
                    <textarea class="reponse-textarea" 
                              id="reponse-texte-${questionId}"
                              placeholder="${tpDejaSoumis ? 'TP déjà soumis - Modification impossible' : 'Tapez votre réponse ici...'}"
                              rows="6"
                              ${isDisabled}></textarea>
                    <div class="textarea-info">
                        <span class="char-count" id="char-count-${questionId}">0 caractères</span>
                    </div>
                </div>
            `;
            break;
            
        case 'image':
        case 'image_reponse':
            const uploadDisabledClass = tpDejaSoumis ? 'disabled-upload' : '';
            html = `
                <div class="reponse-image-question ${disabledClass}">
                    <label for="reponse-texte-${questionId}" class="reponse-label">
                        <i class="fas fa-edit"></i> Votre réponse textuelle (facultatif) :
                    </label>
                    <textarea class="reponse-textarea" 
                              id="reponse-texte-${questionId}"
                              placeholder="${tpDejaSoumis ? 'TP déjà soumis - Modification impossible' : 'Vous pouvez ajouter un commentaire ou explication...'}"
                              rows="4"
                              ${isDisabled}></textarea>
                    <div class="textarea-info">
                        <span class="char-count" id="char-count-${questionId}">0 caractères</span>
                    </div>
                </div>
                
                <div class="upload-section ${uploadDisabledClass}">
                    <h4><i class="fas fa-upload"></i> Télécharger une image (requis) :</h4>
                    <div class="upload-container" onclick="${!tpDejaSoumis ? `document.getElementById('file-input-${questionId}').click()` : ''}">
                        <div class="upload-icon">
                            <i class="fas fa-cloud-upload-alt"></i>
                        </div>
                        <div class="upload-text">
                            ${tpDejaSoumis ? 'TP déjà soumis - Upload désactivé' : 'Cliquez pour télécharger une image'}
                        </div>
                        <div class="upload-hint">
                            Formats acceptés: JPG, PNG, GIF, BMP (max 16MB)
                        </div>
                    </div>
                    <input type="file" id="file-input-${questionId}" 
                           style="display: none" 
                           accept="image/*"
                           ${isDisabled}
                           onchange="${!tpDejaSoumis ? `gererUploadImage(${questionId}, this)` : ''}">
                    <div id="file-preview-${questionId}" class="file-preview" style="display: none"></div>
                </div>
            `;
            break;
    }
    
    container.innerHTML = html;
    
    if ((type === 'ouverte' || type === 'texte' || type === 'image_question' || 
        type === 'image' || type === 'image_reponse') && !tpDejaSoumis) {
        const textarea = document.getElementById(`reponse-texte-${questionId}`);
        const charCount = document.getElementById(`char-count-${questionId}`);
        
        if (textarea && charCount) {
            let timeoutId = null;
            
            textarea.addEventListener('input', function() {
                charCount.textContent = `${this.value.length} caractères`;
                
                reponsesData[questionId].reponse = this.value;
                
                clearTimeout(timeoutId);
                timeoutId = setTimeout(() => {
                    sauvegarderReponseSilencieuse(questionId);
                }, 1000);
            });
            
            textarea.addEventListener('blur', function() {
                reponsesData[questionId].reponse = this.value;
                sauvegarderReponseSilencieuse(questionId);
            });
        }
    }
}

// Charger une réponse existante
function chargerReponseExistante(questionId) {
    const reponse = reponsesData[questionId];
    if (!reponse) return;
    
    const type = reponse.type;
    
    switch(type) {
        case 'ouverte':
        case 'texte':
        case 'image_question':
        case 'image':
        case 'image_reponse':
            const textarea = document.getElementById(`reponse-texte-${questionId}`);
            if (textarea) {
                textarea.value = reponse.reponse || '';
                const charCount = document.getElementById(`char-count-${questionId}`);
                if (charCount) {
                    charCount.textContent = `${textarea.value.length} caractères`;
                }
            }
            if ((type === 'image' || type === 'image_reponse') && reponse.fichier) {
                afficherPreviewFichier(questionId, reponse.fichier);
            }
            break;
            
        case 'qcm':
            if (reponse.reponse) {
                const optionText = reponse.reponse;
                const options = document.querySelectorAll(`[id^="option-${questionId}-"]`);
                for (let i = 0; i < options.length; i++) {
                    const opt = options[i];
                    const text = opt.querySelector('.option-text')?.textContent || opt.textContent;
                    if (text === optionText) {
                        selectionnerOption(questionId, i);
                        break;
                    }
                }
            }
            break;
            
        case 'case_cocher':
            try {
                const selectedTexts = JSON.parse(reponse.reponse || '[]');
                const checkboxes = document.querySelectorAll(`[id^="checkbox-${questionId}-"]`);
                for (let i = 0; i < checkboxes.length; i++) {
                    const cb = checkboxes[i];
                    const text = cb.querySelector('.option-text')?.textContent || cb.textContent;
                    if (selectedTexts.includes(text)) {
                        selectionnerCheckbox(questionId, i);
                    }
                }
            } catch (e) {
                console.error('Erreur parsing réponse cases:', e);
            }
            break;
    }
}

// Gérer la sélection d'option QCM
function selectionnerOption(questionId, optionIndex) {
    if (tpDejaSoumis) return;
    
    const options = document.querySelectorAll(`[id^="option-${questionId}-"]`);
    options.forEach(opt => {
        opt.classList.remove('selected');
    });
    
    const option = document.getElementById(`option-${questionId}-${optionIndex}`);
    if (option) {
        option.classList.add('selected');
        
        const optionText = option.querySelector('.option-text')?.textContent || option.textContent;
        reponsesData[questionId].reponse = optionText;
        sauvegarderReponseSilencieuse(questionId);
    }
}

// Gérer la sélection de cases à cocher
function selectionnerCheckbox(questionId, checkboxIndex) {
    if (tpDejaSoumis) return;
    
    const checkbox = document.getElementById(`checkbox-${questionId}-${checkboxIndex}`);
    if (!checkbox) return;
    
    checkbox.classList.toggle('selected');
    
    const checkboxes = document.querySelectorAll(`[id^="checkbox-${questionId}-"]`);
    const selectedTexts = [];
    checkboxes.forEach((cb, idx) => {
        if (cb.classList.contains('selected')) {
            const optionText = cb.querySelector('.option-text')?.textContent || cb.textContent;
            selectedTexts.push(optionText);
        }
    });
    
    reponsesData[questionId].reponse = JSON.stringify(selectedTexts);
    sauvegarderReponseSilencieuse(questionId);
}

// Gérer l'upload d'image
function gererUploadImage(questionId, input) {
    if (tpDejaSoumis) return;
    
    const file = input.files[0];
    if (!file) return;
    
    if (file.size > 16 * 1024 * 1024) {
        afficherToast('Fichier trop volumineux (max 16MB)', 'error');
        return;
    }
    
    if (!file.type.match('image.*')) {
        afficherToast('Format de fichier non supporté. Utilisez une image.', 'error');
        return;
    }
    
    const textarea = document.getElementById(`reponse-texte-${questionId}`);
    const commentaire = textarea ? textarea.value : (reponsesData[questionId].reponse || '');
    
    reponsesData[questionId].reponse = commentaire;
    
    const preview = document.getElementById(`file-preview-${questionId}`);
    if (preview) {
        preview.innerHTML = `
            <div class="preview-loading">
                <i class="fas fa-spinner fa-spin"></i>
                <div>Chargement...</div>
            </div>
        `;
        preview.style.display = 'flex';
    }
    
    const reader = new FileReader();
    reader.onload = function(e) {
        reponsesData[questionId].fichier = {
            nom: file.name,
            taille: (file.size / 1024).toFixed(1) + ' KB',
            type: file.type,
            data: e.target.result
        };
        
        afficherPreviewFichier(questionId, reponsesData[questionId].fichier);
        sauvegarderFichierAvecCommentaire(questionId, file, commentaire);
    };
    
    reader.readAsDataURL(file);
}

// Sauvegarder le fichier avec le commentaire
async function sauvegarderFichierAvecCommentaire(questionId, file, commentaire) {
    if (tpDejaSoumis) return false;
    
    try {
        const formData = new FormData();
        formData.append('question_id', questionId);
        formData.append('tp_id', tpId);
        formData.append('etudiant_id', etudiantId);
        formData.append('reponse_texte', commentaire);
        formData.append('file', file);
        
        const response = await fetch(`/api/tp/${tpId}/upload_reponse_image`, {
            method: 'POST',
            body: formData
        });
        
        const data = await response.json();
        
        if (data.success) {
            if (data.image_url) {
                reponsesData[questionId].fichier.url = data.image_url;
                reponsesData[questionId].fichier.nom = data.filename || file.name;
                reponsesData[questionId].fichier.taille = data.file_size ? 
                    `${(data.file_size / 1024).toFixed(1)} KB` : '';
                reponsesData[questionId].fichier.data = reponsesData[questionId].fichier.data || '';
            }
            
            reponsesData[questionId].reponse = commentaire;
            
            dernierSaveTime = new Date();
            mettreAJourAffichageSauvegarde();
            afficherToast('Image et commentaire sauvegardés', 'success');
            return true;
        } else {
            afficherToast('Erreur: ' + (data.message || 'Erreur inconnue'), 'error');
            return false;
        }
    } catch (error) {
        console.error('Erreur sauvegarde:', error);
        afficherToast('Erreur de connexion', 'error');
        return false;
    }
}

// Convertir base64 en Blob
function base64ToBlob(base64, contentType = '') {
    try {
        const byteCharacters = atob(base64.split(',')[1]);
        const byteArrays = [];
        
        for (let offset = 0; offset < byteCharacters.length; offset += 512) {
            const slice = byteCharacters.slice(offset, offset + 512);
            const byteNumbers = new Array(slice.length);
            for (let i = 0; i < slice.length; i++) {
                byteNumbers[i] = slice.charCodeAt(i);
            }
            const byteArray = new Uint8Array(byteNumbers);
            byteArrays.push(byteArray);
        }
        
        return new Blob(byteArrays, { type: contentType });
    } catch (error) {
        console.error('Erreur conversion base64 en Blob:', error);
        return null;
    }
}

// Afficher le preview du fichier
function afficherPreviewFichier(questionId, fichier) {
    const preview = document.getElementById(`file-preview-${questionId}`);
    const uploadContainer = document.querySelector(`#file-input-${questionId}`).previousElementSibling;
    
    if (preview) {
        let previewHtml = '';
        
        if (fichier.data && fichier.data.startsWith('data:image')) {
            previewHtml = `
                <div class="preview-image">
                    <img src="${fichier.data}" alt="Aperçu de l'image" 
                         onload="this.style.opacity='1'"
                         style="opacity:0; transition: opacity 0.3s">
                </div>
                <div class="preview-info">
                    <div class="preview-name">${fichier.nom}</div>
                    <div class="preview-size">${fichier.taille}</div>
                    <div class="preview-actions">
                        <button class="action-btn" onclick="agrandirImage('${fichier.data}')" title="Agrandir">
                            <i class="fas fa-search-plus"></i>
                        </button>
                        <button class="action-btn" onclick="telechargerImage('${fichier.data}', '${fichier.nom}')" title="Télécharger">
                            <i class="fas fa-download"></i>
                        </button>
                    </div>
                </div>
                <button class="remove-file" onclick="${!tpDejaSoumis ? `supprimerFichier(${questionId})` : ''}" title="Supprimer" ${tpDejaSoumis ? 'disabled' : ''}>
                    <i class="fas fa-times"></i>
                </button>
            `;
        }
        else if (fichier.url) {
            previewHtml = `
                <div class="preview-image">
                    <img src="${fichier.url}" alt="Aperçu de l'image" 
                         onload="this.style.opacity='1'"
                         onerror="this.onerror=null; this.src='data:image/svg+xml;utf8,<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"100\" height=\"100\" viewBox=\"0 0 100 100\"><rect width=\"100\" height=\"100\" fill=\"%23f0f0f0\"/><text x=\"50\" y=\"50\" font-family=\"Arial\" font-size=\"14\" fill=\"%23666\" text-anchor=\"middle\" dy=\".3em\">Image</text></svg>'"
                         style="opacity:0; transition: opacity 0.3s">
                </div>
                <div class="preview-info">
                    <div class="preview-name">${fichier.nom}</div>
                    <div class="preview-size">${fichier.taille || 'Téléchargé'}</div>
                    <div class="preview-actions">
                        <button class="action-btn" onclick="agrandirImage('${fichier.url}')" title="Agrandir">
                            <i class="fas fa-search-plus"></i>
                        </button>
                        <a href="${fichier.url}" target="_blank" class="action-btn" download="${fichier.nom}" title="Télécharger">
                            <i class="fas fa-download"></i>
                        </a>
                    </div>
                </div>
                <button class="remove-file" onclick="${!tpDejaSoumis ? `supprimerFichier(${questionId})` : ''}" title="Supprimer" ${tpDejaSoumis ? 'disabled' : ''}>
                    <i class="fas fa-times"></i>
                </button>
            `;
        } else {
            previewHtml = `
                <div class="preview-icon">
                    <i class="fas fa-file-image"></i>
                </div>
                <div class="preview-info">
                    <div class="preview-name">${fichier.nom}</div>
                    <div class="preview-size">${fichier.taille || ''}</div>
                    <div class="preview-actions">
                        ${fichier.url ? `<a href="${fichier.url}" target="_blank" class="action-btn" download="${fichier.nom}">
                            <i class="fas fa-download"></i> Télécharger
                        </a>` : ''}
                    </div>
                </div>
                <button class="remove-file" onclick="${!tpDejaSoumis ? `supprimerFichier(${questionId})` : ''}" ${tpDejaSoumis ? 'disabled' : ''}>
                    <i class="fas fa-times"></i>
                </button>
            `;
        }
        
        preview.innerHTML = previewHtml;
        preview.style.display = 'flex';
        
        if (uploadContainer) {
            uploadContainer.style.display = 'none';
        }
    }
}

function telechargerImage(dataUrl, filename) {
    const a = document.createElement('a');
    a.href = dataUrl;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
}

async function supprimerFichier(questionId) {
    if (tpDejaSoumis) return;
    
    reponsesData[questionId].fichier = null;
    
    const preview = document.getElementById(`file-preview-${questionId}`);
    const uploadContainer = document.querySelector(`#file-input-${questionId}`).previousElementSibling;
    
    if (preview) {
        preview.style.display = 'none';
    }
    if (uploadContainer) {
        uploadContainer.style.display = 'block';
    }
    
    const fileInput = document.getElementById(`file-input-${questionId}`);
    if (fileInput) {
        fileInput.value = '';
    }
    
    sauvegarderReponseSilencieuse(questionId);
    
    try {
        const response = await fetch(`/api/tp/${tpId}/supprimer_fichier`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                question_id: questionId,
                tp_id: tpId,
                etudiant_id: etudiantId
            })
        });
        
        const data = await response.json();
        if (data.success) {
            afficherToast('Image supprimée', 'success');
        }
    } catch (error) {
        console.error('Erreur suppression fichier:', error);
    }
}

function sauvegarderReponseSilencieuse(questionId) {
    if (tpDejaSoumis) return;
    
    localStorage.setItem(`tp_${tpId}_reponse_${questionId}`, JSON.stringify({
        type: reponsesData[questionId].type,
        reponse: reponsesData[questionId].reponse,
        fichier: reponsesData[questionId].fichier,
        sauvegarde: true
    }));
    
    mettreAJourProgression();
    mettreAJourNavigation();
    
    const question = questionsData[questionCourante];
    if (question && (question.id == questionId || questionCourante == questionId)) {
        const statusElement = document.getElementById('question-status');
        const reponse = reponsesData[questionId];
        
        let isAnswered = false;
        if (reponse.type === 'case_cocher') {
            try {
                const parsed = JSON.parse(reponse.reponse || '[]');
                isAnswered = parsed.length > 0;
            } catch (e) {
                isAnswered = reponse.reponse && reponse.reponse.trim() !== '';
            }
        } else {
            isAnswered = reponse.reponse && reponse.reponse.trim() !== '';
        }
        
        const hasFileResponse = reponse.fichier !== null;
        isAnswered = isAnswered || hasFileResponse;
        
        if (isAnswered) {
            statusElement.innerHTML = '<i class="fas fa-check-circle"></i> Répondu';
            statusElement.classList.add('answered');
        } else {
            statusElement.innerHTML = '<i class="fas fa-circle"></i> Non répondu';
            statusElement.classList.remove('answered');
        }
    }
}

// Démarrer l'auto-save - INCLURE les commentaires des questions image
function demarrerAutoSave() {
    if (tpDejaSoumis) return;
    if (autoSaveInterval) clearInterval(autoSaveInterval);
    
    autoSaveInterval = setInterval(async () => {
        const reponsesTextuelles = Object.keys(reponsesData)
            .filter(questionId => {
                const reponse = reponsesData[questionId];
                let hasTextResponse = false;
                
                if (reponse.type === 'case_cocher') {
                    try {
                        const parsed = JSON.parse(reponse.reponse || '[]');
                        hasTextResponse = parsed.length > 0;
                    } catch (e) {
                        hasTextResponse = reponse.reponse && reponse.reponse.trim() !== '';
                    }
                } else {
                    hasTextResponse = reponse.reponse && reponse.reponse.trim() !== '';
                }
                
                // Inclure TOUS les types de questions qui ont du texte
                return hasTextResponse;
            });
        
        if (reponsesTextuelles.length > 0) {
            await sauvegarderReponsesTextuelles(reponsesTextuelles);
        }
    }, 15000);
}

async function sauvegarderReponsesTextuelles(questionIds) {
    if (tpDejaSoumis) return;
    
    try {
        const formData = new FormData();
        
        questionIds.forEach(questionId => {
            const reponse = reponsesData[questionId];
            formData.append(`question_${questionId}_id`, questionId);
            formData.append(`question_${questionId}_type`, reponse.type);
            formData.append(`question_${questionId}_reponse`, reponse.reponse || '');
        });
        
        formData.append('tp_id', tpId);
        formData.append('etudiant_id', etudiantId);
        formData.append('timestamp', new Date().toISOString());
        formData.append('count', questionIds.length.toString());

        const response = await fetch(`/api/tp/${tpId}/sauvegarder_auto`, {
            method: 'POST',
            body: formData
        });

        const data = await response.json();
        
        if (data.success) {
            dernierSaveTime = new Date();
            mettreAJourAffichageSauvegarde();
            return data;
        }
        
    } catch (error) {
        // Silencieux
    }
}

// Forcer la sauvegarde - INCLURE les commentaires des questions image
async function forcerSauvegarde() {
    if (tpDejaSoumis) {
        afficherToast('TP déjà soumis - Sauvegarde impossible', 'info');
        return;
    }
    
    const questionIds = Object.keys(reponsesData)
        .filter(questionId => {
            const reponse = reponsesData[questionId];
            let hasTextResponse = false;
            
            if (reponse.type === 'case_cocher') {
                try {
                    const parsed = JSON.parse(reponse.reponse || '[]');
                    hasTextResponse = parsed.length > 0;
                } catch (e) {
                    hasTextResponse = reponse.reponse && reponse.reponse.trim() !== '';
                }
            } else {
                hasTextResponse = reponse.reponse && reponse.reponse.trim() !== '';
            }
            
            const hasFileResponse = reponse.fichier !== null;
            // Inclure les commentaires (hasTextResponse)
            return hasTextResponse || hasFileResponse;
        });
    
    if (questionIds.length > 0) {
        const result = await sauvegarderReponsesTextuelles(questionIds);
        if (result && result.success) {
            afficherToast('Vos réponses ont été sauvegardées', 'success');
        }
    } else {
        afficherToast('Aucune réponse à sauvegarder', 'info');
    }
}

function mettreAJourAffichageSauvegarde() {
    const lastSaveTimeElement = document.getElementById('last-save-time');
    
    if (dernierSaveTime) {
        const now = new Date();
        const diff = Math.floor((now - dernierSaveTime) / 1000);
        
        let text = '';
        if (diff < 60) {
            text = 'À l\'instant';
        } else if (diff < 3600) {
            text = `Il y a ${Math.floor(diff / 60)} minute(s)`;
        } else if (diff < 86400) {
            text = `Il y a ${Math.floor(diff / 3600)} heure(s)`;
        } else {
            text = `Le ${dernierSaveTime.toLocaleDateString('fr-FR')}`;
        }
        
        if (lastSaveTimeElement) lastSaveTimeElement.textContent = text;
    }
}

function mettreAJourTempsRestant() {
    const dateLimiteText = document.getElementById('temps-restant-text');
    if (!dateLimiteText) return;
    dateLimiteText.textContent = 'En cours de calcul...';
}

function mettreAJourProgression() {
    const questionsRepondues = Object.values(reponsesData).filter(r => {
        let hasTextResponse = false;
        
        if (r.type === 'case_cocher') {
            try {
                const parsed = JSON.parse(r.reponse || '[]');
                hasTextResponse = parsed.length > 0;
            } catch (e) {
                hasTextResponse = r.reponse && r.reponse.trim() !== '';
            }
        } else {
            hasTextResponse = r.reponse && r.reponse.trim() !== '';
        }
        
        const hasFileResponse = r.fichier !== null;
        return hasTextResponse || hasFileResponse;
    }).length;
    
    const totalQuestions = questionsData.length;
    const pourcentage = Math.round((questionsRepondues / totalQuestions) * 100);
    
    document.getElementById('progress-value').textContent = `${pourcentage}%`;
    document.getElementById('questions-answered').textContent = `${questionsRepondues}/${totalQuestions}`;
    
    const progressBar = document.getElementById('progress-bar');
    if (progressBar) {
        progressBar.style.width = `${pourcentage}%`;
    }
}

function creerNavigation() {
    const navigation = document.getElementById('question-jump');
    if (!navigation) return;
    
    navigation.innerHTML = '';
    
    questionsData.forEach((_, index) => {
        const button = document.createElement('button');
        button.className = 'jump-button';
        if (tpDejaSoumis) {
            button.classList.add('disabled');
            button.disabled = true;
        }
        button.textContent = index + 1;
        button.onclick = () => allerAQuestion(index);
        
        navigation.appendChild(button);
    });
}

function mettreAJourNavigation() {
    const jumpButtons = document.querySelectorAll('.jump-button');
    const prevButton = document.getElementById('prev-question');
    const nextButton = document.getElementById('next-question');
    
    jumpButtons.forEach((button, index) => {
        button.classList.remove('current');
        button.classList.remove('answered');
        
        if (index === questionCourante) {
            button.classList.add('current');
        }
        
        const questionId = questionsData[index].id || index;
        const reponse = reponsesData[questionId];
        if (reponse) {
            let hasTextResponse = false;
            
            if (reponse.type === 'case_cocher') {
                try {
                    const parsed = JSON.parse(reponse.reponse || '[]');
                    hasTextResponse = parsed.length > 0;
                } catch (e) {
                    hasTextResponse = reponse.reponse && reponse.reponse.trim() !== '';
                }
            } else {
                hasTextResponse = reponse.reponse && reponse.reponse.trim() !== '';
            }
            
            const hasFileResponse = reponse.fichier !== null;
            if (hasTextResponse || hasFileResponse) {
                button.classList.add('answered');
            }
        }
    });
    
    if (prevButton) {
        prevButton.disabled = questionCourante === 0 || tpDejaSoumis;
    }
    
    if (nextButton) {
        nextButton.disabled = questionCourante === questionsData.length - 1 || tpDejaSoumis;
    }
}

function allerAQuestion(index) {
    if (tpDejaSoumis) return;
    if (index < 0 || index >= questionsData.length) return;
    
    const currentQuestionId = questionsData[questionCourante].id || questionCourante;
    sauvegarderReponseSilencieuse(currentQuestionId);
    
    afficherQuestion(index);
    
    document.getElementById('question-container').scrollIntoView({ 
        behavior: 'smooth', 
        block: 'start' 
    });
}

function questionPrecedente() {
    if (tpDejaSoumis) return;
    if (questionCourante > 0) {
        allerAQuestion(questionCourante - 1);
    }
}

function questionSuivante() {
    if (tpDejaSoumis) return;
    if (questionCourante < questionsData.length - 1) {
        allerAQuestion(questionCourante + 1);
    }
}

function agrandirImage(imageUrl) {
    let modal = document.getElementById('image-full-modal');
    if (!modal) {
        modal = document.createElement('div');
        modal.id = 'image-full-modal';
        modal.className = 'image-full-modal';
        modal.innerHTML = `
            <div class="image-full-modal-content">
                <img src="${imageUrl}" alt="Image agrandie" class="image-full-modal-img"
                     onload="this.style.opacity='1'"
                     style="opacity:0; transition: opacity 0.3s">
                <button class="image-full-modal-close" onclick="fermerImageAgrandie()">
                    <i class="fas fa-times"></i>
                </button>
            </div>
        `;
        document.body.appendChild(modal);
        
        modal.addEventListener('click', function(e) {
            if (e.target === modal) {
                fermerImageAgrandie();
            }
        });
    } else {
        const img = modal.querySelector('.image-full-modal-img');
        img.src = imageUrl;
        img.style.opacity = '0';
        setTimeout(() => {
            img.style.opacity = '1';
        }, 100);
    }
    
    modal.classList.add('active');
    document.body.style.overflow = 'hidden';
}

function fermerImageAgrandie() {
    const modal = document.getElementById('image-full-modal');
    if (modal) {
        modal.classList.remove('active');
        document.body.style.overflow = 'auto';
    }
}

function configurerEvenements() {
    document.addEventListener('input', function(e) {
        if (e.target.classList.contains('reponse-textarea')) {
            const match = e.target.id.match(/reponse-texte-(\d+)/);
            if (match) {
                // Géré dans afficherTypeReponse
            }
        }
    });
    
    document.addEventListener('visibilitychange', function() {
        if (document.hidden && !tpDejaSoumis) {
            const questionIds = Object.keys(reponsesData)
                .filter(questionId => {
                    const reponse = reponsesData[questionId];
                    let hasTextResponse = false;
                    
                    if (reponse.type === 'case_cocher') {
                        try {
                            const parsed = JSON.parse(reponse.reponse || '[]');
                            hasTextResponse = parsed.length > 0;
                        } catch (e) {
                            hasTextResponse = reponse.reponse && reponse.reponse.trim() !== '';
                        }
                    } else {
                        hasTextResponse = reponse.reponse && reponse.reponse.trim() !== '';
                    }
                    
                    return hasTextResponse;
                });
            
            if (questionIds.length > 0) {
                sauvegarderReponsesTextuelles(questionIds);
            }
        }
    });
    
    document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape') {
            fermerImageAgrandie();
        }
    });
    
    const submitBtnHeader = document.querySelector('.submit-btn-header');
    if (submitBtnHeader) {
        submitBtnHeader.addEventListener('click', function() {
            if (!tpDejaSoumis) {
                afficherModalSoumission();
            }
        });
    }
    
    const submitBtnFooter = document.querySelector('.submit-btn-footer');
    if (submitBtnFooter) {
        submitBtnFooter.addEventListener('click', function() {
            if (!tpDejaSoumis) {
                afficherModalSoumission();
            }
        });
    }
    
    const submitFinalBtn = document.getElementById('submit-final-btn');
    if (submitFinalBtn) {
        submitFinalBtn.addEventListener('click', soumettreReponses);
    }
    
    const cancelSubmitBtn = document.getElementById('cancel-submit-btn');
    if (cancelSubmitBtn) {
        cancelSubmitBtn.addEventListener('click', fermerModalSoumission);
    }
    
    const closeModalBtn = document.querySelector('.modal-close');
    if (closeModalBtn) {
        closeModalBtn.addEventListener('click', fermerModalSoumission);
    }
}

function afficherModalSoumission() {
    if (tpDejaSoumis) {
        afficherToast('Ce TP a déjà été soumis', 'info');
        return;
    }
    
    if (dateLimiteDepassee) {
        afficherToast('La date limite est dépassée. Vous ne pouvez plus soumettre ce TP.', 'error');
        return;
    }
    
    const questionsRepondues = Object.values(reponsesData).filter(r => {
        let hasTextResponse = false;
        
        if (r.type === 'case_cocher') {
            try {
                const parsed = JSON.parse(r.reponse || '[]');
                hasTextResponse = parsed.length > 0;
            } catch (e) {
                hasTextResponse = r.reponse && r.reponse.trim() !== '';
            }
        } else {
            hasTextResponse = r.reponse && r.reponse.trim() !== '';
        }
        
        const hasFileResponse = r.fichier !== null;
        return hasTextResponse || hasFileResponse;
    }).length;
    
    const totalQuestions = questionsData.length;
    const questionsNonRepondues = totalQuestions - questionsRepondues;
    
    let totalPoints = 0;
    questionsData.forEach(q => {
        totalPoints += q.points || 1.0;
    });
    
    const fichiersCount = Object.values(reponsesData).filter(r => r.fichier !== null).length;
    
    const totalQuestionsEl = document.getElementById('total-questions');
    const answeredCountEl = document.getElementById('answered-count');
    const unansweredCountEl = document.getElementById('unanswered-count');
    const totalPointsEl = document.getElementById('total-points');
    const filesCountEl = document.getElementById('files-count');
    const filesCountDetailEl = document.getElementById('files-count-detail');
    const unansweredWarningEl = document.getElementById('unanswered-warning-count');
    
    if (totalQuestionsEl) totalQuestionsEl.textContent = totalQuestions;
    if (answeredCountEl) answeredCountEl.textContent = questionsRepondues;
    if (unansweredCountEl) unansweredCountEl.textContent = questionsNonRepondues;
    if (totalPointsEl) totalPointsEl.textContent = totalPoints.toFixed(1) + ' points';
    if (filesCountEl) filesCountEl.textContent = fichiersCount;
    if (filesCountDetailEl) filesCountDetailEl.textContent = fichiersCount;
    if (unansweredWarningEl) unansweredWarningEl.textContent = questionsNonRepondues;
    
    const unansweredSection = document.getElementById('unanswered-section');
    const allAnsweredSection = document.getElementById('all-answered-section');
    const filesSection = document.getElementById('files-section');
    
    if (filesSection) {
        if (fichiersCount > 0) {
            filesSection.style.display = 'block';
        } else {
            filesSection.style.display = 'none';
        }
    }
    
    if (questionsNonRepondues > 0) {
        if (unansweredSection) {
            unansweredSection.style.display = 'block';
        }
        if (allAnsweredSection) {
            allAnsweredSection.style.display = 'none';
        }
    } else {
        if (unansweredSection) {
            unansweredSection.style.display = 'none';
        }
        if (allAnsweredSection) {
            allAnsweredSection.style.display = 'block';
        }
    }
    
    const submissionModal = document.getElementById('submission-modal');
    if (submissionModal) {
        submissionModal.style.display = 'flex';
        submissionModal.classList.add('active');
    }
}

function fermerModalSoumission() {
    const submissionModal = document.getElementById('submission-modal');
    if (submissionModal) {
        submissionModal.style.display = 'none';
        submissionModal.classList.remove('active');
    }
}

async function soumettreReponses() {
    if (dateLimiteDepassee) {
        afficherToast('La date limite est dépassée. Vous ne pouvez plus soumettre ce TP.', 'error');
        fermerModalSoumission();
        return;
    }
    
    if (tpDejaSoumis) {
        afficherToast('Ce TP a déjà été soumis', 'info');
        return;
    }
    
    if (estSoumissionEnCours) return;
    estSoumissionEnCours = true;
    
    const submitBtn = document.getElementById('submit-final-btn');
    const originalText = submitBtn ? submitBtn.innerHTML : 'Soumettre';
    
    try {
        if (submitBtn) {
            submitBtn.disabled = true;
            submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Soumission...';
        }
        
        const formData = new FormData();
        formData.append('tp_id', tpId);
        formData.append('etudiant_id', etudiantId);
        formData.append('timestamp', new Date().toISOString());
        
        let questionsAvecReponses = 0;
        let fichiersAEnvoyer = 0;
        
        Object.keys(reponsesData).forEach(questionId => {
            const reponse = reponsesData[questionId];
            if (reponse) {
                let hasTextResponse = false;
                
                if (reponse.type === 'case_cocher') {
                    try {
                        const parsed = JSON.parse(reponse.reponse || '[]');
                        hasTextResponse = parsed.length > 0;
                    } catch (e) {
                        hasTextResponse = reponse.reponse && reponse.reponse.trim() !== '';
                    }
                } else {
                    hasTextResponse = reponse.reponse && reponse.reponse.trim() !== '';
                }
                
                const hasFileResponse = reponse.fichier !== null;
                
                if (hasTextResponse || hasFileResponse) {
                    questionsAvecReponses++;
                    
                    formData.append(`question_${questionId}_reponse`, reponse.reponse || '');
                    formData.append(`question_${questionId}_type`, reponse.type);
                    
                    if (hasFileResponse && reponse.fichier && reponse.fichier.data && 
                        !reponse.fichier.url) {
                        fichiersAEnvoyer++;
                        
                        const blob = base64ToBlob(reponse.fichier.data, reponse.fichier.type);
                        if (blob) {
                            formData.append(`question_${questionId}_file`, blob, reponse.fichier.nom);
                        }
                    }
                    else if (hasFileResponse && reponse.fichier && reponse.fichier.url) {
                        formData.append(`question_${questionId}_file_url`, reponse.fichier.url);
                    }
                }
            }
        });
        
        formData.append('questions_count', questionsAvecReponses.toString());
        formData.append('fichiers_count', fichiersAEnvoyer.toString());
        
        if (questionsAvecReponses === 0) {
            afficherToast('Aucune réponse à soumettre', 'warning');
            estSoumissionEnCours = false;
            if (submitBtn) {
                submitBtn.disabled = false;
                submitBtn.innerHTML = originalText;
            }
            return;
        }
        
        const response = await fetch(`/tp/${tpId}/soumettre_avec_images`, {
            method: 'POST',
            body: formData
        });
        
        const data = await response.json();
        
        if (data.success) {
            tpDejaSoumis = true;
            
            if (timerInterval) {
                clearInterval(timerInterval);
                timerInterval = null;
            }
            if (autoSaveInterval) {
                clearInterval(autoSaveInterval);
                autoSaveInterval = null;
            }
            
            fermerModalSoumission();
            desactiverInterfaceApresSoumission();
            afficherToast('Votre travail a été soumis avec succès !', 'success');
            
            Object.keys(localStorage).forEach(key => {
                if (key.startsWith(`tp_${tpId}_reponse_`)) {
                    localStorage.removeItem(key);
                }
            });
            
            setTimeout(() => {
                window.location.href = data.redirect || `/tp/${tpId}/correction`;
            }, 3000);
        } else {
            afficherToast(`Erreur: ${data.message}`, 'error');
            if (submitBtn) {
                submitBtn.disabled = false;
                submitBtn.innerHTML = originalText;
            }
        }
        
    } catch (error) {
        console.error('Erreur soumission:', error);
        afficherToast('Erreur lors de la soumission: ' + error.message, 'error');
        if (submitBtn) {
            submitBtn.disabled = false;
            submitBtn.innerHTML = originalText;
        }
    } finally {
        estSoumissionEnCours = false;
    }
}

function afficherToast(message, type = 'info') {
    document.querySelectorAll('.toast').forEach(toast => {
        if (toast.parentNode) {
            toast.parentNode.removeChild(toast);
        }
    });
    
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.innerHTML = `
        <i class="fas fa-${type === 'success' ? 'check-circle' : type === 'error' ? 'exclamation-circle' : type === 'warning' ? 'exclamation-triangle' : 'info-circle'}"></i>
        <span>${message}</span>
    `;
    
    document.body.appendChild(toast);
    
    setTimeout(() => {
        toast.style.opacity = '1';
        toast.style.transform = 'translateY(0)';
    }, 10);
    
    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transform = 'translateY(-20px)';
        setTimeout(() => {
            if (toast.parentNode) {
                toast.parentNode.removeChild(toast);
            }
        }, 300);
    }, 3000);
}

document.addEventListener('DOMContentLoaded', function() {
    const scriptTag = document.querySelector('script[data-tp-id]');
    if (scriptTag && scriptTag.dataset.tpId) {
        const tpId = scriptTag.dataset.tpId;
        const etudiantId = scriptTag.dataset.etudiantId || '';
        initialiserQuestionnaire(tpId, etudiantId);
    } else {
        const urlParts = window.location.pathname.split('/');
        const tpIdIndex = urlParts.indexOf('tp') + 1;
        if (tpIdIndex > 0 && urlParts.length > tpIdIndex) {
            initialiserQuestionnaire(urlParts[tpIdIndex], '');
        }
    }
});