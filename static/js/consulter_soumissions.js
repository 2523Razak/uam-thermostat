// ============================================================================
// VARIABLES GLOBALES
// ============================================================================

let soumissionsData = [];
let soumissionsFiltrees = [];
let currentPage = 1;
let itemsPerPage = 10;
let currentSort = { field: 'date_soumission', direction: 'desc' };
let currentFilters = {};
let selectedSubmission = null;
let lastUpdateHash = '';
let isRealtimeActive = true;

// ============================================================================
// INITIALISATION
// ============================================================================

document.addEventListener('DOMContentLoaded', function() {
    console.log("✅ Page consulter_soumissions.js chargée");
    
    // Vérifier la connexion
    verifierConnexion();
    
    // Charger les données initiales
    chargerSoumissions();
    
    // Configurer les événements
    configurerEvenements();
    
    // Configurer les filtres
    configurerFiltres();
    
    // Démarrer les mises à jour en temps réel
    demarrerMisesAJourTempsReel();
    
    // Configurer les événements du modal de correction
    configurerModalCorrection();
});

// ============================================================================
// FONCTIONS DE GESTION DES DONNÉES
// ============================================================================

// Vérifier si l'utilisateur est connecté
function verifierConnexion() {
    fetch('/api/debug_connexions')
        .then(response => response.json())
        .then(data => {
            console.log("🔐 État connexion:", data);
            if (data.error && data.error.includes('non connecté')) {
                afficherToast('Veuillez vous connecter', 'error');
                setTimeout(() => {
                    window.location.href = '/connections';
                }, 2000);
            }
        })
        .catch(error => {
            console.error("❌ Erreur vérification connexion:", error);
        });
}

// Démarrer les mises à jour en temps réel
function demarrerMisesAJourTempsReel() {
    // Vérifier les mises à jour toutes les 10 secondes
    setInterval(() => {
        if (isRealtimeActive) {
            verifierMisesAJour();
        }
    }, 10000);
}

// Vérifier les mises à jour
async function verifierMisesAJour() {
    try {
        console.log("🔄 Vérification des mises à jour...");
        const response = await fetch(`/api/soumissions/stats`);
        
        if (!response.ok) {
            console.warn("⚠️ Erreur lors de la vérification des stats");
            return;
        }
        
        const data = await response.json();
        
        if (data.success) {
            const currentHash = JSON.stringify(data.stats);
            
            // Vérifier si les données ont changé
            if (currentHash !== lastUpdateHash) {
                console.log("📈 Mise à jour détectée");
                lastUpdateHash = currentHash;
                
                // Mettre à jour les statistiques sans recharger tout le tableau
                mettreAJourStats(data.stats);
                mettreAJourCartesStats(data.stats);
                
                // Recharger les données silencieusement
                rechargerDonneesSilencieusement();
            }
        }
    } catch (error) {
        console.warn("⚠️ Erreur vérification mises à jour:", error);
    }
}

// Recharger les données silencieusement
async function rechargerDonneesSilencieusement() {
    try {
        const params = new URLSearchParams();
        params.append('page', currentPage);
        params.append('per_page', itemsPerPage);
        
        Object.keys(currentFilters).forEach(key => {
            if (currentFilters[key] && currentFilters[key] !== 'all') {
                params.append(key, currentFilters[key]);
            }
        });
        
        params.append('sort', currentSort.field);
        params.append('order', currentSort.direction);
        
        const response = await fetch(`/api/soumissions?${params}`);
        const data = await response.json();
        
        if (data.success) {
            soumissionsData = data.soumissions;
            soumissionsFiltrees = soumissionsData;
            
            // Mettre à jour le tableau avec animation
            mettreAJourTableauAvecAnimation();
            mettreAJourPagination(data.pagination);
            
            // Mettre à jour le compteur
            document.getElementById('compteur-soumissions').textContent = `${data.pagination.total} résultats`;
            
            // Mettre à jour le sous-titre
            mettreAJourSousTitre();
        }
    } catch (error) {
        console.warn("⚠️ Erreur rechargement silencieux:", error);
    }
}

// Charger les soumissions depuis le serveur
async function chargerSoumissions() {
    try {
        console.log("📥 Chargement des soumissions...");
        afficherChargement(true);
        
        // Construire les paramètres de requête
        const params = new URLSearchParams();
        params.append('page', currentPage);
        params.append('per_page', itemsPerPage);
        
        // Ajouter les filtres
        Object.keys(currentFilters).forEach(key => {
            if (currentFilters[key] && currentFilters[key] !== 'all') {
                params.append(key, currentFilters[key]);
            }
        });
        
        // Ajouter le tri
        params.append('sort', currentSort.field);
        params.append('order', currentSort.direction);
        
        console.log("📋 Paramètres de requête:", params.toString());
        
        const response = await fetch(`/api/soumissions?${params}`);
        
        if (!response.ok) {
            throw new Error(`Erreur HTTP ${response.status}`);
        }
        
        const data = await response.json();
        console.log("📦 Données reçues:", data);
        
        if (data.success) {
            soumissionsData = data.soumissions;
            soumissionsFiltrees = soumissionsData;
            
            // Mettre à jour le hash pour le suivi des changements
            lastUpdateHash = JSON.stringify(data.stats);
            
            // Mettre à jour l'interface
            mettreAJourTableau();
            mettreAJourPagination(data.pagination);
            mettreAJourStats(data.stats);
            mettreAJourCartesStats(data.stats);
            
            // Mettre à jour les statistiques globales
            document.getElementById('compteur-soumissions').textContent = `${data.pagination.total} résultats`;
            
            // Mettre à jour le sous-titre
            mettreAJourSousTitre();
            
            console.log(`✅ ${soumissionsData.length} soumissions chargées`);
        } else {
            afficherToast('Erreur lors du chargement des soumissions', 'error');
        }
    } catch (error) {
        console.error("❌ Erreur chargement soumissions:", error);
        afficherToast('Erreur de connexion au serveur', 'error');
    } finally {
        afficherChargement(false);
    }
}

// ============================================================================
// FONCTIONS D'AFFICHAGE
// ============================================================================

// Mettre à jour le sous-titre
function mettreAJourSousTitre() {
    let sousTitre = '';
    if (currentFilters.tp_id && currentFilters.tp_id !== 'all') {
        sousTitre += `TP filtré | `;
    }
    if (currentFilters.statut && currentFilters.statut !== 'all') {
        sousTitre += `Statut: ${getStatutLabel(currentFilters.statut)} | `;
    }
    if (currentFilters.search) {
        sousTitre += `Recherche: "${currentFilters.search}" | `;
    }
    if (currentFilters.date) {
        sousTitre += `Date: ${currentFilters.date} | `;
    }
    sousTitre += `Tri: ${getSortLabel(currentSort.field)} ${currentSort.direction === 'asc' ? '↑' : '↓'}`;
    
    const element = document.getElementById('sous-titre-filtres');
    if (element) {
        element.textContent = sousTitre;
    }
}

// Mettre à jour le tableau avec animation
function mettreAJourTableauAvecAnimation() {
    const tbody = document.getElementById('tableau-body');
    if (!tbody) return;
    
    // Supprimer les anciennes animations
    tbody.querySelectorAll('.row-updated').forEach(row => {
        row.classList.remove('row-updated');
    });
    
    mettreAJourTableau();
    
    // Ajouter l'animation aux nouvelles lignes
    setTimeout(() => {
        tbody.querySelectorAll('tr').forEach(row => {
            row.classList.add('row-updated');
            setTimeout(() => {
                row.classList.remove('row-updated');
            }, 1000);
        });
    }, 100);
}

