// gestion_questions.js - VERSION FINALE COMPLÈTE AVEC GESTION DES IMAGES

// ===== VARIABLES GLOBALES =====
let compteurQuestions = 0;
let questionsData = {};
let estSauvegardeEnCours = false;
let tpId = '';

// ===== FONCTIONS D'INITIALISATION =====

// Fonction d'initialisation principale
function initialiserGestionQuestions(idTP) {
    tpId = idTP;
    console.log(`🚀 Initialisation gestion questions pour TP ${tpId}`);
    
    // Charger les questions existantes
    chargerQuestionsExistantes().then(() => {
        // Après le chargement, initialiser les zones d'upload
        setTimeout(() => {
            initialiserZonesUpload();
        }, 100);
    });
    
    mettreAJourProgression();
    
    document.addEventListener('input', function(e) {
        if (e.target.classList.contains('zone-texte') || 
            e.target.classList.contains('input-points') ||
            e.target.classList.contains('input-option') ||
            e.target.classList.contains('select-type')) {
            mettreAJourStatut();
        }
    });
    
    document.addEventListener('change', function(e) {
        if (e.target.classList.contains('input-image')) {
            mettreAJourStatut();
        }
    });
}

// Initialiser toutes les zones d'upload avec images existantes
function initialiserZonesUpload() {
    console.log("🔧 Initialisation des zones d'upload...");
    
    const cartesQuestions = document.querySelectorAll('.carte-question');
    cartesQuestions.forEach(carte => {
        const id = carte.dataset.id;
        const type = carte.querySelector('.select-type').value;
        
        if (type === 'image_question') {
            const zoneUpload = carte.querySelector('.zone-upload-image');
            if (zoneUpload) {
                const imageUrl = questionsData[id]?.imageUrl;
                
                if (imageUrl) {
                    console.log(`   🔧 Initialisation zone upload question ${id} avec image existante`);
                    
                    // Vérifier si la zone est déjà configurée
                    if (!zoneUpload.querySelector('.preview-image-container')) {
                        zoneUpload.innerHTML = `
                            <div class="titre-options">
                                <i class="fas fa-image"></i> Image de la question
                            </div>
                            <div class="preview-image-container">
                                <img id="preview-${id}" class="preview-image" 
                                     src="${imageUrl}" 
                                     alt="Image de la question"
                                     style="display: block;">
                                <div class="upload-controls">
                                    <label for="image-input-${id}" class="bouton-upload">
                                        <i class="fas fa-cloud-upload-alt"></i>
                                        Changer l'image
                                    </label>
                                    <input type="file" id="image-input-${id}" class="input-image" 
                                           accept="image/*" style="display: none;" 
                                           onchange="previewImage(${id}, this)">
                                    <button type="button" class="bouton-supprimer-image" onclick="supprimerImageQuestion(${id})">
                                        <i class="fas fa-trash"></i>
                                    </button>
                                </div>
                                <div class="info-upload">
                                    <i class="fas fa-info-circle"></i>
                                    Formats acceptés: JPG, PNG, GIF, WEBP. Max: 5MB
                                </div>
                            </div>
                        `;
                    } else {
                        // Si la zone existe déjà, mettre à jour l'image
                        const preview = document.getElementById(`preview-${id}`);
                        if (preview) {
                            preview.src = imageUrl;
                            preview.style.display = 'block';
                        }
                    }
                    
                    zoneUpload.style.display = 'block';
                }
            }
        }
    });
    
    console.log("✅ Zones d'upload initialisées");
}

// ===== FONCTIONS D'INTERFACE UTILISATEUR =====

