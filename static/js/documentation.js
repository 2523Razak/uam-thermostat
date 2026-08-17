// Gestion des onglets de la page documentation
document.addEventListener('DOMContentLoaded', () => {
    const boutons = document.querySelectorAll('.bouton-onglet');
    const contenus = document.querySelectorAll('.contenu-onglet');

    // Fonction pour changer d'onglet
    function changerOnglet(cibleId) {
        // Mettre à jour les boutons
        boutons.forEach(b => b.classList.remove('actif'));
        const boutonActif = document.querySelector(`[data-cible="${cibleId}"]`);
        if (boutonActif) {
            boutonActif.classList.add('actif');
        }

        // Mettre à jour les contenus
        contenus.forEach(contenu => {
            contenu.style.display = 'none';
            contenu.classList.remove('actif');
        });
        
        const contenuCible = document.getElementById(cibleId);
        if (contenuCible) {
            contenuCible.style.display = 'block';
            contenuCible.classList.add('actif');
            
            // Animation d'apparition
            contenuCible.style.animation = 'none';
            setTimeout(() => {
                contenuCible.style.animation = 'fadeIn 0.5s ease';
            }, 10);
        }
    }

    // Ajouter les événements aux boutons
    boutons.forEach(bouton => {
        bouton.addEventListener('click', () => {
            const cibleId = bouton.getAttribute('data-cible');
            changerOnglet(cibleId);
            
            // Optionnel: Sauvegarder l'onglet actif dans le localStorage
            localStorage.setItem('ongletActifDoc', cibleId);
        });
    });

    // Restaurer l'onglet actif depuis le localStorage (si existant)
    const ongletSauvegarde = localStorage.getItem('ongletActifDoc');
    if (ongletSauvegarde && document.getElementById(ongletSauvegarde)) {
        changerOnglet(ongletSauvegarde);
    }

    // Gestion du responsive
    function gererResponsive() {
        const largeurEcran = window.innerWidth;
        const contenus = document.querySelectorAll('.contenu-onglet');
        
        if (largeurEcran <= 768) {
            // Sur mobile, s'assurer que tous les contenus sont visibles pour le scroll
            contenus.forEach(contenu => {
                if (!contenu.classList.contains('actif')) {
                    contenu.style.display = 'none';
                }
            });
        }
    }

    // Initialiser le responsive
    gererResponsive();
    
    // Écouter les changements de taille d'écran
    window.addEventListener('resize', gererResponsive);

    // Optionnel: Navigation au clavier
    document.addEventListener('keydown', (e) => {
        if (e.ctrlKey || e.metaKey) return;
        
        const onglets = Array.from(boutons);
        const indexActif = onglets.findIndex(b => b.classList.contains('actif'));
        
        if (e.key === 'ArrowRight' && indexActif < onglets.length - 1) {
            onglets[indexActif + 1].click();
            e.preventDefault();
        } else if (e.key === 'ArrowLeft' && indexActif > 0) {
            onglets[indexActif - 1].click();
            e.preventDefault();
        }
    });
});