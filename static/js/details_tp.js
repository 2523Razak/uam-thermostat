/**
 * details_tp.js
 * Gestion des interactions sur la page des détails du TP
 * 
 * Fonctionnalités :
 * - Animation de la barre de progression
 * - Gestion des messages d'alerte (auto-fermeture + bouton fermeture)
 * - Ouverture des images dans un nouvel onglet
 * - Rafraîchissement automatique des statuts (optionnel)
 * - Gestion des erreurs de chargement d'images
 */

document.addEventListener('DOMContentLoaded', function() {
    
    // ===== 1. ANIMATION DE LA BARRE DE PROGRESSION =====
    animateProgressBar();
    
    // ===== 2. GESTION DES MESSAGES D'ALERTE =====
    initAlertMessages();
    
    // ===== 3. OUVERTURE DES IMAGES DANS NOUVEL ONGLET =====
    initImageLinks();
    
    // ===== 4. GESTION DES ERREURS D'IMAGES =====
    initImageErrorHandler();
    
    // ===== 5. RAFRAÎCHISSEMENT AUTOMATIQUE (optionnel) =====
    initAutoRefresh();
    
    // ===== 6. GESTION DU SCROLL DES QUESTIONS =====
    initQuestionScroll();
    
});

/**
 * Anime la barre de progression au chargement
 */
function animateProgressBar() {
    const progressFill = document.querySelector('.progress-fill');
    if (progressFill) {
        const targetWidth = progressFill.style.width;
        // Réinitialiser à 0
        progressFill.style.width = '0';
        // Animer vers la largeur cible
        setTimeout(() => {
            progressFill.style.width = targetWidth;
        }, 100);
    }
}

/**
 * Initialise les messages d'alerte avec auto-fermeture et bouton de fermeture
 */
function initAlertMessages() {
    const alerts = document.querySelectorAll('.message-alerte');
    
    alerts.forEach(alert => {
        // Ajouter un bouton de fermeture
        const closeBtn = document.createElement('span');
        closeBtn.className = 'alert-close';
        closeBtn.innerHTML = '&times;';
        closeBtn.setAttribute('aria-label', 'Fermer');
        closeBtn.style.cssText = `
            float: right;
            cursor: pointer;
            font-size: 1.2rem;
            font-weight: bold;
            margin-left: 15px;
            color: inherit;
            opacity: 0.7;
            transition: opacity 0.2s ease;
        `;
        
        // Effet hover sur le bouton
        closeBtn.addEventListener('mouseenter', () => {
            closeBtn.style.opacity = '1';
        });
        closeBtn.addEventListener('mouseleave', () => {
            closeBtn.style.opacity = '0.7';
        });
        
        // Fermeture au clic
        closeBtn.onclick = function(e) {
            e.stopPropagation();
            alert.style.transition = 'opacity 0.3s ease';
            alert.style.opacity = '0';
            setTimeout(() => {
                if (alert && alert.parentNode) {
                    alert.remove();
                }
            }, 300);
        };
        
        // Ajouter le bouton si l'alerte n'en a pas déjà un
        if (!alert.querySelector('.alert-close')) {
            // Vérifier si l'alerte a une structure avec div
            const alertContent = alert.querySelector('div');
            if (alertContent) {
                alertContent.style.display = 'flex';
                alertContent.style.alignItems = 'center';
                alertContent.style.justifyContent = 'space-between';
                alertContent.style.width = '100%';
                alertContent.appendChild(closeBtn);
            } else {
                // Sinon, ajouter directement à l'alerte
                const textContent = alert.innerHTML;
                alert.innerHTML = `
                    <div style="display: flex; align-items: center; justify-content: space-between; width: 100%;">
                        <span>${textContent}</span>
                    </div>
                `;
                alert.querySelector('div').appendChild(closeBtn);
            }
        }
        
        // Auto-fermeture après 5 secondes pour les messages de succès et d'info
        if (alert.classList.contains('message-success') || alert.classList.contains('message-info')) {
            setTimeout(() => {
                if (alert && alert.parentNode) {
                    alert.style.transition = 'opacity 0.3s ease';
                    alert.style.opacity = '0';
                    setTimeout(() => {
                        if (alert && alert.parentNode) {
                            alert.remove();
                        }
                    }, 300);
                }
            }, 5000);
        }
    });
}

/**
 * Initialise les liens d'images pour ouvrir dans un nouvel onglet
 */