// Afficher une notification toast
function afficherToast(message, type = 'info') {
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    
    let icon = 'info-circle';
    if (type === 'success') icon = 'check-circle';
    else if (type === 'error') icon = 'exclamation-circle';
    else if (type === 'warning') icon = 'exclamation-triangle';
    
    toast.innerHTML = `
        <i class="fas fa-${icon}"></i>
        <span>${message}</span>
    `;
    
    document.body.appendChild(toast);
    
    setTimeout(() => {
        toast.style.animation = 'slideOut 0.3s ease-out';
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}

// Mettre à jour le statut d'enregistrement
function mettreAJourStatut() {
    const statutEl = document.getElementById('statut-enregistrement');
    const texteStatut = document.getElementById('texte-statut');
    
    if (statutEl && texteStatut) {
        statutEl.style.color = '#ff9800';
        texteStatut.textContent = 'Modifications non sauvegardées';
        texteStatut.style.color = '#ff9800';
    }
}

// Mettre à jour la progression
function mettreAJourProgression() {
    const questions = document.querySelectorAll('.carte-question');
    const nombreQuestions = questions.length;
    const totalPoints = Array.from(questions).reduce((total, question) => {
        const inputPoints = question.querySelector('.input-points');
        return total + (parseFloat(inputPoints?.value) || 0);
    }, 0);
    
    const nombreQuestionsEl = document.getElementById('nombre-questions');
    const totalPointsEl = document.getElementById('total-points');
    
    if (nombreQuestionsEl) nombreQuestionsEl.textContent = nombreQuestions;
    if (totalPointsEl) totalPointsEl.textContent = totalPoints.toFixed(1);
    
    const etatVide = document.getElementById('etat-vide');
    if (etatVide) {
        etatVide.style.display = nombreQuestions > 0 ? 'none' : 'block';
    }
}

// ===== GESTION DES QUESTIONS =====

// Ajouter une nouvelle question
function ajouterQuestion() {
    compteurQuestions++;
    const questionId = compteurQuestions;
    
    console.log(`➕ Ajout question ${questionId}`);
    
    const template = document.getElementById('template-question').innerHTML;
    const html = template.replace(/{id}/g, questionId).replace(/{numero}/g, questionId);
    
    const div = document.createElement('div');
    div.innerHTML = html;
    
    const conteneur = document.getElementById('conteneur-questions');
    if (conteneur.querySelector('#etat-vide')) {
        conteneur.innerHTML = '';
    }
    conteneur.appendChild(div.firstElementChild);
    
    questionsData[questionId] = {
        id: null,
        texte: '',
        type: 'texte',
        points: 1.0,
        options: ['', ''],
        imageFile: null,
        imagePreview: null,
        imageUrl: null
    };
    
    const carte = div.firstElementChild;
    const selectType = carte.querySelector('.select-type');
    selectType.onchange = function() { changerTypeQuestion(questionId); };
    
    const inputPoints = carte.querySelector('.input-points');
    inputPoints.onchange = function() { mettreAJourProgression(); };
    
    const boutonAjouterOption = carte.querySelector('.bouton-ajouter-option');
    if (boutonAjouterOption) {
        boutonAjouterOption.onclick = function() { ajouterOption(questionId); };
    }
    
    const zoneTexte = carte.querySelector('.zone-texte');
    zoneTexte.oninput = function() { mettreAJourStatut(); };
    
    mettreAJourProgression();
    
    div.firstElementChild.scrollIntoView({ behavior: 'smooth', block: 'center' });
    
    afficherToast('Question ajoutée', 'success');
}

// Changer le type de question
function changerTypeQuestion(id) {
    const carte = document.querySelector(`[data-id="${id}"]`);
    const select = carte.querySelector('.select-type');
    const zoneOptions = carte.querySelector('.zone-options');
    const infoImage = carte.querySelector('.info-image');
    const zoneUpload = carte.querySelector('.zone-upload-image');
    const type = select.value;
    
    console.log(`🔄 Changement type question ${id} vers: ${type}`);
    
    if (questionsData[id]) {
        questionsData[id].type = type;
    }
    
    if (zoneOptions) zoneOptions.style.display = 'none';
    if (infoImage) infoImage.style.display = 'none';
    if (zoneUpload) zoneUpload.style.display = 'none';
    
    if (type === 'choix_multiple' || type === 'case_cocher') {
        if (zoneOptions) {
            zoneOptions.style.display = 'block';
        }
    } else if (type === 'image_reponse') {
        if (infoImage) {
            infoImage.style.display = 'block';
        }
    } else if (type === 'image_question') {
        if (zoneUpload) {
            zoneUpload.style.display = 'block';
            
            const existingImageUrl = questionsData[id]?.imageUrl;
            
            if (!zoneUpload.querySelector('.preview-image-container') || 
                !zoneUpload.querySelector('.bouton-upload')) {
                
                console.log(`   🔧 Configuration zone d'upload pour question ${id}`);
                
                zoneUpload.innerHTML = `
                    <div class="titre-options">
                        <i class="fas fa-image"></i> Image de la question
                    </div>
                    <div class="preview-image-container">
                        <img id="preview-${id}" class="preview-image" 
                             src="${existingImageUrl || ''}" 
                             alt="Aperçu de l'image"
                             style="${existingImageUrl ? 'display: block;' : 'display: none;'}">
                        <div class="upload-controls">
                            <label for="image-input-${id}" class="bouton-upload">
                                <i class="fas fa-cloud-upload-alt"></i>
                                ${existingImageUrl ? 'Changer l\'image' : 'Choisir une image'}
                            </label>
                            <input type="file" id="image-input-${id}" class="input-image" 
                                   accept="image/*" style="display: none;" 
                                   onchange="previewImage(${id}, this)">
                            <button type="button" class="bouton-supprimer-image" onclick="supprimerImageQuestion(${id})">
                                <i class="fas fa-trash"></i>
                            </button>
                        </div>
                        <div class="info-upload">
                            <i class="fas fa-info-circle"></i>
                            Formats acceptés: JPG, PNG, GIF, WEBP. Max: 5MB
                        </div>
                    </div>
                `;
            } else if (existingImageUrl) {
                const preview = document.getElementById(`preview-${id}`);
                if (preview) {
                    preview.src = existingImageUrl;
                    preview.style.display = 'block';
                    console.log(`   🖼️  Image existante affichée: ${existingImageUrl}`);
                }
            }
        }
    }
    
    mettreAJourStatut();
}

// ===== GESTION DES IMAGES =====

// Prévisualiser l'image sélectionnée
function previewImage(id, input) {
    const preview = document.getElementById(`preview-${id}`);
    
    if (input.files && input.files[0]) {
        const file = input.files[0];
        
        if (file.size > 5 * 1024 * 1024) {
            afficherToast('Fichier trop volumineux (max 5MB)', 'error');
            input.value = '';
            return;
        }
        
        const validTypes = ['image/jpeg', 'image/png', 'image/gif', 'image/webp', 'image/jpg'];
        if (!validTypes.includes(file.type.toLowerCase())) {
            afficherToast('Format non supporté (JPG, PNG, GIF, WEBP uniquement)', 'error');
            input.value = '';
            return;
        }
        
        const reader = new FileReader();
        
        reader.onload = function(e) {
            preview.src = e.target.result;
            preview.style.display = 'block';
            
            if (questionsData[id]) {
                questionsData[id].imageFile = file;
                questionsData[id].imagePreview = e.target.result;
            }
            
            mettreAJourStatut();
        }
        
        reader.readAsDataURL(file);
    }
}

// Supprimer l'image d'une question
function supprimerImageQuestion(id) {
    const preview = document.getElementById(`preview-${id}`);
    const input = document.getElementById(`image-input-${id}`);
    
    if (preview) {
        preview.src = '';
        preview.style.display = 'none';
    }
    
    if (input) {
        input.value = '';
    }
    
    if (questionsData[id]) {
        delete questionsData[id].imageFile;
        delete questionsData[id].imagePreview;
        questionsData[id].imageUrl = null;
    }
    
    mettreAJourStatut();
    afficherToast('Image supprimée', 'warning');
}

// Uploader l'image vers le serveur
async function uploaderImageQuestion(id) {
    const input = document.getElementById(`image-input-${id}`);
    
    if (!input || !input.files || input.files.length === 0) {
        return questionsData[id]?.imageUrl || null;
    }
    
    const file = input.files[0];
    const formData = new FormData();
    formData.append('image', file);
    formData.append('tp_id', tpId);
    
    try {
        console.log(`📤 Upload image pour question ${id}...`);
        
        const response = await fetch(`/api/tp/${tpId}/upload_question_image`, {
            method: 'POST',
            body: formData
        });
        
        const data = await response.json();
        console.log('Réponse upload:', data);
        
        if (data.success && data.image_url) {
            afficherToast('Image uploadée avec succès', 'success');
            
            const preview = document.getElementById(`preview-${id}`);
            if (preview) {
                preview.src = data.image_url;
                preview.style.display = 'block';
            }
            
            return data.image_url;
        } else {
            afficherToast(`Erreur: ${data.message}`, 'error');
            return null;
        }
    } catch (error) {
        console.error('Erreur upload image:', error);
        afficherToast('Erreur de connexion au serveur', 'error');
        return null;
    }
}

// ===== GESTION DES OPTIONS =====

// Ajouter une option à une question
function ajouterOption(id) {
    const listeOptions = document.getElementById(`liste-options-${id}`);
    if (!listeOptions) return;
    
    const nombreOptions = listeOptions.querySelectorAll('.option-item').length + 1;
    
    const div = document.createElement('div');
    div.className = 'option-item';
    div.innerHTML = `
        <input type="text" class="input-option" placeholder="Option ${nombreOptions}" oninput="mettreAJourStatut()">
        <button class="bouton-supprimer" style="width: 30px; height: 30px;" onclick="supprimerOption(${id}, this)">
            <i class="fas fa-times"></i>
        </button>
    `;
    
    listeOptions.appendChild(div);
    
    if (questionsData[id] && !questionsData[id].options) {
        questionsData[id].options = [];
    }
    if (questionsData[id]) {
        questionsData[id].options.push('');
    }
    
    mettreAJourStatut();
}

// Supprimer une option d'une question
function supprimerOption(id, bouton) {
    const item = bouton.parentElement;
    const listeOptions = item.parentElement;
    
    if (listeOptions.querySelectorAll('.option-item').length > 2) {
        const index = Array.from(listeOptions.children).indexOf(item);
        item.remove();
        
        if (questionsData[id] && questionsData[id].options && questionsData[id].options.length > index) {
            questionsData[id].options.splice(index, 1);
        }
        
        mettreAJourStatut();
    } else {
        afficherToast('Une question doit avoir au moins 2 options', 'warning');
    }
}

// ===== GESTION DE LA SUPPRESSION =====

// Supprimer une question complète
function supprimerQuestion(id) {
    appConfirm('Voulez-vous vraiment supprimer cette question ?', {
        title: 'Supprimer la question',
        confirmLabel: 'Supprimer',
        danger: true
    }).then(function(ok) {
        if (ok) {
            const carte = document.querySelector(`[data-id="${id}"]`);
            if (carte) {
                carte.remove();
                delete questionsData[id];
                
                mettreAJourProgression();
                mettreAJourStatut();
                
                afficherToast('Question supprimée', 'success');
            }
        }
    });
}

// ===== SAUVEGARDE DES QUESTIONS =====

// Enregistrer toutes les questions
async function enregistrerQuestions() {
    if (estSauvegardeEnCours || !tpId) {
        afficherToast('Sauvegarde déjà en cours', 'warning');
        return;
    }
    
    estSauvegardeEnCours = true;
    const btnEnregistrer = document.getElementById('btn-enregistrer');
    const iconOriginal = btnEnregistrer.innerHTML;
    
    try {
        btnEnregistrer.innerHTML = '<i class="fas fa-spinner fa-spin"></i>';
        const statutEl = document.getElementById('statut-enregistrement');
        const texteStatut = document.getElementById('texte-statut');
        if (statutEl && texteStatut) {
            statutEl.style.color = '#2196F3';
            texteStatut.textContent = 'Enregistrement en cours...';
            texteStatut.style.color = '#2196F3';
        }
        
        console.log(`💾 Début sauvegarde pour TP ${tpId}`);
        
        const questions = [];
        const cartesQuestions = document.querySelectorAll('.carte-question');
        
        console.log(`📊 ${cartesQuestions.length} questions à traiter`);
        
        for (const carte of cartesQuestions) {
            const id = carte.dataset.id;
            const type = carte.querySelector('.select-type').value;
            
            if (type === 'image_question') {
                const input = document.getElementById(`image-input-${id}`);
                const hasNewImage = input && input.files && input.files.length > 0;
                const hasExistingUrl = questionsData[id] && questionsData[id].imageUrl;
                
                if (hasNewImage) {
                    console.log(`📤 Upload nouvelle image pour question ${id}`);
                    const imageUrl = await uploaderImageQuestion(id);
                    if (imageUrl) {
                        questionsData[id].imageUrl = imageUrl;
                        console.log(`✅ Image uploadée: ${imageUrl}`);
                    } else {
                        console.log(`❌ Échec upload image pour question ${id}`);
                    }
                } else if (hasExistingUrl) {
                    console.log(`ℹ️  Conservation image existante pour question ${id}: ${questionsData[id].imageUrl}`);
                } else {
                    console.log(`⚠️  Aucune image pour question ${id} (type: image_question)`);
                }
            }
        }
        
        console.log("\n📝 Collecte des données des questions:");
        for (const carte of cartesQuestions) {
            const id = carte.dataset.id;
            const texte = carte.querySelector('.zone-texte').value.trim();
            const type = carte.querySelector('.select-type').value;
            const points = parseFloat(carte.querySelector('.input-points').value) || 1.0;
            
            console.log(`\nQuestion ${id}:`);
            console.log(`  Type: ${type}`);
            console.log(`  Texte: ${texte.substring(0, 50)}${texte.length > 50 ? '...' : ''}`);
            console.log(`  Points: ${points}`);
            
            if (!texte && type !== 'image_question') {
                console.log(`  ❌ Validation: texte manquant`);
                afficherToast(`Question ${id}: texte requis`, 'warning');
                continue;
            }
            
            if (type === 'image_question') {
                const hasImage = questionsData[id] && questionsData[id].imageUrl;
                if (!hasImage) {
                    console.log(`  ❌ Validation: image manquante`);
                    afficherToast(`Question ${id}: image requise`, 'warning');
                    continue;
                }
                console.log(`  ✅ Validation: image présente`);
            }
            
            let reponseCorrecte = '';
            if (type === 'choix_multiple' || type === 'case_cocher') {
                const inputsOptions = carte.querySelectorAll('.input-option');
                const options = Array.from(inputsOptions).map(input => input.value.trim()).filter(opt => opt !== '');
                
                if (options.length < 2) {
                    console.log(`  ❌ Validation: moins de 2 options`);
                    afficherToast(`Question ${id}: minimum 2 options`, 'warning');
                    continue;
                }
                
                reponseCorrecte = JSON.stringify(options);
                console.log(`  Options: ${options.length}`);
            }
            
            let typeBackend = 'qcm';
            switch (type) {
                case 'texte':
                    typeBackend = 'ouverte';
                    break;
                case 'choix_multiple':
                    typeBackend = 'qcm';
                    break;
                case 'case_cocher':
                    typeBackend = 'case_cocher';
                    break;
                case 'image_reponse':
                    typeBackend = 'image_reponse';
                    break;
                case 'image_question':
                    typeBackend = 'image_question';
                    break;
            }
            
            const imageUrl = questionsData[id]?.imageUrl || null;
            console.log(`  Image URL: ${imageUrl || 'aucune'}`);
            
            questions.push({
                texte: texte,
                type_question: typeBackend,
                points: points,
                ordre: parseInt(id),
                reponse_correcte: reponseCorrecte,
                image_url: imageUrl
            });
            
            console.log(`  ✅ Prête pour envoi`);
        }
        
        if (questions.length === 0) {
            console.log('❌ Aucune question valide à enregistrer');
            afficherToast('Aucune question valide à enregistrer', 'warning');
            estSauvegardeEnCours = false;
            btnEnregistrer.innerHTML = iconOriginal;
            return;
        }
        
        console.log(`\n📤 Envoi de ${questions.length} questions au serveur`);
        
        const response = await fetch(`/api/tp/${tpId}/questions`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-Requested-With': 'XMLHttpRequest'
            },
            body: JSON.stringify({ questions: questions })
        });
        
        const data = await response.json();
        console.log('Réponse du serveur:', data);
        
        if (data.success) {
            if (statutEl && texteStatut) {
                statutEl.style.color = '#4CAF50';
                texteStatut.textContent = 'Sauvegardé';
                texteStatut.style.color = '#4CAF50';
            }
            
            const message = data.message || `${data.count || questions.length} question(s) enregistrée(s) avec succès`;
            if (data.notifications_envoyees && data.notifications_envoyees > 0) {
                afficherToast(`${message} - ${data.notifications_envoyees} étudiants notifiés`, 'success');
            } else {
                afficherToast(message, 'success');
            }
            
            console.log(`✅ Sauvegarde réussie: ${message}`);
        } else {
            console.log(`❌ Erreur sauvegarde: ${data.message}`);
            afficherToast(`Erreur : ${data.message}`, 'error');
            if (statutEl && texteStatut) {
                statutEl.style.color = '#f44336';
                texteStatut.textContent = 'Erreur de sauvegarde';
                texteStatut.style.color = '#f44336';
            }
        }
        
    } catch (error) {
        console.error('❌ Erreur lors de l\'enregistrement:', error);
        afficherToast('Erreur de connexion au serveur', 'error');
        
        const statutEl = document.getElementById('statut-enregistrement');
        const texteStatut = document.getElementById('texte-statut');
        if (statutEl && texteStatut) {
            statutEl.style.color = '#f44336';
            texteStatut.textContent = 'Erreur';
            texteStatut.style.color = '#f44336';
        }
    } finally {
        estSauvegardeEnCours = false;
        btnEnregistrer.innerHTML = iconOriginal;
    }
}

