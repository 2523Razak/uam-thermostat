 // ===== GESTION DES ÉTAPES =====
        let etapeActuelle = 1;
        const etapes = ['etape-1', 'etape-2', 'etape-3'];
        
        // Initialiser la progression
        function initialiserProgression() {
            const indicateurs = document.querySelectorAll('.etape-progression');
            indicateurs.forEach((indicateur, index) => {
                if (index < etapeActuelle - 1) {
                    indicateur.classList.add('completed');
                    indicateur.classList.remove('active');
                } else if (index === etapeActuelle - 1) {
                    indicateur.classList.add('active');
                    indicateur.classList.remove('completed');
                } else {
                    indicateur.classList.remove('active', 'completed');
                }
            });
        }
        
        // Changer d'étape
        function changerEtape(nouvelleEtape) {
            // Valider l'étape actuelle
            if (!validerEtape(etapeActuelle)) {
                return;
            }
            
            // Masquer l'étape actuelle
            document.getElementById(etapes[etapeActuelle - 1]).classList.remove('active');
            
            // Afficher la nouvelle étape
            etapeActuelle = nouvelleEtape;
            document.getElementById(etapes[etapeActuelle - 1]).classList.add('active');
            
            // Mettre à jour la progression
            initialiserProgression();
            
            // Mettre à jour les boutons
            mettreAJourBoutons();
            
            // Mettre à jour le récapitulatif si nous sommes à l'étape 3
            if (etapeActuelle === 3) {
                mettreAJourRecapitulatif();
            }
        }
        
        // Mettre à jour les boutons de navigation
        function mettreAJourBoutons() {
            const btnPrecedent = document.getElementById('btn-precedent');
            const btnSuivant = document.getElementById('btn-suivant');
            const btnCreerFinal = document.getElementById('btn-creer-final');
            
            btnPrecedent.style.display = etapeActuelle > 1 ? 'inline-flex' : 'none';
            btnSuivant.style.display = etapeActuelle < 3 ? 'inline-flex' : 'none';
            btnCreerFinal.style.display = etapeActuelle === 3 ? 'inline-flex' : 'none';
        }
        
        // Valider une étape
        function validerEtape(numeroEtape) {
            if (numeroEtape === 1) {
                const titre = document.getElementById('titre').value.trim();
                if (!titre) {
                    alert('Veuillez saisir un titre pour le TP');
                    document.getElementById('titre').focus();
                    return false;
                }
                return true;
            }
            return true;
        }
        
        // ===== GESTION DES ÉTUDIANTS =====
        let etudiants = [];
        
        // Initialiser la gestion des étudiants
        document.addEventListener('DOMContentLoaded', function() {
            // Bouton ajouter étudiant
            document.getElementById('btn-ajouter-etudiant').addEventListener('click', function() {
                const identifiant = prompt('Saisissez le matricule ou l\'email de l\'étudiant :');
                if (identifiant && identifiant.trim()) {
                    ajouterEtudiant(identifiant.trim());
                }
            });
            
            // Gestion de la saisie en masse
            const textareaEtudiants = document.getElementById('etudiants-textarea');
            if (textareaEtudiants) {
                textareaEtudiants.addEventListener('blur', function() {
                    const lignes = this.value.split('\n');
                    let ajoutes = 0;
                    
                    lignes.forEach(ligne => {
                        const identifiant = ligne.trim();
                        if (identifiant && !etudiants.includes(identifiant)) {
                            etudiants.push(identifiant);
                            ajoutes++;
                        }
                    });
                    
                    if (ajoutes > 0) {
                        mettreAJourListeEtudiants();
                        this.value = '';
                        afficherNotification(`${ajoutes} étudiant(s) ajouté(s)`, 'info');
                    }
                });
            }
            
            // Initialiser les boutons
            mettreAJourBoutons();
            
            // Événements de navigation
            document.getElementById('btn-precedent').addEventListener('click', function() {
                if (etapeActuelle > 1) {
                    changerEtape(etapeActuelle - 1);
                }
            });
            
            document.getElementById('btn-suivant').addEventListener('click', function() {
                if (etapeActuelle < 3) {
                    changerEtape(etapeActuelle + 1);
                }
            });
            
            // Validation du formulaire final
            document.getElementById('form-creer-tp').addEventListener('submit', function(e) {
                if (!validerFormulaireFinal()) {
                    e.preventDefault();
                } else {
                    // Ajouter les étudiants au formulaire
                    const hiddenInput = document.getElementById('etudiants-hidden');
                    hiddenInput.value = JSON.stringify(etudiants);
                    
                    // Afficher un message de confirmation
                    const titre = document.getElementById('titre').value.trim();
                    if (confirm(`Êtes-vous prêt à créer le TP "${titre}" ?`)) {
                        // Le formulaire sera soumis normalement
                        document.getElementById('btn-creer-final').innerHTML = '<i class="fas fa-spinner fa-spin"></i> Création...';
                        document.getElementById('btn-creer-final').disabled = true;
                    } else {
                        e.preventDefault();
                    }
                }
            });
        });
        
        // Ajouter un étudiant
        function ajouterEtudiant(identifiant) {
            // Validation simple de l'identifiant
            if (!identifiant || identifiant.length < 3) {
                afficherNotification('Identifiant trop court', 'warning');
                return;
            }
            
            if (etudiants.includes(identifiant)) {
                afficherNotification('Cet étudiant est déjà dans la liste', 'warning');
                return;
            }
            
            etudiants.push(identifiant);
            mettreAJourListeEtudiants();
            afficherNotification('Étudiant ajouté avec succès', 'success');
        }
        
        // Supprimer un étudiant
        function supprimerEtudiant(index) {
            if (confirm('Retirer cet étudiant de la liste des participants ?')) {
                const etudiant = etudiants[index];
                etudiants.splice(index, 1);
                mettreAJourListeEtudiants();
                afficherNotification(`Étudiant "${etudiant}" retiré de la liste`, 'info');
            }
        }
        
        // Mettre à jour la liste des étudiants
        function mettreAJourListeEtudiants() {
            const liste = document.getElementById('liste-etudiants');
            const compteur = document.getElementById('compteur-etudiants');
            
            // Mettre à jour le compteur
            compteur.textContent = `${etudiants.length} étudiant(s)`;
            
            // Mettre à jour l'affichage
            if (etudiants.length === 0) {
                liste.innerHTML = `
                    <div class="etat-vide">
                        <i class="fas fa-users icone-vide"></i>
                        <p>Aucun étudiant ajouté pour le moment</p>
                        <p style="font-size: 0.9rem; margin-top: 5px;">
                            Commencez par ajouter des étudiants via le bouton ci-dessus
                        </p>
                    </div>
                `;
                return;
            }
            
            let html = '';
            etudiants.forEach((etudiant, index) => {
                html += `
                    <div class="etudiant-item">
                        <span class="identifiant-etudiant">
                            <i class="fas fa-user-graduate" style="color: #1a237e; margin-right: 8px;"></i>
                            ${etudiant}
                        </span>
                        <button type="button" class="bouton-supprimer" onclick="supprimerEtudiant(${index})">
                            <i class="fas fa-times"></i>
                        </button>
                    </div>
                `;
            });
            
            liste.innerHTML = html;
        }
        
        // Mettre à jour le récapitulatif
        function mettreAJourRecapitulatif() {
            const titre = document.getElementById('titre').value.trim();
            const module = document.getElementById('module').value.trim();
            const dateLimite = document.getElementById('date_limite').value;
            
            document.getElementById('recap-titre-text').textContent = titre || '-';
            document.getElementById('recap-module-text').textContent = module || 'Non spécifié';
            document.getElementById('recap-etudiants-text').textContent = `${etudiants.length} étudiant(s)`;
            
            if (dateLimite) {
                const date = new Date(dateLimite);
                const options = { 
                    year: 'numeric', 
                    month: 'long', 
                    day: 'numeric',
                    hour: '2-digit',
                    minute: '2-digit'
                };
                document.getElementById('recap-date-limite-text').textContent = date.toLocaleDateString('fr-FR', options);
            } else {
                document.getElementById('recap-date-limite-text').textContent = 'Non spécifiée';
            }
        }
        
        // Valider le formulaire final
        function validerFormulaireFinal() {
            const titre = document.getElementById('titre').value.trim();
            const confirmCreator = document.getElementById('confirm-creator').checked;
            
            if (!titre) {
                afficherNotification('Veuillez saisir un titre pour le TP', 'error');
                changerEtape(1);
                return false;
            }
            
            if (!confirmCreator) {
                afficherNotification('Veuillez confirmer que vous êtes l\'enseignant responsable', 'error');
                return false;
            }
            
            // Pas de validation obligatoire pour les étudiants - le TP peut être créé sans étudiants
            if (etudiants.length === 0) {
                if (!confirm('Aucun étudiant n\'a été ajouté à ce TP. Vous pourrez ajouter des étudiants plus tard. Souhaitez-vous tout de même créer le TP ?')) {
                    changerEtape(2);
                    return false;
                }
            }
            
            return true;
        }
        
        // Afficher une notification
        function afficherNotification(message, type) {
            // Créer l'élément de notification
            const notification = document.createElement('div');
            notification.className = `message-alerte message-${type}`;
            notification.innerHTML = `
                <i class="fas fa-${type === 'success' ? 'check-circle' : type === 'error' ? 'exclamation-circle' : 'info-circle'}"></i>
                ${message}
            `;
            
            // Insérer au début du contenu principal
            const contenu = document.querySelector('.contenu-principal');
            contenu.insertBefore(notification, contenu.firstChild);
            
            // Supprimer après 5 secondes
            setTimeout(() => {
                notification.remove();
            }, 5000);
        }