// Mettre à jour le tableau
function mettreAJourTableau() {
    const tbody = document.getElementById('tableau-body');
    if (!tbody) return;
    
    tbody.innerHTML = '';
    
    if (soumissionsFiltrees.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="9" style="text-align: center; padding: 40px;">
                    <i class="fas fa-inbox fa-2x" style="color: #adb5bd; margin-bottom: 15px;"></i>
                    <p>Aucune soumission trouvée</p>
                    <p class="small-text">Essayez de modifier vos filtres</p>
                </td>
            </tr>
        `;
        return;
    }
    
    soumissionsFiltrees.forEach(soumission => {
        const tr = document.createElement('tr');
        tr.dataset.id = soumission.id;
        tr.dataset.tpId = soumission.tp_id;
        tr.dataset.etudiantId = soumission.etudiant_id;
        
        // Formater la date de soumission
        const dateSoumission = soumission.date_soumission ? 
            formaterDate(soumission.date_soumission) : 'Non soumis';
        
        // Calculer la dernière activité
        const derniereActivite = soumission.date_soumission ? 
            calculerDerniereActivite(soumission.date_soumission) : 'Jamais';
        
        // Note obtenue / Note maximale possible
        let noteDisplay = '-';
        let noteClass = '';
        
        if (soumission.note_valeur !== null && soumission.questions_count > 0) {
            const noteMaxPossible = soumission.note_max || (soumission.questions_count * 20);
            const notePourcentage = (soumission.note_valeur / noteMaxPossible) * 100;
            
            noteDisplay = `${soumission.note_valeur.toFixed(1)}/${noteMaxPossible.toFixed(1)}`;
            
            if (notePourcentage >= 70) noteClass = 'note-excellente';
            else if (notePourcentage >= 50) noteClass = 'note-moyenne';
            else noteClass = 'note-faible';
        }
        
        // Calculer le pourcentage de progression
        let progressionPourcentage = 0;
        let progressionText = '0%';
        
        if (soumission.questions_count > 0) {
            progressionPourcentage = Math.round((soumission.reponses_count / soumission.questions_count) * 100);
            progressionText = `${progressionPourcentage}%`;
        } else {
            progressionText = soumission.progression || '0%';
            const match = progressionText.match(/(\d+)%/);
            progressionPourcentage = match ? parseInt(match[1]) : 0;
        }
        
        tr.innerHTML = `
            <td>
                <div class="etudiant-info ${soumission.etudiant_supprime ? 'etudiant-supprime' : ''}">
                    <strong>${soumission.etudiant_nom} ${soumission.etudiant_prenom}</strong>
                    ${soumission.etudiant_supprime 
                        ? '<span class="badge-compte-supprime">Compte supprimé</span>' 
                        : `<div class="small-text">${soumission.etudiant_matricule}</div>`}
                </div>
            </td>
            <td>
                <div class="tp-info">
                    <strong>${soumission.tp_titre}</strong>
                    ${soumission.tp_module ? `<div class="small-text">${soumission.tp_module}</div>` : ''}
                </div>
            </td>
            <td>${soumission.tp_module || '-'}</td>
            <td>
                <span class="statut-badge statut-${soumission.statut}">
                    ${getStatutLabel(soumission.statut)}
                </span>
            </td>
            <td>
                <div class="progression-barre-amelioree ${soumission.statut === 'en_cours' ? 'progression-en-cours' : ''}">
                    <div class="progression-remplissage-amelioree" style="width: ${progressionPourcentage}%">
                        <span class="progression-pourcentage">${progressionPourcentage}%</span>
                    </div>
                </div>
                <div class="progression-texte-amelioree">${progressionText}</div>
                <div class="small-text">${soumission.reponses_count || 0}/${soumission.questions_count || 0} questions</div>
            </td>
            <td>
                <div class="date-soumission">${dateSoumission}</div>
                ${soumission.duree ? `<div class="small-text">${soumission.duree}</div>` : ''}
            </td>
            <td>
                ${derniereActivite}
                ${soumission.statut === 'en_cours' ? '<div class="small-text">En progression</div>' : ''}
            </td>
            <td class="note-cell ${noteClass}">
                ${noteDisplay}
            </td>
            <td>
                <div class="actions-cell">
                    <button class="action-btn voir" title="Voir les détails" onclick="voirDetails(${soumission.tp_id}, ${soumission.etudiant_id}, event)">
                        <i class="fas fa-eye"></i>
                    </button>
                    <button class="action-btn corriger" title="Corriger" onclick="ouvrirCorrectionDirect(${soumission.tp_id}, ${soumission.etudiant_id}, event)">
                        <i class="fas fa-edit"></i>
                    </button>
                    <button class="action-btn exporter" title="Exporter" onclick="exporterSoumission(${soumission.tp_id}, ${soumission.etudiant_id}, event)">
                        <i class="fas fa-download"></i>
                    </button>
                </div>
            </td>
        `;
        
        // Ajouter un gestionnaire d'événement pour la ligne entière
        tr.addEventListener('click', function(e) {
            if (!e.target.closest('.actions-cell')) {
                voirDetails(soumission.tp_id, soumission.etudiant_id, e);
            }
        });
        
        tbody.appendChild(tr);
    });
}

// Mettre à jour la pagination
function mettreAJourPagination(pagination) {
    const container = document.getElementById('pagination');
    if (!container || !pagination) return;
    
    container.innerHTML = '';
    
    const totalPages = pagination.total_pages;
    if (totalPages <= 1) return;
    
    // Bouton précédent
    const prevBtn = document.createElement('button');
    prevBtn.className = 'page-btn';
    prevBtn.innerHTML = '<i class="fas fa-chevron-left"></i>';
    prevBtn.disabled = currentPage === 1;
    prevBtn.onclick = () => changerPage(currentPage - 1);
    container.appendChild(prevBtn);
    
    // Pages numérotées
    const maxPagesToShow = 5;
    let startPage = Math.max(1, currentPage - Math.floor(maxPagesToShow / 2));
    let endPage = Math.min(totalPages, startPage + maxPagesToShow - 1);
    
    if (endPage - startPage + 1 < maxPagesToShow) {
        startPage = Math.max(1, endPage - maxPagesToShow + 1);
    }
    
    // Première page
    if (startPage > 1) {
        const firstBtn = document.createElement('button');
        firstBtn.className = 'page-btn';
        firstBtn.textContent = '1';
        firstBtn.onclick = () => changerPage(1);
        container.appendChild(firstBtn);
        
        if (startPage > 2) {
            const ellipsis = document.createElement('span');
            ellipsis.className = 'page-ellipsis';
            ellipsis.textContent = '...';
            container.appendChild(ellipsis);
        }
    }
    
    // Pages
    for (let i = startPage; i <= endPage; i++) {
        const pageBtn = document.createElement('button');
        pageBtn.className = 'page-btn';
        pageBtn.textContent = i;
        if (i === currentPage) {
            pageBtn.classList.add('active');
        }
        pageBtn.onclick = () => changerPage(i);
        container.appendChild(pageBtn);
    }
    
    // Dernière page
    if (endPage < totalPages) {
        if (endPage < totalPages - 1) {
            const ellipsis = document.createElement('span');
            ellipsis.className = 'page-ellipsis';
            ellipsis.textContent = '...';
            container.appendChild(ellipsis);
        }
        
        const lastBtn = document.createElement('button');
        lastBtn.className = 'page-btn';
        lastBtn.textContent = totalPages;
        lastBtn.onclick = () => changerPage(totalPages);
        container.appendChild(lastBtn);
    }
    
    // Bouton suivant
    const nextBtn = document.createElement('button');
    nextBtn.className = 'page-btn';
    nextBtn.innerHTML = '<i class="fas fa-chevron-right"></i>';
    nextBtn.disabled = currentPage === totalPages;
    nextBtn.onclick = () => changerPage(currentPage + 1);
    container.appendChild(nextBtn);
    
    // Info de pagination
    const pageInfo = document.createElement('span');
    pageInfo.className = 'page-info';
    pageInfo.textContent = `${pagination.total} résultats • Page ${currentPage} sur ${totalPages}`;
    container.appendChild(pageInfo);
}

// Changer de page
function changerPage(page) {
    if (page < 1 || page > Math.ceil(soumissionsFiltrees.length / itemsPerPage)) return;
    currentPage = page;
    chargerSoumissions();
}

// Mettre à jour les statistiques
function mettreAJourStats(stats) {
    const elements = {
        'stat-tps': document.getElementById('stat-tps'),
        'stat-etudiants': document.getElementById('stat-etudiants'),
        'stat-soumis': document.getElementById('stat-soumis'),
        'stat-moyenne': document.getElementById('stat-moyenne'),
        'stat-en-cours': document.getElementById('stat-en-cours')
    };
    
    Object.keys(elements).forEach(key => {
        if (elements[key]) {
            const value = stats[key.replace('stat-', '')] || 0;
            if (key === 'stat-moyenne' && typeof value === 'number') {
                elements[key].textContent = value.toFixed(1);
            } else {
                elements[key].textContent = value;
            }
        }
    });
}

// Mettre à jour les cartes de statistiques
function mettreAJourCartesStats(stats) {
    const container = document.getElementById('cartes-stats');
    if (!container) return;
    
    const totalSoumissions = (stats.soumis || 0) + (stats.en_cours || 0) + (stats.non_commence || 0);
    const tauxCompletion = totalSoumissions > 0 ? Math.round((stats.soumis / totalSoumissions) * 100) : 0;
    const tauxProgression = totalSoumissions > 0 ? Math.round(((stats.soumis + stats.en_cours) / totalSoumissions) * 100) : 0;
    
    container.innerHTML = `
        <div class="carte-stat">
            <div class="carte-stat-header">
                <h3 class="carte-stat-titre">Soumissions complètes</h3>
                <i class="fas fa-check-circle carte-stat-icon"></i>
            </div>
            <div class="carte-stat-valeur">${stats.soumis || 0}</div>
            <div class="carte-stat-evolution">
                <i class="fas fa-chart-line"></i>
                <span>${tauxCompletion}% du total</span>
            </div>
        </div>
        
        <div class="carte-stat">
            <div class="carte-stat-header">
                <h3 class="carte-stat-titre">En progression</h3>
                <i class="fas fa-spinner carte-stat-icon"></i>
            </div>
            <div class="carte-stat-valeur">${stats.en_cours || 0}</div>
            <div class="carte-stat-evolution">
                <i class="fas fa-chart-line"></i>
                <span>${tauxProgression}% en activité</span>
            </div>
        </div>
        
        <div class="carte-stat">
            <div class="carte-stat-header">
                <h3 class="carte-stat-titre">Moyenne générale</h3>
                <i class="fas fa-chart-bar carte-stat-icon"></i>
            </div>
            <div class="carte-stat-valeur">${stats.moyenne_notes ? stats.moyenne_notes.toFixed(1) : '0.0'}/20</div>
            <div class="carte-stat-evolution">
                <i class="fas fa-star"></i>
                <span>Sur ${stats.soumis || 0} soumissions notées</span>
            </div>
        </div>
        
        <div class="carte-stat">
            <div class="carte-stat-header">
                <h3 class="carte-stat-titre">Dernière activité</h3>
                <i class="fas fa-clock carte-stat-icon"></i>
            </div>
            <div class="carte-stat-valeur">${formaterDateRelative(getRecentActivityDate())}</div>
            <div class="carte-stat-evolution">
                <i class="fas fa-user-clock"></i>
                <span>Activité récente</span>
            </div>
        </div>
    `;
}

// ============================================================================
// FONCTIONS D'ÉVÉNEMENTS
// ============================================================================

// Configurer les événements
function configurerEvenements() {
    console.log("⚙️ Configuration des événements...");
    
    // Tri des colonnes
    document.querySelectorAll('th[data-sort]').forEach(th => {
        th.addEventListener('click', function() {
            const field = this.dataset.sort;
            if (currentSort.field === field) {
                currentSort.direction = currentSort.direction === 'asc' ? 'desc' : 'asc';
            } else {
                currentSort.field = field;
                currentSort.direction = 'asc';
            }
            
            // Mettre à jour les icônes de tri
            document.querySelectorAll('th i').forEach(icon => {
                icon.className = 'fas fa-sort';
            });
            
            const icon = this.querySelector('i');
            if (icon) {
                icon.className = currentSort.direction === 'asc' ? 'fas fa-sort-up' : 'fas fa-sort-down';
            }
            
            currentPage = 1;
            chargerSoumissions();
        });
    });
    
    // Fermer le modal
    const modalFermer = document.getElementById('modal-fermer');
    if (modalFermer) {
        modalFermer.addEventListener('click', fermerModalDetails);
    }
    
    const modalCorrectionFermer = document.getElementById('modal-correction-fermer');
    if (modalCorrectionFermer) {
        modalCorrectionFermer.addEventListener('click', fermerModalCorrection);
    }
    
    // Fermer le modal en cliquant à l'extérieur
    const modalDetails = document.getElementById('modal-details');
    if (modalDetails) {
        modalDetails.addEventListener('click', function(e) {
            if (e.target === this) {
                fermerModalDetails();
            }
        });
    }
    
    const modalCorrection = document.getElementById('modal-correction');
    if (modalCorrection) {
        modalCorrection.addEventListener('click', function(e) {
            if (e.target === this) {
                fermerModalCorrection();
            }
        });
    }
    
    // Actualiser les données
    const actualiserDonnees = document.getElementById('actualiser-donnees');
    if (actualiserDonnees) {
        actualiserDonnees.addEventListener('click', function() {
            console.log("🔄 Actualisation manuelle...");
            chargerSoumissions();
        });
    }
    
    // Exporter les données
    const exporterDonnees = document.getElementById('exporter-donnees');
    if (exporterDonnees) {
        exporterDonnees.addEventListener('click', function() {
            // Vérifier qu'un TP est sélectionné
            const tpId = document.getElementById('filtre-tp')?.value || 'all';
            
            if (tpId === 'all') {
                afficherToast('Veuillez d\'abord sélectionner un TP spécifique dans les filtres', 'error');
                
                // Ouvrir automatiquement les filtres
                const filtresBody = document.getElementById('filtres-body');
                const toggleFiltres = document.getElementById('toggle-filtres');
                if (filtresBody && filtresBody.style.display === 'none') {
                    filtresBody.style.display = 'block';
                    if (toggleFiltres) {
                        toggleFiltres.innerHTML = '<i class="fas fa-sliders-h"></i> Masquer';
                    }
                }
                
                // Mettre le focus sur le sélecteur de TP
                const filtreTp = document.getElementById('filtre-tp');
                if (filtreTp) {
                    filtreTp.focus();
                }
                
                return;
            }
            
            exporterDonneesCSV();
        });
    }
    
    // Écouter les touches pour fermer les modals
    document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape') {
            if (document.getElementById('modal-details').style.display === 'flex') {
                fermerModalDetails();
            }
            if (document.getElementById('modal-correction').style.display === 'flex') {
                fermerModalCorrection();
            }
            if (document.getElementById('image-modal-overlay') && document.getElementById('image-modal-overlay').style.display === 'flex') {
                closeImageModal();
            }
        }
    });
}

// Configurer les filtres
function configurerFiltres() {
    console.log("⚙️ Configuration des filtres...");
    
    // Toggle des filtres
    const toggleFiltres = document.getElementById('toggle-filtres');
    if (toggleFiltres) {
        toggleFiltres.addEventListener('click', function() {
            const body = document.getElementById('filtres-body');
            if (body) {
                if (body.style.display === 'none' || body.style.display === '') {
                    body.style.display = 'block';
                    this.innerHTML = '<i class="fas fa-sliders-h"></i> Masquer';
                } else {
                    body.style.display = 'none';
                    this.innerHTML = '<i class="fas fa-sliders-h"></i> Afficher';
                }
            }
        });
    }
    
    // Appliquer les filtres
    const appliquerFiltres = document.getElementById('appliquer-filtres');
    if (appliquerFiltres) {
        appliquerFiltres.addEventListener('click', appliquerFiltresHandler);
    }
    
    // Réinitialiser les filtres
    const reinitialiserFiltres = document.getElementById('reinitialiser-filtres');
    if (reinitialiserFiltres) {
        reinitialiserFiltres.addEventListener('click', reinitialiserFiltresHandler);
    }
    
    // Filtrer en temps réel
    const filtreTp = document.getElementById('filtre-tp');
    if (filtreTp) {
        filtreTp.addEventListener('change', function() {
            currentFilters.tp_id = this.value;
            currentPage = 1;
            chargerSoumissions();
        });
    }
    
    const filtreStatut = document.getElementById('filtre-statut');
    if (filtreStatut) {
        filtreStatut.addEventListener('change', function() {
            currentFilters.statut = this.value;
            currentPage = 1;
            chargerSoumissions();
        });
    }
    
    const filtreDate = document.getElementById('filtre-date');
    if (filtreDate) {
        filtreDate.addEventListener('change', function() {
            currentFilters.date = this.value;
            currentPage = 1;
            chargerSoumissions();
        });
    }
    
    const filtreEtudiant = document.getElementById('filtre-etudiant');
    if (filtreEtudiant) {
        filtreEtudiant.addEventListener('input', debounce(function() {
            currentFilters.search = this.value.trim();
            currentPage = 1;
            chargerSoumissions();
        }, 500));
    }
}

// Configurer les événements du modal de correction
function configurerModalCorrection() {
    // Fermer le modal d'image
    document.addEventListener('click', function(e) {
        const imageModal = document.getElementById('image-modal-overlay');
        if (imageModal && e.target === imageModal) {
            closeImageModal();
        }
        
        const imageModalDetails = document.getElementById('image-modal-overlay-details');
        if (imageModalDetails && e.target === imageModalDetails) {
            closeImageModalDetails();
        }
    });
}

// Appliquer les filtres
function appliquerFiltresHandler() {
    console.log("🔍 Application des filtres...");
    currentFilters = {
        tp_id: document.getElementById('filtre-tp')?.value || 'all',
        statut: document.getElementById('filtre-statut')?.value || 'all',
        date: document.getElementById('filtre-date')?.value || '',
        search: document.getElementById('filtre-etudiant')?.value.trim() || ''
    };
    
    console.log("📋 Filtres appliqués:", currentFilters);
    currentPage = 1;
    chargerSoumissions();
}

// Réinitialiser les filtres
function reinitialiserFiltresHandler() {
    console.log("🔄 Réinitialisation des filtres...");
    const filtreTp = document.getElementById('filtre-tp');
    const filtreStatut = document.getElementById('filtre-statut');
    const filtreDate = document.getElementById('filtre-date');
    const filtreEtudiant = document.getElementById('filtre-etudiant');
    
    if (filtreTp) filtreTp.value = 'all';
    if (filtreStatut) filtreStatut.value = 'all';
    if (filtreDate) filtreDate.value = '';
    if (filtreEtudiant) filtreEtudiant.value = '';
    
    currentFilters = {};
    currentPage = 1;
    chargerSoumissions();
}

// ============================================================================
// FONCTION PRINCIPALE POUR OUVIR LA CORRECTION
// ============================================================================

// FONCTION ULTIME - Ouvre directement la correction sans passer par les détails
async function ouvrirCorrectionDirect(tpId, etudiantId, event) {
    console.log("📝 ouvrirCorrectionDirect appelée avec:", { tpId, etudiantId });
    
    if (event) {
        event.stopPropagation();
        event.preventDefault();
    }
    
    try {
        // Afficher un indicateur de chargement
        afficherToast('Chargement de la soumission...', 'info');
        
        // 1. Charger les données de la soumission
        const response = await fetch(`/api/soumissions/${tpId}/${etudiantId}`);
        
        if (!response.ok) {
            throw new Error(`Erreur HTTP ${response.status}`);
        }
        
        const data = await response.json();
        
        console.log("📝 Données reçues de l'API:", data);
        
        if (!data.success) {
            throw new Error(data.message || 'Erreur lors du chargement des données');
        }
        
        // 2. Définir selectedSubmission AVANT d'ouvrir le modal
        selectedSubmission = data;
        
        // 3. Afficher le modal de correction
        afficherModalCorrection(data);
        
    } catch (error) {
        console.error("❌ Erreur dans ouvrirCorrectionDirect:", error);
        afficherToast(`Erreur: ${error.message}`, 'error');
    }
}

// ============================================================================
// FONCTION POUR OUVRIR LA CORRECTION DEPUIS LES DÉTAILS
// ============================================================================

function ouvrirCorrection() {
    console.log("📝 ouvrirCorrection() appelée");
    console.log("📝 selectedSubmission:", selectedSubmission);
    
    if (!selectedSubmission) {
        afficherToast('Erreur: Aucune soumission sélectionnée', 'error');
        return;
    }
    
    const tpId = selectedSubmission.tp.id;
    const etudiantId = selectedSubmission.etudiant.id;
    
    console.log("📝 Données extraites:", { tpId, etudiantId });
    
    // Fermer le modal de détails
    fermerModalDetails();
    
    // Ouvrir directement la correction
    ouvrirCorrectionDirect(tpId, etudiantId, null);
}

// Afficher le modal de correction avec affichage des images
function afficherModalCorrection(data) {
    console.log("📝 afficherModalCorrection appelée avec:", data);
    
    const modal = document.getElementById('modal-correction');
    const body = document.getElementById('modal-correction-body');
    
    if (!modal || !body) {
        afficherToast('Erreur: Modal de correction non trouvé', 'error');
        return;
    }
    
    // Vérifier que les données sont valides
    if (!data || !data.tp || !data.etudiant) {
        afficherToast('Erreur: Données de soumission invalides', 'error');
        return;
    }
    
    // Calculer les statistiques
    const questionsRepondues = data.statistiques?.questions_repondues || 0;
    const questionsTotal = data.statistiques?.questions_total || 0;
    const pourcentage = questionsTotal > 0 ? Math.round((questionsRepondues / questionsTotal) * 100) : 0;
    
    // Déterminer le statut de soumission
    let statutSoumission = '';
    let statutClass = '';
    let infoStatut = '';
    
    if (questionsRepondues === questionsTotal) {
        statutSoumission = 'TP Soumis';
        statutClass = 'statut-soumis';
        infoStatut = 'L\'étudiant a soumis toutes les questions. Vous pouvez noter l\'ensemble du TP.';
    } else if (questionsRepondues > 0) {
        statutSoumission = 'TP en cours';
        statutClass = 'statut-en_cours';
        infoStatut = `L'étudiant a répondu à ${questionsRepondues}/${questionsTotal} questions. Vous pouvez noter les questions répondues.`;
    } else {
        statutSoumission = 'Non commencé';
        statutClass = 'statut-non_commence';
        infoStatut = 'L\'étudiant n\'a pas encore répondu à ce TP. La correction n\'est pas possible.';
    }
    
    body.innerHTML = `
        <div class="correction-container-academique">
            <div class="details-section-academique">
                <h3><i class="fas fa-edit"></i> Correction de la Soumission</h3>
                <div class="info-grid-academique">
                    <div class="info-item-academique">
                        <span class="info-label-academique">Étudiant</span>
                        <span class="info-value-academique">${data.etudiant?.prenom || ''} ${data.etudiant?.nom || ''}${data.etudiant?.compte_supprime ? ' <span class="badge-compte-supprime">Compte supprimé</span>' : ''}</span>
                    </div>
                    <div class="info-item-academique">
                        <span class="info-label-academique">TP</span>
                        <span class="info-value-academique">${data.tp?.titre || ''}</span>
                    </div>
                    <div class="info-item-academique">
                        <span class="info-label-academique">Statut de soumission</span>
                        <div class="info-value-academique">
                            <span class="statut-badge ${statutClass}">${statutSoumission}</span>
                            <div class="small-text" style="margin-top: 5px;">${infoStatut}</div>
                        </div>
                    </div>
                </div>
                <div class="statut-info-alerte">
                    ${questionsRepondues < questionsTotal ? 
                        `<div class="alerte-info">
                            <i class="fas fa-info-circle"></i>
                            <span>Note: Seules les questions déjà répondues peuvent être notées.</span>
                        </div>` : 
                        `<div class="alerte-success">
                            <i class="fas fa-check-circle"></i>
                            <span>TP complet - Toutes les questions peuvent être notées.</span>
                        </div>`
                    }
                </div>
            </div>
            
            <form id="correction-form">
                ${(data.questions || []).map((q, index) => {
                    const hasResponse = q.reponse_etudiant !== null && q.reponse_etudiant !== '';
                    const hasFile = q.fichier_url && q.fichier_nom;
                    const isAnswered = questionsRepondues > 0 && (hasResponse || hasFile);
                    const noteValue = q.note !== null && q.note !== undefined ? q.note : '';
                    
                    // Déterminer comment afficher la réponse
                    let reponseDisplay = '';
                    if (hasFile) {
                        // Vérifier si c'est une image
                        const imageExtensions = ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp'];
                        const isImage = imageExtensions.some(ext => 
                            q.fichier_nom.toLowerCase().endsWith(ext)
                        );
                        
                        if (isImage) {
                            // Afficher l'image avec possibilité de zoom
                            reponseDisplay = `
                                <div class="image-response-container">
                                    <div class="image-preview" onclick="openImageModal('${q.fichier_url}', '${q.fichier_nom}')">
                                        <img src="${q.fichier_url}" alt="${q.fichier_nom}" 
                                             class="student-uploaded-image">
                                        <div class="image-overlay">
                                            <i class="fas fa-search-plus"></i>
                                            <span>Cliquez pour agrandir</span>
                                        </div>
                                    </div>
                                    <div class="image-info">
                                        <small><i class="fas fa-file-image"></i> ${q.fichier_nom}</small>
                                        <a href="${q.fichier_url}" target="_blank" 
                                           class="download-link" download="${q.fichier_nom}">
                                            <i class="fas fa-download"></i> Télécharger
                                        </a>
                                    </div>
                                </div>
                            `;
                        } else {
                            // Pour les fichiers non-image
                            reponseDisplay = `
                                <div class="file-response-container">
                                    <div class="file-icon">
                                        <i class="fas fa-file-alt fa-2x"></i>
                                    </div>
                                    <div class="file-info">
                                        <strong>${q.fichier_nom}</strong>
                                        <a href="${q.fichier_url}" target="_blank" class="download-link" 
                                           download="${q.fichier_nom}">
                                            <i class="fas fa-download"></i> Télécharger le fichier
                                        </a>
                                    </div>
                                </div>
                            `;
                        }
                    } else if (hasResponse) {
                        // Réponse texte normale
                        reponseDisplay = formatReponse(q.reponse_etudiant, q.type_question);
                    } else {
                        reponseDisplay = '<div class="reponse-non-repondu"><i class="fas fa-times-circle"></i> Non répondu</div>';
                    }
                    
                    return `
                        <div class="correction-item-academique ${!isAnswered ? 'question-non-repondu' : ''}">
                            <div class="question-enonce-academique">
                                <strong>Question ${index + 1}</strong>
                                ${q.enonce || ''}
                                <span class="question-points">${q.points || 0} point${(q.points || 0) > 1 ? 's' : ''}</span>
                                ${!isAnswered ? '<span class="badge-non-repondu"><i class="fas fa-clock"></i> Non répondu</span>' : ''}
                            </div>
                            
                            <div class="reponse-container-academique">
                                <span class="reponse-label-academique">
                                    <i class="fas fa-user-edit"></i> Réponse de l'étudiant:
                                </span>
                                <div class="reponse-etudiant-academique">
                                    ${reponseDisplay}
                                </div>
                            </div>
                            
                            <div class="note-input-container-academique ${!isAnswered ? 'disabled-note-input' : ''}">
                                <label style="font-weight: 500;">Attribution de points:</label>
                                <input type="number" 
                                       id="note-${q.id}" 
                                       name="note-${q.id}" 
                                       class="note-input-academique ${!isAnswered ? 'disabled' : ''}" 
                                       min="0" 
                                       max="${q.points || 0}" 
                                       step="0.5"
                                       value="${noteValue}"
                                       placeholder="0-${q.points || 0}"
                                       ${!isAnswered ? 'disabled' : ''}>
                                <span class="note-max-academique">/ ${q.points || 0} points</span>
                            </div>
                            ${!isAnswered ? '<div class="note-disabled-info small-text"><i class="fas fa-info-circle"></i> Non notable (question non répondue)</div>' : ''}
                        </div>
                    `;
                }).join('')}
                
                <div class="details-section-academique">
                    <h3><i class="fas fa-comment-dots"></i> Commentaire Général</h3>
                    <p class="small-text" style="margin-bottom: 10px; color: #6c757d;">
                        Ajoutez un commentaire constructif pour aider l'étudiant à améliorer son travail.
                    </p>
                    <textarea id="commentaire-general" class="commentaire-input-academique" 
                              placeholder="Exemple: Bon travail sur les concepts fondamentaux. Pour la prochaine fois, essayez d'approfondir l'analyse des résultats...">${escapeHtml(data.commentaire_general || '')}</textarea>
                </div>
            </form>
        </div>
        
        <!-- Modal pour afficher l'image en grand -->
        <div class="image-modal-overlay" id="image-modal-overlay" style="display: none;">
            <div class="image-modal-content">
                <div class="image-modal-header">
                    <h3 id="image-modal-title">Image de l'étudiant</h3>
                    <button class="image-modal-close" onclick="closeImageModal()">&times;</button>
                </div>
                <div class="image-modal-body">
                    <img id="image-modal-img" src="" alt="" class="full-size-image">
                </div>
                <div class="image-modal-footer">
                    <a href="" id="image-modal-download" download class="bouton bouton-primary">
                        <i class="fas fa-download"></i> Télécharger
                    </a>
                    <button class="bouton bouton-secondary" onclick="closeImageModal()">
                        <i class="fas fa-times"></i> Fermer
                    </button>
                </div>
            </div>
        </div>
    `;
    
    modal.style.display = 'flex';
    console.log("✅ Modal de correction affiché");
}