function initImageLinks() {
    // Sélectionner tous les conteneurs d'images
    const imageContainers = document.querySelectorAll('.image-container');
    
    imageContainers.forEach(container => {
        // Chercher les images dans le conteneur
        const img = container.querySelector('img');
        if (img && img.src) {
            // Vérifier si l'image est déjà dans un lien
            let parentLink = container.querySelector('a.image-link');
            
            if (!parentLink) {
                // Créer un lien autour de l'image
                const link = document.createElement('a');
                link.href = img.src;
                link.target = '_blank';
                link.rel = 'noopener noreferrer';
                link.className = 'image-link';
                link.setAttribute('title', 'Cliquez pour voir l\'image en grand');
                
                // Remplacer l'image par le lien contenant l'image
                img.parentNode.insertBefore(link, img);
                link.appendChild(img);
                
                // Ajouter l'icône d'agrandissement
                const zoomIcon = document.createElement('span');
                zoomIcon.className = 'image-zoom-icon';
                zoomIcon.innerHTML = '<i class="fas fa-search-plus"></i> Agrandir';
                link.appendChild(zoomIcon);
            }
        }
    });
    
    // Ajouter un effet de survol élégant
    const style = document.createElement('style');
    style.textContent = `
        .image-link {
            display: inline-block;
            position: relative;
            text-decoration: none;
            cursor: pointer;
        }
        .image-link:hover img {
            opacity: 0.95;
            transform: scale(1.01);
            transition: all 0.2s ease;
        }
        .image-zoom-icon {
            position: absolute;
            bottom: 10px;
            right: 10px;
            background: rgba(0, 0, 0, 0.7);
            color: white;
            padding: 5px 10px;
            border-radius: 20px;
            font-size: 0.75rem;
            display: flex;
            align-items: center;
            gap: 5px;
            opacity: 0;
            transition: opacity 0.2s ease;
            pointer-events: none;
            font-family: 'Poppins', sans-serif;
        }
        .image-link:hover .image-zoom-icon {
            opacity: 1;
        }
        .image-zoom-icon i {
            font-size: 0.7rem;
        }
    `;
    document.head.appendChild(style);
    
    // Logger le nombre d'images trouvées
    const totalImages = document.querySelectorAll('.image-container img').length;
    if (totalImages > 0) {
        console.log(`🔍 ${totalImages} image(s) trouvée(s) - clic pour agrandir dans un nouvel onglet`);
    }
}

/**
 * Gère les erreurs de chargement des images
 * Affiche un message personnalisé quand une image ne peut pas être chargée
 */
function initImageErrorHandler() {
    const images = document.querySelectorAll('.question-image, .reponse-image');
    
    images.forEach(img => {
        img.addEventListener('error', function() {
            // Éviter les boucles infinies
            if (this.hasAttribute('data-error-handled')) {
                return;
            }
            this.setAttribute('data-error-handled', 'true');
            
            // Créer un message d'erreur
            const errorDiv = document.createElement('div');
            errorDiv.className = 'image-error-message';
            errorDiv.innerHTML = `
                <i class="fas fa-exclamation-triangle"></i>
                <span>Image non disponible</span>
                <small>${this.alt || 'Fichier introuvable'}</small>
            `;
            errorDiv.style.cssText = `
                padding: 15px;
                background: #f8d7da;
                color: #721c24;
                border-radius: 6px;
                text-align: center;
                margin: 10px 0;
                display: flex;
                flex-direction: column;
                gap: 5px;
                align-items: center;
            `;
            
            // Cacher l'image et afficher l'erreur
            this.style.display = 'none';
            this.parentElement.appendChild(errorDiv);
            
            // Logger l'erreur
            console.error(`❌ Image non chargée: ${this.src}`);
        });
        
        // Logger les succès
        img.addEventListener('load', function() {
            console.log(`✅ Image chargée: ${this.src.substring(this.src.lastIndexOf('/') + 1)}`);
        });
    });
}

/**
 * Initialise le rafraîchissement automatique des statuts
 * Met à jour les informations sans recharger la page
 */
function initAutoRefresh() {
    // Récupérer l'ID du TP depuis l'URL
    const tpId = getTpIdFromUrl();
    
    if (!tpId) {
        console.log('📌 Auto-refresh désactivé: ID du TP non trouvé');
        return;
    }
    
    let refreshInterval = null;
    let isPageVisible = true;
    
    // Détecter quand la page est visible ou cachée
    document.addEventListener('visibilitychange', function() {
        isPageVisible = !document.hidden;
        
        if (isPageVisible) {
            // Page visible : redémarrer le rafraîchissement
            if (!refreshInterval) {
                refreshInterval = setInterval(() => {
                    refreshTpStatus(tpId);
                }, 60000); // Toutes les 60 secondes
                console.log('🔄 Auto-refresh activé');
            }
        } else {
            // Page cachée : arrêter le rafraîchissement
            if (refreshInterval) {
                clearInterval(refreshInterval);
                refreshInterval = null;
                console.log('⏸️ Auto-refresh mis en pause');
            }
        }
    });
    
    // Démarrer le rafraîchissement
    refreshInterval = setInterval(() => {
        if (isPageVisible) {
            refreshTpStatus(tpId);
        }
    }, 60000);
    
    console.log('🔄 Auto-refresh configuré (toutes les 60 secondes)');
}