// ===== CHARGEMENT DES QUESTIONS EXISTANTES =====

// Charger les questions existantes depuis le serveur
async function chargerQuestionsExistantes() {
    return new Promise((resolve, reject) => {
        try {
            console.log(`📥 Chargement questions pour TP ${tpId}...`);
            fetch(`/api/tp/${tpId}/questions`)
                .then(response => response.json())
                .then(data => {
                    console.log('Réponse chargement questions:', data);
                    
                    if (data.success && data.questions && data.questions.length > 0) {
                        const etatVide = document.getElementById('etat-vide');
                        if (etatVide) etatVide.remove();
                        
                        const conteneur = document.getElementById('conteneur-questions');
                        conteneur.innerHTML = '';
                        
                        compteurQuestions = 0;
                        questionsData = {};
                        
                        console.log(`📊 ${data.questions.length} questions reçues`);
                        
                        const questionsTriees = data.questions.sort((a, b) => (a.ordre || 0) - (b.ordre || 0));
                        
                        for (const question of questionsTriees) {
                            compteurQuestions++;
                            const questionId = compteurQuestions;
                            
                            console.log(`\n📝 Chargement question ${questionId}:`);
                            console.log(`  Type: ${question.type_question}`);
                            console.log(`  Image URL: ${question.image_url || 'aucune'}`);
                            
                            const template = document.getElementById('template-question').innerHTML;
                            const html = template
                                .replace(/{id}/g, questionId)
                                .replace(/{numero}/g, question.ordre || compteurQuestions);
                            
                            const div = document.createElement('div');
                            div.innerHTML = html;
                            
                            const carte = div.firstElementChild;
                            
                            const zoneTexte = carte.querySelector('.zone-texte');
                            zoneTexte.value = question.texte || question.enonce || '';
                            
                            const selectType = carte.querySelector('.select-type');
                            
                            let typeFrontend = 'texte';
                            const typeQuestion = question.type_question || question.type;
                            
                            switch (typeQuestion) {
                                case 'qcm':
                                    typeFrontend = 'choix_multiple';
                                    break;
                                case 'ouverte':
                                    typeFrontend = 'texte';
                                    break;
                                case 'case_cocher':
                                    typeFrontend = 'case_cocher';
                                    break;
                                case 'image_reponse':
                                    typeFrontend = 'image_reponse';
                                    break;
                                case 'image_question':
                                    typeFrontend = 'image_question';
                                    break;
                            }
                            
                            selectType.value = typeFrontend;
                            
                            const inputPoints = carte.querySelector('.input-points');
                            inputPoints.value = question.points || 1.0;
                            
                            if (typeFrontend === 'choix_multiple' || typeFrontend === 'case_cocher') {
                                let options = [];
                                try {
                                    if (question.reponse_correcte && question.reponse_correcte !== '') {
                                        options = JSON.parse(question.reponse_correcte);
                                    } else {
                                        options = ['Option 1', 'Option 2'];
                                    }
                                } catch (e) {
                                    console.warn('Erreur parsing options:', e);
                                    options = ['Option 1', 'Option 2'];
                                }
                                
                                const listeOptions = carte.querySelector('.liste-options');
                                listeOptions.innerHTML = '';
                                
                                options.forEach((option, idx) => {
                                    const optionDiv = document.createElement('div');
                                    optionDiv.className = 'option-item';
                                    optionDiv.innerHTML = `
                                        <input type="text" class="input-option" placeholder="Option ${idx + 1}" value="${option}" oninput="mettreAJourStatut()">
                                        <button class="bouton-supprimer" style="width: 30px; height: 30px;" onclick="supprimerOption(${questionId}, this)">
                                            <i class="fas fa-times"></i>
                                        </button>
                                    `;
                                    listeOptions.appendChild(optionDiv);
                                });
                            }
                            
                            if (typeFrontend === 'image_question' && question.image_url) {
                                console.log(`  📷 Configuration image: ${question.image_url}`);
                                
                                const zoneUpload = carte.querySelector('.zone-upload-image');
                                if (zoneUpload) {
                                    zoneUpload.innerHTML = `
                                        <div class="titre-options">
                                            <i class="fas fa-image"></i> Image de la question
                                        </div>
                                        <div class="preview-image-container">
                                            <img id="preview-${questionId}" class="preview-image" 
                                                 src="${question.image_url}" 
                                                 alt="Image de la question"
                                                 style="display: block;">
                                            <div class="upload-controls">
                                                <label for="image-input-${questionId}" class="bouton-upload">
                                                    <i class="fas fa-cloud-upload-alt"></i>
                                                    Changer l'image
                                                </label>
                                                <input type="file" id="image-input-${questionId}" class="input-image" 
                                                       accept="image/*" style="display: none;" 
                                                       onchange="previewImage(${questionId}, this)">
                                                <button type="button" class="bouton-supprimer-image" onclick="supprimerImageQuestion(${questionId})">
                                                    <i class="fas fa-trash"></i>
                                                </button>
                                            </div>
                                            <div class="info-upload">
                                                <i class="fas fa-info-circle"></i>
                                                Formats acceptés: JPG, PNG, GIF, WEBP. Max: 5MB
                                            </div>
                                        </div>
                                    `;
                                    
                                    zoneUpload.style.display = 'block';
                                    
                                    const preview = document.getElementById(`preview-${questionId}`);
                                    if (preview && question.image_url) {
                                        preview.src = question.image_url;
                                        preview.style.display = 'block';
                                        console.log(`  ✅ Image affichée dans zone d'upload`);
                                    }
                                }
                            }
                            
                            selectType.onchange = function() { changerTypeQuestion(questionId); };
                            inputPoints.onchange = function() { mettreAJourProgression(); };
                            
                            const boutonAjouterOption = carte.querySelector('.bouton-ajouter-option');
                            if (boutonAjouterOption) {
                                boutonAjouterOption.onclick = function() { ajouterOption(questionId); };
                            }
                            
                            zoneTexte.oninput = function() { mettreAJourStatut(); };
                            
                            const zoneOptions = carte.querySelector('.zone-options');
                            const infoImage = carte.querySelector('.info-image');
                            const zoneUpload = carte.querySelector('.zone-upload-image');
                            
                            if (typeFrontend === 'choix_multiple' || typeFrontend === 'case_cocher') {
                                if (zoneOptions) zoneOptions.style.display = 'block';
                            } else {
                                if (zoneOptions) zoneOptions.style.display = 'none';
                            }
                            
                            if (typeFrontend === 'image_reponse') {
                                if (infoImage) infoImage.style.display = 'block';
                            } else {
                                if (infoImage) infoImage.style.display = 'none';
                            }
                            
                            if (typeFrontend === 'image_question' && zoneUpload) {
                                zoneUpload.style.display = 'block';
                            }
                            
                            conteneur.appendChild(carte);
                            
                            let optionsData = [];
                            if (typeFrontend === 'choix_multiple' || typeFrontend === 'case_cocher') {
                                try {
                                    if (question.reponse_correcte && question.reponse_correcte !== '') {
                                        optionsData = JSON.parse(question.reponse_correcte);
                                    }
                                } catch (e) {
                                    console.warn('Erreur parsing options:', e);
                                }
                            }
                            
                            questionsData[questionId] = {
                                id: question.id,
                                texte: question.texte || question.enonce || '',
                                type: typeFrontend,
                                points: question.points || 1.0,
                                options: optionsData,
                                imageUrl: question.image_url || null
                            };
                            
                            console.log(`  ✅ Question ${questionId} chargée`);
                        }
                        
                        mettreAJourProgression();
                        
                        const statutEl = document.getElementById('statut-enregistrement');
                        const texteStatut = document.getElementById('texte-statut');
                        if (statutEl && texteStatut) {
                            statutEl.style.color = '#4CAF50';
                            texteStatut.textContent = 'Sauvegardé';
                            texteStatut.style.color = '#4CAF50';
                        }
                        
                        console.log(`✅ ${data.questions.length} questions chargées avec succès`);
                        afficherToast(`${data.questions.length} question(s) chargée(s)`, 'success');
                        
                        resolve();
                    } else {
                        console.log('ℹ️  Aucune question existante');
                        resolve();
                    }
                })
                .catch(error => {
                    console.error('❌ Erreur lors du chargement des questions:', error);
                    afficherToast('Erreur lors du chargement des questions', 'error');
                    reject(error);
                });
                
        } catch (error) {
            console.error('❌ Erreur lors du chargement des questions:', error);
            afficherToast('Erreur lors du chargement des questions', 'error');
            reject(error);
        }
    });
}

