// bibliotheque.js - Système de filtrage de documents

/**
 * Gère le filtrage des documents dans la bibliothèque
 */
class DocumentFilter {
    constructor() {
        this.filterButtons = document.querySelectorAll('.bouton-filtre');
        this.cards = document.querySelectorAll('.carte-document');
        this.searchInput = null; // Pour une future fonctionnalité de recherche
        this.initialize();
    }

    /**
     * Initialise le système de filtrage
     */
    initialize() {
        this.setupEventListeners();
        this.setupDownloadButtons();
    }

    /**
     * Configure les écouteurs d'événements
     */
    setupEventListeners() {
        // Filtrage par boutons
        this.filterButtons.forEach(button => {
            button.addEventListener('click', (event) => {
                this.handleFilterClick(event);
            });
        });

        // Pour une future fonctionnalité de recherche
        this.setupSearch();
    }

    /**
     * Gère le clic sur un bouton de filtre
     * @param {Event} event - L'événement de clic
     */
    handleFilterClick(event) {
        // Retirer la classe active de tous les boutons
        this.filterButtons.forEach(btn => btn.classList.remove('actif'));
        
        // Ajouter la classe active au bouton cliqué
        event.currentTarget.classList.add('actif');
        
        // Récupérer la valeur du filtre
        const filter = event.currentTarget.getAttribute('data-filter');
        
        // Appliquer le filtre
        this.applyFilter(filter);
        
        // Ajouter une animation de transition
        this.animateFilterTransition();
    }

    /**
     * Applique le filtre aux cartes
     * @param {string} filter - Le filtre à appliquer
     */
    applyFilter(filter) {
        this.cards.forEach(card => {
            if (filter === 'tous') {
                card.style.display = 'flex';
                card.classList.remove('filtered-out');
            } else {
                const category = card.getAttribute('data-category');
                if (category === filter) {
                    card.style.display = 'flex';
                    card.classList.remove('filtered-out');
                } else {
                    card.style.display = 'none';
                    card.classList.add('filtered-out');
                }
            }
        });
        
        // Déclencher un événement personnalisé pour indiquer que le filtrage est terminé
        document.dispatchEvent(new CustomEvent('filterApplied', { 
            detail: { filter: filter } 
        }));
    }

    /**
     * Anime la transition lors du changement de filtre
     */
    animateFilterTransition() {
        this.cards.forEach((card, index) => {
            if (card.style.display !== 'none') {
                card.style.opacity = '0';
                card.style.transform = 'translateY(10px)';
                
                setTimeout(() => {
                    card.style.transition = 'opacity 0.3s ease, transform 0.3s ease';
                    card.style.opacity = '1';
                    card.style.transform = 'translateY(0)';
                }, index * 50); // Effet de cascade
            }
        });
    }

    /**
     * Configure les boutons de téléchargement
     */
    setupDownloadButtons() {
        const downloadButtons = document.querySelectorAll('.bouton-telecharger');
        
        downloadButtons.forEach(button => {
            button.addEventListener('click', (event) => {
                this.handleDownload(event);
            });
        });
    }

    /**
     * Gère le téléchargement d'un document
     * @param {Event} event - L'événement de clic
     */
    handleDownload(event) {
        event.preventDefault();
        
        // Récupérer les informations du document
        const card = event.currentTarget.closest('.carte-document');
        const title = card.querySelector('h3').textContent;
        const category = card.getAttribute('data-category');
        
        // Simuler le téléchargement (à remplacer par une vraie logique)
        this.simulateDownload(title, category);
        
        // Ajouter une animation de confirmation
        this.showDownloadConfirmation(event.currentTarget, title);
    }

    /**
     * Simule le téléchargement d'un document
     * @param {string} title - Titre du document
     * @param {string} category - Catégorie du document
     */
    simulateDownload(title, category) {
        console.log(`Téléchargement du document: ${title} (${category})`);
        
        // Ici, vous pouvez ajouter la logique pour télécharger le vrai fichier
        // Par exemple:
        // window.location.href = `/download/${encodeURIComponent(title)}`;
        
        // Pour l'instant, on simule juste un téléchargement
        setTimeout(() => {
            console.log(`Document "${title}" téléchargé avec succès!`);
        }, 500);
    }

    /**
     * Affiche une confirmation de téléchargement
     * @param {HTMLElement} button - Le bouton de téléchargement
     * @param {string} title - Titre du document
     */
    showDownloadConfirmation(button, title) {
        const originalText = button.innerHTML;
        
        // Changer le texte du bouton temporairement
        button.innerHTML = `
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <polyline points="20 6 9 17 4 12"></polyline>
            </svg>
            Téléchargé!
        `;
        
        button.classList.add('downloading');
        
        // Restaurer le texte original après 2 secondes
        setTimeout(() => {
            button.innerHTML = originalText;
            button.classList.remove('downloading');
            button.classList.add('downloaded');
            
            // Retirer la classe après un moment
            setTimeout(() => {
                button.classList.remove('downloaded');
            }, 1000);
        }, 2000);
    }

    /**
     * Configure la fonctionnalité de recherche (pour une future implémentation)
     */
    setupSearch() {
        // Cette fonction peut être implémentée plus tard
        console.log('Fonctionnalité de recherche prête à être implémentée');
    }

    /**
     * Réinitialise tous les filtres
     */
    resetFilters() {
        this.filterButtons.forEach(btn => btn.classList.remove('actif'));
        const allFilter = document.querySelector('.bouton-filtre[data-filter="tous"]');
        if (allFilter) {
            allFilter.classList.add('actif');
        }
        this.applyFilter('tous');
    }

    /**
     * Récupère toutes les cartes filtrées
     * @param {string} filter - Le filtre à appliquer
     * @returns {Array} - Les cartes filtrées
     */
    getFilteredCards(filter = 'tous') {
        if (filter === 'tous') {
            return Array.from(this.cards);
        }
        
        return Array.from(this.cards).filter(card => {
            return card.getAttribute('data-category') === filter;
        });
    }

    /**
     * Ajoute un nouveau document à la bibliothèque
     * @param {Object} documentData
     */
    addDocument(documentData) {
        // Cette fonction peut être utilisée pour ajouter dynamiquement des documents
        // à implémenter selon les besoins
        console.log('Ajout de document:', documentData);
    }
}

/**
 * Initialise le système de filtrage quand le DOM est chargé
 */
function initializeBibliotheque() {
    // Vérifier si nous sommes sur la page bibliothèque
    if (document.querySelector('.page-bibliotheque')) {
        const documentFilter = new DocumentFilter();
        
        // Exposer l'instance globalement si nécessaire
        window.documentFilter = documentFilter;
        
        // Ajouter des raccourcis clavier
        document.addEventListener('keydown', (event) => {
            // Ctrl+F pour réinitialiser les filtres
            if (event.ctrlKey && event.key === 'f') {
                event.preventDefault();
                documentFilter.resetFilters();
            }
        });
        
        console.log('Système de bibliothèque initialisé avec succès');
    }
}

// Initialiser quand le DOM est chargé
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initializeBibliotheque);
} else {
    initializeBibliotheque();
}