/**
 * Extrait l'ID du TP depuis l'URL
 * @returns {number|null} L'ID du TP ou null si non trouvé
 */
function getTpIdFromUrl() {
    const urlParts = window.location.pathname.split('/');
    const tpIndex = urlParts.findIndex(part => part === 'details_tp');
    
    if (tpIndex !== -1 && urlParts[tpIndex + 1]) {
        const tpId = parseInt(urlParts[tpIndex + 1]);
        if (!isNaN(tpId)) {
            return tpId;
        }
    }
    return null;
}

/**
 * Rafraîchit le statut du TP via API
 * @param {number} tpId - L'ID du TP
 */
async function refreshTpStatus(tpId) {
    try {
        const response = await fetch(`/api/tp/${tpId}/statut`);
        
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }
        
        const data = await response.json();
        
        if (data.success) {
            // Mettre à jour l'affichage du statut
            const statutBadge = document.querySelector('.statut-badge');
            if (statutBadge && data.statut) {
                updateStatutBadge(statutBadge, data.statut);
            }
            
            // Mettre à jour le statut de progression si disponible
            if (data.progress !== undefined) {
                const progressFill = document.querySelector('.progress-fill');
                if (progressFill) {
                    progressFill.style.width = `${data.progress}%`;
                }
                
                const statNumber = document.querySelector('.stat-number');
                if (statNumber && data.reponses_count !== undefined) {
                    statNumber.textContent = `${data.reponses_count}/${data.questions_count}`;
                }
                
                const statPercent = document.querySelector('.stat-percent');
                if (statPercent && data.progress !== undefined) {
                    statPercent.textContent = `${Math.round(data.progress)}%`;
                }
            }
            
            console.log('📊 Statut mis à jour:', data.statut);
        }
    } catch (error) {
        // Silencieux pour ne pas surcharger la console
        console.debug('Auto-refresh:', error.message);
    }
}

/**
 * Met à jour l'affichage du badge de statut
 * @param {HTMLElement} badge - L'élément badge
 * @param {string} statut - Le nouveau statut
 */
function updateStatutBadge(badge, statut) {
    // Sauvegarder l'icône et le texte actuels
    const icon = badge.querySelector('i');
    const textSpan = badge.childNodes[1];
    
    // Supprimer les classes existantes
    badge.classList.remove('statut-disponible', 'statut-en_cours', 'statut-soumis', 'statut-expire');
    
    // Ajouter la nouvelle classe
    badge.classList.add(`statut-${statut}`);
    
    // Mettre à jour le texte et l'icône
    switch(statut) {
        case 'disponible':
            if (icon) icon.className = 'fas fa-play-circle';
            if (textSpan) textSpan.textContent = ' Disponible';
            break;
        case 'en_cours':
            if (icon) icon.className = 'fas fa-clock';
            if (textSpan) textSpan.textContent = ' En cours';
            break;
        case 'soumis':
            if (icon) icon.className = 'fas fa-check-circle';
            if (textSpan) textSpan.textContent = ' Soumis';
            break;
        case 'expire':
            if (icon) icon.className = 'fas fa-ban';
            if (textSpan) textSpan.textContent = ' Expiré';
            break;
        default:
            console.warn(`Statut inconnu: ${statut}`);
    }
}

/**
 * Initialise le défilement vers les questions non répondues
 * Et le survol des questions
 */
function initQuestionScroll() {
    // Mettre en évidence les questions non répondues
    const unrepliedQuestions = document.querySelectorAll('.question-item.non-repondu');
    
    if (unrepliedQuestions.length > 0 && unrepliedQuestions.length <= 3) {
        // Ajouter une indication visuelle
        const statsElement = document.querySelector('.progress-status p');
        if (statsElement) {
            const remainingText = document.createElement('small');
            remainingText.style.display = 'block';
            remainingText.style.marginTop = '10px';
            remainingText.style.fontSize = '0.85rem';
            remainingText.innerHTML = `<i class="fas fa-exclamation-circle"></i> ${unrepliedQuestions.length} question(s) sans réponse`;
            statsElement.appendChild(remainingText);
        }
    }
    
    // Ajouter un effet de survol sur les questions
    const questions = document.querySelectorAll('.question-item');
    questions.forEach(question => {
        question.addEventListener('mouseenter', function() {
            this.style.transform = 'translateX(5px)';
            this.style.transition = 'transform 0.2s ease';
        });
        
        question.addEventListener('mouseleave', function() {
            this.style.transform = 'translateX(0)';
        });
    });
}

/**
 * Exporte les fonctions pour d'éventuels usages externes
 */
if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        animateProgressBar,
        initAlertMessages,
        initImageLinks,
        initImageErrorHandler,
        initAutoRefresh,
        getTpIdFromUrl,
        refreshTpStatus,
        updateStatutBadge,
        initQuestionScroll
    };
}