// Ouvrir le modal d'image en grand
function openImageModal(imageUrl, fileName) {
    console.log("🖼️ Ouverture modal image:", { imageUrl, fileName });
    const modalOverlay = document.getElementById('image-modal-overlay');
    const modalImage = document.getElementById('image-modal-img');
    const modalTitle = document.getElementById('image-modal-title');
    const downloadLink = document.getElementById('image-modal-download');
    
    if (modalOverlay && modalImage) {
        modalImage.src = imageUrl;
        modalImage.alt = fileName;
        modalTitle.textContent = `Image: ${fileName}`;
        downloadLink.href = imageUrl;
        downloadLink.download = fileName;
        modalOverlay.style.display = 'flex';
        document.body.style.overflow = 'hidden';
    }
}

// Fermer le modal d'image
function closeImageModal() {
    const modalOverlay = document.getElementById('image-modal-overlay');
    if (modalOverlay) {
        modalOverlay.style.display = 'none';
        document.body.style.overflow = 'auto';
    }
}

// ============================================================================
// SAUVEGARDE DE LA CORRECTION - VERSION CORRIGÉE
// ============================================================================

// Sauvegarder la correction
async function sauvegarderCorrection() {
    console.log("💾 sauvegarderCorrection() appelée");
    
    // Vérifier que selectedSubmission existe
    if (!selectedSubmission) {
        afficherToast('Erreur: Aucune soumission sélectionnée', 'error');
        return;
    }
    
    try {
        // Récupérer toutes les notes
        const corrections = [];
        let notesValides = 0;
        
        // Parcourir toutes les questions de selectedSubmission
        selectedSubmission.questions.forEach((question) => {
            const inputId = `note-${question.id}`;
            const noteInput = document.getElementById(inputId);
            
            if (noteInput && !noteInput.disabled) {
                const noteValue = noteInput.value.trim();
                
                if (noteValue !== '' && noteValue !== null) {
                    try {
                        const noteNum = parseFloat(noteValue);
                        if (!isNaN(noteNum) && noteNum >= 0) {
                            corrections.push({
                                question_id: question.id,
                                note: noteNum
                            });
                            notesValides++;
                            console.log(`✅ Note ${noteNum} pour question ${question.id}`);
                        }
                    } catch (e) {
                        console.warn(`⚠️ Note invalide pour question ${question.id}: ${noteValue}`);
                    }
                }
            }
        });
        
        if (notesValides === 0) {
            afficherToast('Veuillez attribuer au moins une note valide', 'error');
            return;
        }
        
        // Récupérer le commentaire
        const commentaireInput = document.getElementById('commentaire-general');
        const commentaire = commentaireInput ? commentaireInput.value : '';
        
        // Préparer les données
        const correctionData = {
            tp_id: selectedSubmission.tp.id,
            etudiant_id: selectedSubmission.etudiant.id,
            corrections: corrections,
            commentaire: commentaire
        };
        
        console.log("📤 Données à envoyer:", correctionData);
        
        // Afficher un indicateur de chargement
        afficherToast('Enregistrement de la correction en cours...', 'info');
        
        // Envoyer au serveur avec timeout
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 15000);
        
        try {
            const response = await fetch('/api/soumissions/correction', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(correctionData),
                signal: controller.signal
            });
            
            clearTimeout(timeoutId);
            
            console.log("📥 Statut réponse:", response.status);
            
            // Vérifier d'abord le Content-Type
            const contentType = response.headers.get("content-type") || "";
            
            if (!contentType.includes("application/json")) {
                const errorText = await response.text();
                console.error("❌ Réponse non-JSON reçue:", errorText.substring(0, 500));
                
                if (response.status === 401) {
                    afficherToast('Erreur: Vous devez être connecté pour corriger', 'error');
                } else if (response.status === 403) {
                    afficherToast('Erreur: Vous n\'êtes pas autorisé à corriger ce TP', 'error');
                } else if (response.status === 404) {
                    afficherToast('Erreur: Route API non trouvée (404)', 'error');
                } else if (response.status === 500) {
                    afficherToast('Erreur serveur interne. Vérifiez les logs Flask.', 'error');
                } else {
                    afficherToast(`Erreur HTTP ${response.status}: ${errorText.substring(0, 100)}`, 'error');
                }
                return;
            }
            
            // Si c'est du JSON, parser normalement
            const data = await response.json();
            console.log("📥 Réponse JSON du serveur:", data);
            
            if (data.success) {
                afficherToast(data.message || 'Correction enregistrée avec succès!', 'success');
                fermerModalCorrection();
                
                // Recharger les données après un délai
                setTimeout(() => {
                    chargerSoumissions();
                }, 1500);
            } else {
                afficherToast(`Erreur: ${data.message}`, 'error');
            }
            
        } catch (fetchError) {
            if (fetchError.name === 'AbortError') {
                afficherToast('Erreur: Timeout - le serveur ne répond pas', 'error');
            } else {
                console.error("❌ Erreur fetch:", fetchError);
                afficherToast('Erreur réseau: ' + fetchError.message, 'error');
            }
        }
        
    } catch (error) {
        console.error("❌ Erreur dans sauvegarderCorrection:", error);
        afficherToast('Erreur lors de la sauvegarde: ' + error.message, 'error');
    }
}