// ===== FONCTIONS DE DÉBOGAGE =====

// Fonction de débogage pour vérifier toutes les images
function debugImages() {
    console.log("🔍 DÉBOGAGE DES IMAGES");
    console.log("=" .repeat(50));
    
    const cartesQuestions = document.querySelectorAll('.carte-question');
    console.log(`Nombre de questions: ${cartesQuestions.length}`);
    
    cartesQuestions.forEach(carte => {
        const id = carte.dataset.id;
        const type = carte.querySelector('.select-type').value;
        const zoneUpload = carte.querySelector('.zone-upload-image');
        const preview = document.getElementById(`preview-${id}`);
        
        console.log(`\nQuestion ${id}:`);
        console.log(`  Type: ${type}`);
        console.log(`  Zone upload: ${zoneUpload ? 'trouvée' : 'non trouvée'}`);
        console.log(`  Preview: ${preview ? 'trouvé' : 'non trouvé'}`);
        
        if (preview) {
            console.log(`  Source image: ${preview.src}`);
            console.log(`  Visible: ${preview.style.display !== 'none'}`);
        }
        
        console.log(`  Données image: ${questionsData[id]?.imageUrl || 'aucune'}`);
    });
    
    console.log("=" .repeat(50));
}

// ===== EXPORT DES FONCTIONS GLOBALES =====

window.initialiserGestionQuestions = initialiserGestionQuestions;
window.ajouterQuestion = ajouterQuestion;
window.changerTypeQuestion = changerTypeQuestion;
window.previewImage = previewImage;
window.supprimerImageQuestion = supprimerImageQuestion;
window.ajouterOption = ajouterOption;
window.supprimerOption = supprimerOption;
window.supprimerQuestion = supprimerQuestion;
window.enregistrerQuestions = enregistrerQuestions;
window.mettreAJourProgression = mettreAJourProgression;
window.mettreAJourStatut = mettreAJourStatut;
window.debugImages = debugImages;
window.initialiserZonesUpload = initialiserZonesUpload;