// ============================================================================
// FONCTIONS DE DÉTAILS
// ============================================================================

// Afficher les détails d'une soumission
async function voirDetails(tpId, etudiantId, event) {
    console.log("👁️ Voir détails:", { tpId, etudiantId });
    
    if (event) {
        event.stopPropagation();
        event.preventDefault();
    }
    
    try {
        afficherChargementModal(true);
        
        const response = await fetch(`/api/soumissions/${tpId}/${etudiantId}`);
        
        if (!response.ok) {
            throw new Error(`Erreur HTTP ${response.status}`);
        }
        
        const data = await response.json();
        console.log("📝 Détails reçus:", data);
        
        if (data.success) {
            selectedSubmission = data;
            afficherModalDetails(data);
        } else {
            afficherToast(data.message || 'Erreur lors du chargement des détails', 'error');
        }
    } catch (error) {
        console.error("❌ Erreur chargement détails:", error);
        afficherToast('Erreur de connexion: ' + error.message, 'error');
    } finally {
        afficherChargementModal(false);
    }
}

// Afficher le modal de détails
function afficherModalDetails(data) {
    const modal = document.getElementById('modal-details');
    const body = document.getElementById('modal-body');
    
    if (!modal || !body) {
        console.error("❌ Modal non trouvé");
        return;
    }
    
    // Calculer les statistiques
    const questionsRepondues = data.statistiques?.questions_repondues || 0;
    const questionsTotal = data.statistiques?.questions_total || 0;
    const pourcentage = questionsTotal > 0 ? Math.round((questionsRepondues / questionsTotal) * 100) : 0;
    const noteTotale = data.statistiques?.note_totale ? data.statistiques.note_totale.toFixed(1) : '0.0';
    const noteMax = data.statistiques?.note_max ? data.statistiques.note_max.toFixed(1) : '0.0';
    const notePourcentage = questionsTotal > 0 && data.statistiques?.note_totale && data.statistiques?.note_max ? 
        Math.round((data.statistiques.note_totale / data.statistiques.note_max) * 100) : 0;
    
    // Calculer la durée totale depuis les données reçues
    let dureeTotale = 'Non disponible';
    if (data.statistiques?.duree_totale) {
        dureeTotale = data.statistiques.duree_totale;
    } else if (data.statistiques?.duree_totale_minutes) {
        dureeTotale = formaterDureeMinutes(data.statistiques.duree_totale_minutes);
    }
    
    // Déterminer le statut
    let statut = '';
    let statutClass = '';
    if (questionsRepondues === questionsTotal) {
        statut = 'Soumis';
        statutClass = 'statut-soumis';
    } else if (questionsRepondues > 0) {
        statut = 'En cours';
        statutClass = 'statut-en_cours';
    } else {
        statut = 'Non commencé';
        statutClass = 'statut-non_commence';
    }
    
    // Déterminer le statut de la note
    let noteStatus = '';
    let noteStatusClass = '';
    if (notePourcentage >= 70) {
        noteStatus = 'Excellent';
        noteStatusClass = 'note-excellente-status';
    } else if (notePourcentage >= 50) {
        noteStatus = 'Satisfaisant';
        noteStatusClass = 'note-satisfaisante-status';
    } else if (noteTotale > 0) {
        noteStatus = 'À améliorer';
        noteStatusClass = 'note-a-ameliorer-status';
    }
    
    body.innerHTML = `
        <div class="details-container">
            <!-- Informations de l'étudiant -->
            <div class="details-section-academique">
                <h3><i class="fas fa-user-graduate"></i> Informations de l'Étudiant${data.etudiant?.compte_supprime ? ' <span class="badge-compte-supprime">Compte supprimé</span>' : ''}</h3>
                <div class="info-grid-academique">
                    <div class="info-item-academique">
                        <span class="info-label-academique">Nom Complet</span>
                        <span class="info-value-academique">${data.etudiant?.prenom || ''} ${data.etudiant?.nom || ''}</span>
                    </div>
                    <div class="info-item-academique">
                        <span class="info-label-academique">Matricule</span>
                        <span class="info-value-academique">${data.etudiant?.matricule || ''}</span>
                    </div>
                    <div class="info-item-academique email-item">
                        <span class="info-label-academique">Email</span>
                        <span class="info-value-academique" style="font-size: 0.9rem; color: #1a73e8; word-break: break-all;">
                            <i class="fas fa-envelope" style="margin-right: 5px;"></i>
                            ${data.etudiant?.email || ''}
                        </span>
                    </div>
                    <div class="info-item-academique">
                        <span class="info-label-academique">Organisation</span>
                        <span class="info-value-academique">${data.etudiant?.organisation || 'Non spécifié'}</span>
                    </div>
                </div>
            </div>
            
            <!-- Informations du Travail Pratique -->
            <div class="details-section-academique">
                <h3><i class="fas fa-flask"></i> Travail Pratique</h3>
                <div class="info-grid-academique">
                    <div class="info-item-academique">
                        <span class="info-label-academique">Titre du TP</span>
                        <span class="info-value-academique">${data.tp?.titre || ''}</span>
                    </div>
                    <div class="info-item-academique">
                        <span class="info-label-academique">Module</span>
                        <span class="info-value-academique">${data.tp?.module || 'Non spécifié'}</span>
                    </div>
                    <div class="info-item-academique">
                        <span class="info-label-academique">Date limite</span>
                        <span class="info-value-academique">${data.tp?.date_limite ? formaterDate(data.tp.date_limite) : 'Non définie'}</span>
                    </div>
                    <div class="info-item-academique">
                        <span class="info-label-academique">Nombre de questions</span>
                        <span class="info-value-academique">${questionsTotal}</span>
                    </div>
                </div>
            </div>
            
            <!-- Statistiques de performance -->
            <div class="details-section-academique">
                <h3><i class="fas fa-chart-line"></i> Performance et Statistiques</h3>
                <div class="stats-section">
                    <div class="stat-item">
                        <div class="stat-label">Progression</div>
                        <div class="stat-value">${pourcentage}%</div>
                        <div class="progression-barre-amelioree ${statut === 'En cours' ? 'progression-en-cours' : ''}">
                            <div class="progression-remplissage-amelioree" style="width: ${pourcentage}%">
                                <span class="progression-pourcentage">${pourcentage}%</span>
                            </div>
                        </div>
                    </div>
                    <div class="stat-item">
                        <div class="stat-label">Questions répondues</div>
                        <div class="stat-value">${questionsRepondues}/${questionsTotal}</div>
                    </div>
                    <div class="stat-item">
                        <div class="stat-label">Note obtenue</div>
                        <div class="stat-value">${noteTotale}/${noteMax}</div>
                    </div>
                    <div class="stat-item">
                        <div class="stat-label">Statut</div>
                        <div class="info-value-academique">
                            <span class="statut-badge ${statutClass}">${statut}</span>
                        </div>
                    </div>
                </div>
                <div class="info-grid-academique" style="margin-top: 15px;">
                    <div class="info-item-academique">
                        <span class="info-label-academique">Date d'inscription</span>
                        <span class="info-value-academique">${data.statistiques?.date_inscription ? formaterDate(data.statistiques.date_inscription) : 'Non disponible'}</span>
                    </div>
                    <div class="info-item-academique">
                        <span class="info-label-academique">Durée totale</span>
                        <span class="info-value-academique">${dureeTotale}</span>
                    </div>
                    <div class="info-item-academique">
                        <span class="info-label-academique">Performance</span>
                        <div class="info-value-academique">
                            ${noteTotale > 0 ? `
                                <div class="note-indicator">
                                    <span class="note-value">${notePourcentage}%</span>
                                    ${noteStatus ? `<span class="note-status ${noteStatusClass}">${noteStatus}</span>` : ''}
                                </div>
                            ` : '<span class="small-text">Non noté</span>'}
                        </div>
                    </div>
                </div>
            </div>
            
            <!-- Questions et réponses -->
            <div class="details-section-academique">
                <h3><i class="fas fa-question-circle"></i> Évaluation des Questions</h3>
                <div class="questions-container-academique">
                    ${(data.questions || []).map((q, index) => {
                        const note = q.note !== null && q.note !== undefined ? parseFloat(q.note) : null;
                        let noteStatus = '';
                        let noteStatusClass = '';
                        
                        if (note !== null) {
                            if (note === q.points) {
                                noteStatus = 'Excellent';
                                noteStatusClass = 'note-excellente-status';
                            } else if (note >= q.points * 0.5) {
                                noteStatus = 'Satisfaisant';
                                noteStatusClass = 'note-satisfaisante-status';
                            } else {
                                noteStatus = 'À améliorer';
                                noteStatusClass = 'note-a-ameliorer-status';
                            }
                        }
                        
                        // Afficher l'image si présente
                        let reponseDisplay = '';
                        if (q.fichier_url && q.fichier_nom) {
                            const imageExtensions = ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp'];
                            const isImage = imageExtensions.some(ext => 
                                q.fichier_nom.toLowerCase().endsWith(ext)
                            );
                            
                            if (isImage) {
                                reponseDisplay = `
                                    <div class="image-response-container">
                                        <div class="image-preview" onclick="openImageModalDetails('${q.fichier_url}', '${q.fichier_nom}')">
                                            <img src="${q.fichier_url}" alt="${q.fichier_nom}" 
                                                 class="student-uploaded-image">
                                            <div class="image-overlay">
                                                <i class="fas fa-search-plus"></i>
                                                <span>Cliquez pour agrandir</span>
                                            </div>
                                        </div>
                                        <div class="image-info">
                                            <small><i class="fas fa-file-image"></i> ${q.fichier_nom}</small>
                                        </div>
                                    </div>
                                `;
                            } else {
                                reponseDisplay = `
                                    <div class="file-response-container">
                                        <div class="file-icon">
                                            <i class="fas fa-file-alt fa-2x"></i>
                                        </div>
                                        <div class="file-info">
                                            <strong>${q.fichier_nom}</strong>
                                            <a href="${q.fichier_url}" target="_blank" class="download-link" 
                                               download="${q.fichier_nom}">
                                                <i class="fas fa-download"></i> Télécharger
                                            </a>
                                        </div>
                                    </div>
                                `;
                            }
                        } else if (q.reponse_etudiant) {
                            reponseDisplay = formatReponse(q.reponse_etudiant, q.type_question);
                        } else {
                            reponseDisplay = '<i class="fas fa-times-circle"></i> Non répondu';
                        }
                        
                        return `
                            <div class="question-item-academique">
                                <div class="question-enonce-academique">
                                    <strong>Question ${index + 1}</strong>
                                    ${q.enonce || ''}
                                    <span class="question-points">${q.points || 0} point${(q.points || 0) > 1 ? 's' : ''}</span>
                                </div>
                                
                                <div class="reponse-container-academique">
                                    <span class="reponse-label-academique">
                                        <i class="fas fa-user-edit"></i> Réponse de l'étudiant:
                                    </span>
                                    <div class="reponse-etudiant-academique ${!q.reponse_etudiant && !q.fichier_url ? 'reponse-non-repondu' : ''}">
                                        ${reponseDisplay}
                                    </div>
                                </div>
                                
                                <div class="reponse-container-academique">
                                    <span class="reponse-label-academique">
                                        <i class="fas fa-check-circle"></i> Évaluation:
                                    </span>
                                    ${note !== null ? `
                                        <div class="reponse-correcte-academique">
                                            <div class="note-indicator">
                                                <span class="note-value">${note}/${q.points || 0}</span>
                                                ${noteStatus ? `<span class="note-status ${noteStatusClass}">${noteStatus}</span>` : ''}
                                            </div>
                                        </div>
                                    ` : `
                                        <div class="reponse-correcte-academique" style="background: #fff3cd;">
                                            <i class="fas fa-clock"></i> En attente de correction
                                        </div>
                                    `}
                                </div>
                            </div>
                        `;
                    }).join('')}
                </div>
            </div>
        </div>
        
        <!-- Modal d'image pour les détails -->
        <div class="image-modal-overlay" id="image-modal-overlay-details" style="display: none;">
            <div class="image-modal-content">
                <div class="image-modal-header">
                    <h3 id="image-modal-title-details">Image de l'étudiant</h3>
                    <button class="image-modal-close" onclick="closeImageModalDetails()">&times;</button>
                </div>
                <div class="image-modal-body">
                    <img id="image-modal-img-details" src="" alt="" class="full-size-image">
                </div>
                <div class="image-modal-footer">
                    <a href="" id="image-modal-download-details" download class="bouton bouton-primary">
                        <i class="fas fa-download"></i> Télécharger
                    </a>
                    <button class="bouton bouton-secondary" onclick="closeImageModalDetails()">
                        <i class="fas fa-times"></i> Fermer
                    </button>
                </div>
            </div>
        </div>
    `;
    
    modal.style.display = 'flex';
    console.log("✅ Modal de détails affiché");
}

// Fonctions pour le modal d'image dans les détails
function openImageModalDetails(imageUrl, fileName) {
    console.log("🖼️ Ouverture modal image détails:", { imageUrl, fileName });
    const modalOverlay = document.getElementById('image-modal-overlay-details');
    const modalImage = document.getElementById('image-modal-img-details');
    const modalTitle = document.getElementById('image-modal-title-details');
    const downloadLink = document.getElementById('image-modal-download-details');
    
    if (modalOverlay && modalImage) {
        modalImage.src = imageUrl;
        modalImage.alt = fileName;
        modalTitle.textContent = `Image: ${fileName}`;
        downloadLink.href = imageUrl;
        downloadLink.download = fileName;
        modalOverlay.style.display = 'flex';
        document.body.style.overflow = 'hidden';
    }
}

function closeImageModalDetails() {
    const modalOverlay = document.getElementById('image-modal-overlay-details');
    if (modalOverlay) {
        modalOverlay.style.display = 'none';
        document.body.style.overflow = 'auto';
    }
}

// Formater une réponse selon son type
function formatReponse(reponse, type) {
    if (!reponse) return '';
    
    try {
        if (type === 'case_cocher') {
            // La réponse stockée est un tableau JSON des TEXTES des options
            // cochées (pas des index) : on l'affiche tel quel, joint par des virgules.
            let items;
            try {
                items = JSON.parse(reponse);
            } catch (e) {
                items = reponse.split(',').map(s => s.trim());
            }
            if (!Array.isArray(items)) items = [String(items)];
            return items.filter(x => String(x).trim() !== '').map(x => escapeHtml(String(x))).join(', ');
        } else if (type === 'qcm') {
            // La réponse stockée EST déjà le texte de l'option choisie.
            return escapeHtml(String(reponse));
        } else if (type === 'code') {
            return `<pre style="background: #f5f5f5; padding: 10px; border-radius: 4px; overflow-x: auto;"><code>${escapeHtml(reponse)}</code></pre>`;
        } else {
            // Échapper les caractères HTML pour la sécurité
            return reponse.replace(/[&<>"']/g, function(m) {
                return {
                    '&': '&amp;',
                    '<': '&lt;',
                    '>': '&gt;',
                    '"': '&quot;',
                    "'": '&#39;'
                }[m];
            }).replace(/\n/g, '<br>');
        }
    } catch (e) {
        console.warn("⚠️ Erreur formatage réponse:", e);
        return reponse;
    }
}

// Formater la durée en minutes
function formaterDureeMinutes(minutes) {
    if (!minutes || minutes === 0) return '0 min';
    
    const heures = Math.floor(minutes / 60);
    const mins = Math.floor(minutes % 60);
    
    if (heures > 0) {
        return `${heures}h ${mins}min`;
    } else {
        return `${mins}min`;
    }
}

// ============================================================================
// FONCTIONS D'EXPORT CSV
// ============================================================================

// Exporter toutes les données en CSV
async function exporterDonneesCSV() {
    try {
        console.log("📤 Export CSV avec filtres:", currentFilters);
        
        // Récupérer l'ID du TP sélectionné
        const tpId = document.getElementById('filtre-tp')?.value || 'all';
        
        if (tpId === 'all') {
            afficherToast('Veuillez sélectionner un TP spécifique pour l\'export', 'error');
            return;
        }
        
        afficherToast('Génération du fichier CSV...', 'info');
        
        // Construire les paramètres de requête
        const params = new URLSearchParams();
        params.append('tp_id', tpId);
        
        // Ajouter les autres filtres si nécessaire
        const statut = document.getElementById('filtre-statut')?.value;
        if (statut && statut !== 'all') {
            params.append('statut', statut);
        }
        
        const search = document.getElementById('filtre-etudiant')?.value;
        if (search && search.trim() !== '') {
            params.append('search', search.trim());
        }
        
        window.location.href = `/api/soumissions/export_csv?${params}`;
        
        // Afficher un message de succès après un délai
        setTimeout(() => {
            afficherToast('Export CSV en cours de téléchargement...', 'success');
        }, 500);
        
    } catch (error) {
        console.error("❌ Erreur export CSV:", error);
        afficherToast('Erreur lors de l\'exportation: ' + error.message, 'error');
    }
}

// Exporter une soumission individuelle
async function exporterSoumission(tpId, etudiantId, event) {
    console.log("📤 Export soumission:", { tpId, etudiantId });
    
    if (event) {
        event.stopPropagation();
        event.preventDefault();
    }
    
    try {
        afficherToast('Préparation de l\'export PDF...', 'info');
        
        const response = await fetch(`/api/soumissions/${tpId}/${etudiantId}/export`);
        
        if (!response.ok) {
            throw new Error(`Erreur HTTP ${response.status}`);
        }
        
        const blob = await response.blob();
        
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `soumission_${tpId}_${etudiantId}_${new Date().toISOString().slice(0, 10)}.pdf`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        window.URL.revokeObjectURL(url);
        
        afficherToast('Exportation PDF terminée', 'success');
    } catch (error) {
        console.error("❌ Erreur exportation:", error);
        afficherToast('Erreur lors de l\'exportation: ' + error.message, 'error');
    }
}

// Exporter les détails d'une soumission
function exporterDetails() {
    if (!selectedSubmission) {
        afficherToast('Aucune soumission sélectionnée', 'error');
        return;
    }
    
    console.log("📤 Export détails:", selectedSubmission);
    exporterSoumission(selectedSubmission.tp.id, selectedSubmission.etudiant.id);
}

// ============================================================================
// AUTRES FONCTIONS
// ============================================================================

// Fermer le modal de détails
function fermerModalDetails() {
    const modal = document.getElementById('modal-details');
    if (modal) {
        modal.style.display = 'none';
    }
    selectedSubmission = null;
    console.log("❌ Modal détails fermé");
}

// Fermer le modal de correction
function fermerModalCorrection() {
    const modal = document.getElementById('modal-correction');
    if (modal) {
        modal.style.display = 'none';
    }
    selectedSubmission = null;
    console.log("❌ Modal correction fermé");
}

// Afficher/masquer le chargement
function afficherChargement(show) {
    const indicator = document.getElementById('indicateur-chargement');
    const container = document.getElementById('conteneur-tableau');
    const pagination = document.getElementById('pagination');
    
    if (indicator) indicator.style.display = show ? 'flex' : 'none';
    if (container) container.style.display = show ? 'none' : 'block';
    if (pagination) pagination.style.display = show ? 'none' : 'flex';
}

// Afficher/masquer le chargement du modal
function afficherChargementModal(show) {
    const body = document.getElementById('modal-body');
    if (!body) return;
    
    if (show) {
        body.innerHTML = `
            <div style="text-align: center; padding: 40px;">
                <div class="spinner"></div>
                <p>Chargement des détails de la soumission...</p>
            </div>
        `;
    }
}

// Afficher une notification toast
function afficherToast(message, type = 'info') {
    // Supprimer les anciens toasts
    document.querySelectorAll('.toast').forEach(toast => {
        toast.remove();
    });
    
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.innerHTML = `
        <i class="fas fa-${type === 'success' ? 'check-circle' : type === 'error' ? 'exclamation-circle' : 'info-circle'}"></i>
        <span>${message}</span>
    `;
    
    document.body.appendChild(toast);
    
    // Animation d'entrée
    setTimeout(() => {
        toast.classList.add('show');
    }, 10);
    
    // Supprimer après 3 secondes
    setTimeout(() => {
        toast.classList.remove('show');
        setTimeout(() => {
            if (toast.parentNode) {
                toast.remove();
            }
        }, 300);
    }, 3000);
}

// ============================================================================
// FONCTIONS UTILITAIRES
// ============================================================================

// Formater une date
function formaterDate(dateString) {
    if (!dateString) return '-';
    
    try {
        const date = new Date(dateString);
        if (isNaN(date.getTime())) {
            return 'Date invalide';
        }
        return date.toLocaleDateString('fr-FR', {
            day: '2-digit',
            month: '2-digit',
            year: 'numeric',
            hour: '2-digit',
            minute: '2-digit'
        });
    } catch (error) {
        return 'Date invalide';
    }
}

// Formater une date relative
function formaterDateRelative(dateString) {
    if (!dateString) return 'Jamais';
    
    try {
        const date = new Date(dateString);
        if (isNaN(date.getTime())) {
            return 'Date invalide';
        }
        
        const now = new Date();
        const diff = Math.floor((now - date) / 1000); // Différence en secondes
        
        if (diff < 60) return 'À l\'instant';
        if (diff < 3600) return `Il y a ${Math.floor(diff / 60)} minute(s)`;
        if (diff < 86400) return `Il y a ${Math.floor(diff / 3600)} heure(s)`;
        if (diff < 604800) return `Il y a ${Math.floor(diff / 86400)} jour(s)`;
        
        return date.toLocaleDateString('fr-FR', { day: '2-digit', month: '2-digit' });
    } catch (error) {
        return 'Date invalide';
    }
}

// Calculer la dernière activité
function calculerDerniereActivite(dateString) {
    if (!dateString) return 'Jamais';
    return formaterDateRelative(dateString);
}

// Obtenir la date d'activité la plus récente
function getRecentActivityDate() {
    if (soumissionsFiltrees.length === 0) return null;
    
    const dates = soumissionsFiltrees
        .map(s => s.date_soumission)
        .filter(d => d)
        .sort()
        .reverse();
    
    return dates.length > 0 ? dates[0] : null;
}

// Obtenir le label d'un statut
function getStatutLabel(statut) {
    const labels = {
        'soumis': 'Soumis',
        'en_cours': 'En cours',
        'non_commence': 'Non démarré'
    };
    return labels[statut] || statut;
}

// Obtenir le label d'un tri
function getSortLabel(field) {
    const labels = {
        'etudiant': 'Étudiant',
        'tp': 'TP',
        'module': 'Module',
        'statut': 'Statut',
        'progression': 'Progression',
        'date_soumission': 'Date',
        'derniere_activite': 'Activité',
        'note': 'Note'
    };
    return labels[field] || field;
}

// Fonction debounce pour limiter les appels
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func.apply(this, args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

// ============================================================================
// EXPORT DES FONCTIONS GLOBALES
// ============================================================================

// Exporter toutes les fonctions globalement
window.voirDetails = voirDetails;
window.ouvrirCorrectionDirect = ouvrirCorrectionDirect;
window.ouvrirCorrection = ouvrirCorrection;
window.exporterSoumission = exporterSoumission;
window.sauvegarderCorrection = sauvegarderCorrection;
window.exporterDetails = exporterDetails;
window.fermerModalDetails = fermerModalDetails;
window.fermerModalCorrection = fermerModalCorrection;
window.openImageModal = openImageModal;
window.closeImageModal = closeImageModal;
window.openImageModalDetails = openImageModalDetails;
window.closeImageModalDetails = closeImageModalDetails;
window.formatReponse = formatReponse;
window.exporterDonneesCSV = exporterDonneesCSV;