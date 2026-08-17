// Estime la latence réseau réelle vers le serveur (mesurée en continu) pour
// adapter automatiquement les délais d'attente et la fréquence des requêtes.
// Utile en particulier sur une connexion internet lente/instable, et quand
// plusieurs utilisateurs partagent le même tunnel (la latence observée
// augmente naturellement avec la charge, et l'estimateur s'adapte tout seul
// sans qu'il soit nécessaire de régler des valeurs fixes à la main).
// Principe identique à l'estimation du RTT en TCP (RFC 6298) :
// timeout = latence_moyenne_lissée + 4 x variance.
class EstimateurReseau {
    constructor() {
        this.rttLisse = null;   // latence moyenne lissée (ms)
        this.variance = null;   // variabilité de la latence (ms)
        this.alpha = 0.125;     // poids de la nouvelle mesure sur la moyenne
        this.beta = 0.25;       // poids de la nouvelle mesure sur la variance
    }

    enregistrerSucces(dureeMs) {
        if (this.rttLisse === null) {
            this.rttLisse = dureeMs;
            this.variance = dureeMs / 2;
        } else {
            this.variance = (1 - this.beta) * this.variance + this.beta * Math.abs(this.rttLisse - dureeMs);
            this.rttLisse = (1 - this.alpha) * this.rttLisse + this.alpha * dureeMs;
        }
    }

    // Délai d'attente recommandé pour une requête, borné entre min et max.
    timeoutRecommande(min = 5000, max = 30000) {
        if (this.rttLisse === null) {
            return 8000; // valeur prudente par défaut avant toute mesure
        }
        const calcule = this.rttLisse + 4 * this.variance;
        return Math.min(max, Math.max(min, Math.ceil(calcule)));
    }

    // Intervalle recommandé entre deux requêtes d'un même polling : plus la
    // latence observée est élevée, plus on espace les requêtes, pour ne pas
    // les empiler et aggraver la congestion sur le tunnel.
    intervalleRecommande(base = 1000, marge = 200, facteurMax = 6) {
        if (this.rttLisse === null) {
            return base;
        }
        const supplement = Math.min(base * facteurMax, this.rttLisse * 0.5);
        return Math.ceil(base + supplement + marge);
    }

    get latenceMs() {
        return this.rttLisse;
    }
}

// Classe principale pour la surveillance de température avec contrôle PI/PID et Personnalisé
class SurveillanceTemperature {
    constructor() {
        // Estimateur de latence réseau partagé (health check, données, etc.)
        this.estimateurReseau = new EstimateurReseau();

        // Initialisation des propriétés principales
        this.graphique = null;
        this.donnees = {
            etiquettes: [],
            temperatures: [],
            consignes: [],
            erreurs: [],
            sorties: []
        };
        this.nombre_max_points = 5000;
        
        // Récupérer l'état depuis le localStorage
        this.id_connexion = localStorage.getItem('idConnexionArduino');
        this.est_connecte = localStorage.getItem('estConnecteArduino') === 'true';
        this.surveillance_active = localStorage.getItem('surveillanceActiveArduino') === 'true';
        this.consigne_actuelle = parseFloat(localStorage.getItem('consigneActuelleArduino')) || 25.0;
        this.type_controleur = localStorage.getItem('typeControleurArduino') || 'none';
        
        // Paramètres des contrôleurs
        this.parametres_controleur = {
            pi: { kp: 1.0, ki: 0.1 },
            pid: { kp: 1.0, ki: 0.1, kd: 0.05 },
            custom: {} // Pour le mode personnalisé
        };
        
        const parametres_sauvegardes = localStorage.getItem('parametresControleurArduino');
        if (parametres_sauvegardes) {
            this.parametres_controleur = JSON.parse(parametres_sauvegardes);
        }
        
        // Variables pour les intervalles
        this.intervalle_surveillance = null;
        this.intervalle_rafraichissement_ports = null;
        this.intervalle_statistiques = null;
        this.intervalle_verification_serveur = null;
        this.utilisateur_interagit_ports = false;
        
        // Navigation du graphique
        this.index_debut_graphique = 0;
        this.points_visibles_graphique = 50;
        
        // Variables pour l'appui long
        this.timeout_navigation = null;
        this.interval_navigation = null;
        
        // Variables pour code personnalisé
        this.exemplesCode = {};
        this.code_personnalise_actif = false;
        this.code_personnalise_type = null; // 'pi', 'pid', ou 'mpc'
        this.code_personnalise_hash = null;
        
        // Initialisation
        this.initialiserGraphique();
        this.chargerPorts();
        this.configurerEcouteursEvenements();
        this.initialiserControleur();
        this.initialiserCurseurTemperature();
        
        // Restaurer la connexion si active
        if (this.est_connecte && this.id_connexion) {
            this.restaurerConnexion();
        } else {
            this.demarrerVerificationServeur();
        }
        
        console.log('SurveillanceTemperature initialisée');
        
        // Rendre l'instance accessible globalement
        window.surveillanceTemperatureApp = this;
        
        // Initialiser la gestion du code personnalisé
        this.initialiserCodePersonnalise();
    }

    // Vérifier périodiquement la connexion au serveur
    demarrerVerificationServeur() {
        if (this.boucle_verif_serveur_active) return;
        this.boucle_verif_serveur_active = true;
        this._bouclerVerificationServeur();
    }

    async _bouclerVerificationServeur() {
        if (!this.boucle_verif_serveur_active) return;
        
        await this.verifierServeurActif();
        
        if (!this.boucle_verif_serveur_active) return;
        
        // Intervalle adapté à la latence observée (base 5s)
        const delai = this.estimateurReseau.intervalleRecommande(5000, 1000);
        this.intervalle_verification_serveur = setTimeout(() => this._bouclerVerificationServeur(), delai);
    }

    // Arrêter la vérification du serveur
    arreterVerificationServeur() {
        this.boucle_verif_serveur_active = false;
        if (this.intervalle_verification_serveur) {
            clearTimeout(this.intervalle_verification_serveur);
            this.intervalle_verification_serveur = null;
        }
    }

    // Vérifier si le serveur est actif
    async verifierServeurActif() {
        const debut = performance.now();
        try {
            const controller = new AbortController();
            const delaiMax = this.estimateurReseau.timeoutRecommande(5000, 25000);
            const timeoutId = setTimeout(() => controller.abort(), delaiMax);
            
            const response = await fetch('/api/health', {
                method: 'GET',
                signal: controller.signal
            });
            
            clearTimeout(timeoutId);
            
            if (!response.ok) {
                throw new Error('Serveur non disponible');
            }
            
            const data = await response.json();
            if (data.status !== 'healthy') {
                throw new Error('Serveur en état anormal');
            }
            
            // Requête réussie : on affine l'estimation de latence et on
            // efface les échecs précédents
            this.estimateurReseau.enregistrerSucces(performance.now() - debut);
            this.echecs_consecutifs_serveur = 0;
            
        } catch (erreur) {
            this.echecs_consecutifs_serveur = (this.echecs_consecutifs_serveur || 0) + 1;
            console.warn(`Vérification serveur échouée (${this.echecs_consecutifs_serveur}/3) - délai actuel: ${Math.round(this.estimateurReseau.timeoutRecommande(5000, 25000))}ms:`, erreur);
            
            // On ne déclare la connexion perdue qu'après plusieurs échecs
            // d'affilée. Sur une connexion internet lente/instable, une
            // requête isolée qui traîne ne doit pas couper l'Arduino.
            if (this.echecs_consecutifs_serveur >= 3) {
                this.gererDeconnexionServeur();
            }
        }
    }

    // Gérer la déconnexion du serveur
    gererDeconnexionServeur() {
        if (this.est_connecte) {
            this.afficherMessage('Connexion au serveur perdue', 'error');
            this.deconnecterArduinoDirect('health_check_serveur_echoue');
        }
        
        this.basculerBoutonsConnexion(false);
        this.basculerBoutonsSurveillance(false);
        this.mettreAJourStatutConnexion(false, 'Serveur déconnecté');
        this.arreterSurveillanceDonnees();
        this.arreterRafraichissementAutoPorts();
    }

    // Initialiser le curseur de température
    initialiserCurseurTemperature() {
        const curseur_temperature = document.getElementById('temp-slider');
        const valeur_curseur = document.getElementById('slider-value');
        
        if (curseur_temperature && valeur_curseur) {
            if (isNaN(this.consigne_actuelle) || this.consigne_actuelle < 0 || this.consigne_actuelle > 100) {
                this.consigne_actuelle = 25.0;
            }
            
            curseur_temperature.value = this.consigne_actuelle;
            valeur_curseur.textContent = `${this.consigne_actuelle}°C`;
        }
    }

    // Initialiser le contrôleur
    initialiserControleur() {
        const selecteur_controleur = document.getElementById('controller-select');
        
        if (selecteur_controleur) {
            const optionsValides = ['none', 'pi', 'pid', 'custom'];
            if (!optionsValides.includes(this.type_controleur)) {
                this.type_controleur = 'none';
            }
            
            selecteur_controleur.value = this.type_controleur;
            this.mettreAJourAffichageControleur();
        }
    }

    // Initialiser le graphique UNIQUE
    initialiserGraphique() {
        const contexte = document.getElementById('temperatureChart').getContext('2d');
        this.graphique = new Chart(contexte, {
            type: 'line',
            data: {
                labels: this.donnees.etiquettes,
                datasets: [
                    // Température - TOUJOURS VISIBLE
                    {
                        id: 'temperature',
                        label: 'Température',
                        data: this.donnees.temperatures,
                        borderColor: '#4a55ff',
                        backgroundColor: 'rgba(74, 85, 255, 0.1)',
                        tension: 0.4,
                        fill: false,
                        pointRadius: 2,
                        borderDash: [],
                        borderWidth: 2,
                        yAxisID: 'y'
                    },
                    // Consigne - TOUJOURS VISIBLE
                    {
                        id: 'consigne',
                        label: 'Consigne',
                        data: this.donnees.consignes,
                        borderColor: '#f56565',
                        backgroundColor: 'rgba(245, 101, 101, 0.1)',
                        borderDash: [5, 5],
                        tension: 0.4,
                        fill: false,
                        pointRadius: 2,
                        borderWidth: 2,
                        yAxisID: 'y'
                    },
                    // Erreur - VISIBLE SEULEMENT EN PI/PID
                    {
                        id: 'erreur',
                        label: 'Erreur',
                        data: this.donnees.erreurs,
                        borderColor: '#e53e3e',
                        backgroundColor: 'rgba(229, 62, 62, 0.1)',
                        tension: 0.4,
                        fill: false,
                        pointRadius: 2,
                        borderDash: [3, 3],
                        borderWidth: 1.5,
                        hidden: true,
                        yAxisID: 'y'
                    },
                    // Sortie contrôleur - VISIBLE SEULEMENT EN PI/PID
                    {
                        id: 'sortie',
                        label: 'Sortie Contrôleur',
                        data: this.donnees.sorties,
                        borderColor: '#38a169',
                        backgroundColor: 'rgba(56, 161, 105, 0.1)',
                        tension: 0.4,
                        fill: false,
                        pointRadius: 2,
                        borderDash: [2, 4],
                        borderWidth: 1.5,
                        hidden: true,
                        yAxisID: 'y'
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    'y': {
                        type: 'linear',
                        display: true,
                        position: 'left',
                        title: {
                            display: true,
                            text: 'Température (°C) / Sortie (%)'
                        },
                        min: 0,
                        max: 100,
                        grid: {
                            drawOnChartArea: true
                        }
                    }
                },
                animation: { duration: 0 },
                plugins: {
                    legend: {
                        display: true,
                        position: 'top',
                        labels: {
                            usePointStyle: true,
                            pointStyle: 'line',
                            padding: 20,
                            generateLabels: (chart) => {
                                const datasets = chart.data.datasets;
                                const typeControleur = this.type_controleur;
                                
                                return datasets.map((dataset, index) => {
                                    // Filtrer les légendes selon le type de contrôleur
                                    switch(typeControleur) {
                                        case 'none':
                                            // Boucle ouverte: seulement température et consigne
                                            if (index === 0 || index === 1) {
                                                return {
                                                    text: dataset.label,
                                                    fillStyle: dataset.borderColor,
                                                    strokeStyle: dataset.borderColor,
                                                    lineWidth: dataset.borderWidth,
                                                    lineDash: dataset.borderDash || [],
                                                    hidden: !chart.isDatasetVisible(index),
                                                    index: index
                                                };
                                            }
                                            return null;
                                            
                                        case 'pi':
                                        case 'pid':
                                        case 'custom':
                                            // PI/PID/Personnalisé: toutes les courbes
                                            return {
                                                text: dataset.label,
                                                fillStyle: dataset.borderColor,
                                                strokeStyle: dataset.borderColor,
                                                lineWidth: dataset.borderWidth,
                                                lineDash: dataset.borderDash || [],
                                                hidden: !chart.isDatasetVisible(index),
                                                index: index
                                            };
                                            
                                        default:
                                            return null;
                                    }
                                }).filter(label => label !== null);
                            }
                        },
                        onClick: (e, legendItem, legend) => {
                            const index = legendItem.index;
                            const meta = this.graphique.getDatasetMeta(index);
                            
                            // Toujours garder température et consigne visibles
                            if (index === 0 || index === 1) {
                                return;
                            }
                            
                            meta.hidden = meta.hidden === null ? !this.graphique.data.datasets[index].hidden : null;
                            this.graphique.update();
                        }
                    },
                    tooltip: {
                        mode: 'index',
                        intersect: false
                    }
                },
                interaction: {
                    mode: 'nearest',
                    axis: 'x',
                    intersect: false
                }
            }
        });
        
        // Initialiser la légende selon le type de contrôleur
        this.mettreAJourLegende();
    }

    // Mettre à jour la légende selon le type de contrôleur
    mettreAJourLegende() {
        if (!this.graphique) return;
        
        // Mettre à jour l'affichage des datasets selon le type de contrôleur
        const datasets = this.graphique.data.datasets;
        
        switch(this.type_controleur) {
            case 'none':
                datasets[0].hidden = false; // Température
                datasets[1].hidden = false; // Consigne
                datasets[2].hidden = true;  // Erreur (cachée)
                datasets[3].hidden = true;  // Sortie (cachée)
                break;
                
            case 'pi':
            case 'pid':
            case 'custom':
                datasets[0].hidden = false; // Température
                datasets[1].hidden = false; // Consigne
                datasets[2].hidden = false; // Erreur
                datasets[3].hidden = false; // Sortie
                break;
        }
        
        this.graphique.update();
        
        // Appliquer le style de ligne pour les légendes
        setTimeout(() => {
            const legendItems = document.querySelectorAll('.chartjs-legend .chartjs-legend-item');
            
            legendItems.forEach(item => {
                const pointMarker = item.querySelector('.chartjs-legend-marker');
                if (pointMarker) {
                    // Supprimer le point existant
                    pointMarker.remove();
                    
                    // Créer une ligne à la place
                    const lineMarker = document.createElement('div');
                    lineMarker.style.cssText = `
                        width: 20px;
                        height: 2px;
                        margin-right: 8px;
                        display: inline-block;
                        vertical-align: middle;
                    `;
                    
                    // Trouver la couleur de la ligne
                    const labelText = item.textContent;
                    let borderColor = '#4a55ff';
                    let borderDash = '';
                    let borderWidth = '2px';
                    
                    switch(labelText) {
                        case 'Température':
                            borderColor = '#4a55ff';
                            borderDash = 'solid';
                            borderWidth = '2px';
                            break;
                        case 'Consigne':
                            borderColor = '#f56565';
                            borderDash = '5px, 5px';
                            borderWidth = '2px';
                            break;
                        case 'Erreur':
                            borderColor = '#e53e3e';
                            borderDash = '3px, 3px';
                            borderWidth = '1.5px';
                            break;
                        case 'Sortie Contrôleur':
                            borderColor = '#38a169';
                            borderDash = '2px, 4px';
                            borderWidth = '1.5px';
                            break;
                    }
                    
                    lineMarker.style.backgroundColor = borderColor;
                    lineMarker.style.borderTop = `${borderWidth} ${borderDash} ${borderColor}`;
                    
                    // Insérer la ligne avant le texte
                    const labelTextElement = item.querySelector('.chartjs-legend-text');
                    if (labelTextElement) {
                        item.insertBefore(lineMarker, labelTextElement);
                    }
                }
            });
        }, 500);
    }

    // Restaurer une connexion existante
    async restaurerConnexion() {
        this.mettreAJourStatutConnexion(true, 'Restauration...');
        this.basculerBoutonsConnexion(true);
        
        this.initialiserControleur();
        this.initialiserCurseurTemperature();
        
        try {
            const controller = new AbortController();
            const timeoutId = setTimeout(() => controller.abort(), 3000);
            
            const reponse = await fetch(`/api/check_connection?connection_id=${this.id_connexion}`, {
                signal: controller.signal
            });
            clearTimeout(timeoutId);
            
            const resultat = await reponse.json();
            
            if (resultat.active) {
                if (this.surveillance_active) {
                    this.demarrerSurveillanceDonnees();
                }
                this.afficherMessage('Connexion restaurée', 'success');
                this.mettreAJourStatutConnexion(true, 'Connecté');
                
                // Envoyer le mode contrôleur
                await this.envoyerModeControleur();
                
                // Charger les données historiques
                await this.chargerDonneesHistoriques();
                
                if (this.surveillance_active) {
                    this.allerFinDonnees();
                }
                
                this.demarrerVerificationServeur();
                this.mettreAJourLegende();
                
                // Vérifier l'état du code personnalisé
                if (this.type_controleur === 'custom') {
                    await this.verifierCodePersonnaliseActif();
                }
            } else {
                this.gererConnexionPerdue('restauration_check_connection_inactive');
            }
        } catch (erreur) {
            console.error('Erreur restauration:', erreur);
            this.gererConnexionPerdue('restauration_exception:' + erreur.message);
        }
    }

    // Charger les données historiques
    async chargerDonneesHistoriques() {
        if (!this.est_connecte || !this.id_connexion) return;
        
        try {
            const reponse = await fetch(`/api/historical_data?connection_id=${this.id_connexion}&limit=${this.nombre_max_points}`);
            const donneesHistoriques = await reponse.json();
            
            if (donneesHistoriques.labels && donneesHistoriques.labels.length > 0) {
                this.donnees.etiquettes = donneesHistoriques.labels;
                this.donnees.temperatures = donneesHistoriques.temperatures;
                this.donnees.consignes = donneesHistoriques.consignes;
                this.donnees.erreurs = donneesHistoriques.errors || [];
                this.donnees.sorties = donneesHistoriques.outputs || [];
                
                if (this.surveillance_active) {
                    this.allerFinDonnees();
                }
                
                this.mettreAJourVueGraphique();
                this.mettreAJourLegende();
                
                console.log(`Données historiques chargées: ${donneesHistoriques.labels.length} points`);
            }
        } catch (erreur) {
            console.error('Erreur chargement données historiques:', erreur);
        }
    }

    // Gérer une connexion perdue
    gererConnexionPerdue(raison = 'non spécifiée') {
        console.warn('Connexion perdue - raison:', raison);
        this.afficherMessage('Connexion perdue', 'error');
        this.deconnecterArduinoDirect(raison);
    }

    // Sauvegarder l'état
    sauvegarderEtatConnexion() {
        localStorage.setItem('idConnexionArduino', this.id_connexion);
        localStorage.setItem('estConnecteArduino', this.est_connecte.toString());
        localStorage.setItem('surveillanceActiveArduino', this.surveillance_active.toString());
        localStorage.setItem('consigneActuelleArduino', this.consigne_actuelle.toString());
        localStorage.setItem('typeControleurArduino', this.type_controleur);
        localStorage.setItem('parametresControleurArduino', JSON.stringify(this.parametres_controleur));
    }

    // Effacer l'état
    effacerEtatConnexion() {
        localStorage.removeItem('idConnexionArduino');
        localStorage.removeItem('estConnecteArduino');
        localStorage.removeItem('surveillanceActiveArduino');
        localStorage.removeItem('consigneActuelleArduino');
        localStorage.removeItem('typeControleurArduino');
        localStorage.removeItem('parametresControleurArduino');
        this.consigne_actuelle = 25.0;
    }

    // Charger les ports Arduino
    async chargerPorts() {
        try {
            this.afficherChargementPorts(true);
            const reponse = await fetch('/api/ports');
            const ports = await reponse.json();
            this.mettreAJourListePorts(ports);
            this.afficherChargementPorts(false);
        } catch (erreur) {
            console.error('Erreur chargement ports:', erreur);
            this.afficherChargementPorts(false);
            this.afficherMessage('Erreur de chargement des ports', 'error');
        }
    }

    // Démarrer le rafraîchissement automatique des ports
    demarrerRafraichissementAutoPorts() {
        if (!this.intervalle_rafraichissement_ports) {
            this.intervalle_rafraichissement_ports = setInterval(() => {
                if (!this.utilisateur_interagit_ports) {
                    this.chargerPorts();
                }
            }, this.est_connecte ? 5000 : 3000);
        }
    }

    // Arrêter le rafraîchissement automatique des ports
    arreterRafraichissementAutoPorts() {
        if (this.intervalle_rafraichissement_ports) {
            clearInterval(this.intervalle_rafraichissement_ports);
            this.intervalle_rafraichissement_ports = null;
        }
    }

    // Afficher l'état de chargement des ports
    afficherChargementPorts(chargement) {
        const bouton_rafraichir = document.getElementById('refresh-ports');
        if (chargement) {
            bouton_rafraichir.innerHTML = 'Chargement...';
            bouton_rafraichir.disabled = true;
        } else {
            bouton_rafraichir.innerHTML = '🔄 Actualiser les ports';
            bouton_rafraichir.disabled = false;
        }
    }

    // Mettre à jour la liste des ports
    mettreAJourListePorts(ports) {
        const selecteur_port = document.getElementById('port-select');
        selecteur_port.innerHTML = '<option value="">Sélectionnez un port Arduino</option>';
        
        const ports_disponibles = ports.filter(port => !port.en_utilisation);
        const ports_utilises = ports.filter(port => port.en_utilisation);
        
        if (ports_disponibles.length === 0) {
            const option = document.createElement('option');
            option.value = "";
            option.textContent = "Aucun port Arduino disponible";
            option.disabled = true;
            selecteur_port.appendChild(option);
        } else {
            ports_disponibles.forEach(port => {
                const option = document.createElement('option');
                option.value = port.port;
                option.textContent = `${port.port} - ${port.description}`;
                selecteur_port.appendChild(option);
            });
        }
        
        if (ports_utilises.length > 0) {
            const separateur = document.createElement('option');
            separateur.disabled = true;
            separateur.textContent = "────────── Ports occupés ──────────";
            selecteur_port.appendChild(separateur);
            
            ports_utilises.forEach(port => {
                const option = document.createElement('option');
                option.value = port.port;
                option.textContent = `${port.port} - ${port.description} (Occupé)`;
                option.disabled = true;
                selecteur_port.appendChild(option);
            });
        }
        
        this.mettreAJourCompteurPorts(ports_disponibles.length, ports.length);
    }

    // Mettre à jour le compteur de ports
    mettreAJourCompteurPorts(disponibles, total) {
        const element_compteur = document.getElementById('port-count') || this.creerElementCompteurPorts();
        element_compteur.textContent = `${disponibles}/${total} ports disponibles`;
    }

    // Créer l'élément de compteur de ports
    creerElementCompteurPorts() {
        const element_compteur = document.createElement('div');
        element_compteur.id = 'port-count';
        element_compteur.style.cssText = `
            font-size: 0.8rem;
            color: #718096;
            margin-top: 8px;
            text-align: center;
            font-weight: 500;
            padding: 4px 8px;
            background-color: #f8fafc;
            border-radius: 12px;
            border: 1px solid #e2e8f0;
        `;
        
        const carte_config = document.getElementById('config-arduino');
        carte_config.appendChild(element_compteur);
        
        return element_compteur;
    }

    // Configurer les écouteurs d'événements
    configurerEcouteursEvenements() {
        // Gestion des ports
        document.getElementById('refresh-ports').addEventListener('click', () => {
            this.chargerPorts();
        });

        document.getElementById('start-btn').addEventListener('click', () => {
            this.connecterArduino();
        });

        const selecteur_port = document.getElementById('port-select');
        
        selecteur_port.addEventListener('focus', () => {
            this.utilisateur_interagit_ports = true;
            this.arreterRafraichissementAutoPorts();
        });

        selecteur_port.addEventListener('blur', () => {
            setTimeout(() => {
                this.utilisateur_interagit_ports = false;
                this.demarrerRafraichissementAutoPorts();
            }, 2000);
        });

        selecteur_port.addEventListener('change', () => {
            this.utilisateur_interagit_ports = true;
            this.arreterRafraichissementAutoPorts();
            
            setTimeout(() => {
                this.utilisateur_interagit_ports = false;
                this.demarrerRafraichissementAutoPorts();
            }, 5000);
        });

        // Gestion du monitoring
        document.getElementById('stop-monitoring-btn').addEventListener('click', () => {
            this.arreterSurveillance();
        });

        document.getElementById('disconnect-btn').addEventListener('click', () => {
            this.deconnecterArduino();
        });

        // Gestion du contrôleur
        const selecteur_controleur = document.getElementById('controller-select');
        
        if (selecteur_controleur) {
            const optionsValides = ['none', 'pi', 'pid', 'custom'];
            if (!optionsValides.includes(this.type_controleur)) {
                this.type_controleur = 'none';
            }
            
            selecteur_controleur.value = this.type_controleur;
        }
        
        this.mettreAJourAffichageControleur();
        
        selecteur_controleur.addEventListener('change', async (e) => {
            const nouveauMode = e.target.value;
            
            // Si on sélectionne "Personnalisé", vérifier qu'un code est actif
            if (nouveauMode === 'custom') {
                const estActif = await this.verifierCodePersonnaliseActif();
                if (estActif) {
                    this.type_controleur = 'custom';
                    this.mettreAJourAffichageControleur();
                    this.sauvegarderEtatConnexion();
                    
                    // Envoyer immédiatement le mode au serveur si connecté
                    if (this.est_connecte && this.id_connexion) {
                        this.envoyerModeControleur();
                    }
                } else {
                    // Afficher un message et revenir au mode précédent
                    this.afficherMessage('Aucun code personnalisé actif. Veuillez d\'abord activer un code dans l\'éditeur.', 'warning');
                    selecteur_controleur.value = this.type_controleur; // Revenir au mode précédent
                }
            } else {
                // Pour les autres modes (none, pi, pid)
                this.type_controleur = nouveauMode;
                this.mettreAJourAffichageControleur();
                this.sauvegarderEtatConnexion();
                
                // Envoyer immédiatement le mode au serveur si connecté
                if (this.est_connecte && this.id_connexion) {
                    this.envoyerModeControleur();
                }
            }
        });

        document.getElementById('appliquer-parametres').addEventListener('click', () => {
            this.appliquerParametresControleur();
        });

        // Gestion de la consigne
        const curseur_temperature = document.getElementById('temp-slider');
        const valeur_curseur = document.getElementById('slider-value');
        
        if (curseur_temperature && valeur_curseur) {
            curseur_temperature.value = this.consigne_actuelle;
            valeur_curseur.textContent = `${this.consigne_actuelle}°C`;
            
            curseur_temperature.addEventListener('input', () => {
                const valeur = parseFloat(curseur_temperature.value);
                valeur_curseur.textContent = `${valeur}°C`;
            });
        }

        document.getElementById('apply-consigne').addEventListener('click', () => {
            this.mettreAJourConsigne();
        });

        // Gestion de l'export
        document.getElementById('export-btn').addEventListener('click', () => {
            this.exporterDonneesCSV('complet');
        });

        document.getElementById('export-btn').addEventListener('dblclick', () => {
            this.exporterDonneesCSV('resume');
        });

        // Gestion du graphique
        document.getElementById('chart-prev').addEventListener('click', () => {
            this.naviguerGraphique('precedent');
        });

        document.getElementById('chart-next').addEventListener('click', () => {
            this.naviguerGraphique('suivant');
        });

        document.getElementById('chart-play').addEventListener('click', () => {
            this.demarrerSurveillance();
        });

        document.getElementById('chart-zoom-in').addEventListener('click', () => {
            this.zoomerGraphique('agrandir');
        });

        document.getElementById('chart-zoom-out').addEventListener('click', () => {
            this.zoomerGraphique('reduire');
        });

        document.getElementById('chart-reset').addEventListener('click', () => {
            this.reinitialiserVueGraphique();
        });

        document.getElementById('chart-first').addEventListener('click', () => {
            this.allerDebutDonnees();
        });

        document.getElementById('chart-last').addEventListener('click', () => {
            this.allerFinDonnees();
        });

        // Gestion du bouton code personnalisé
        document.getElementById('custom-code-btn').addEventListener('click', () => {
            window.location.href = '/code_personnalise';
        });

        // Appui long pour navigation rapide
        this.configurerAppuiLongBoutons();

        this.basculerBoutonsConnexion(this.est_connecte);
        this.basculerBoutonsSurveillance(this.surveillance_active);
        
        this.mettreAJourVueGraphique();
        this.demarrerRafraichissementAutoPorts();
    }

    // Configurer l'appui long sur les boutons de navigation
    configurerAppuiLongBoutons() {
        const boutonPrev = document.getElementById('chart-prev');
        const boutonNext = document.getElementById('chart-next');
        
        // Appui long sur ◀
        boutonPrev.addEventListener('mousedown', () => {
            this.timeout_navigation = setTimeout(() => {
                this.interval_navigation = setInterval(() => {
                    this.naviguerGraphique('precedent');
                }, 200);
            }, 500);
        });

        boutonPrev.addEventListener('mouseup', () => {
            this.arreterAppuiLong();
        });

        boutonPrev.addEventListener('mouseleave', () => {
            this.arreterAppuiLong();
        });

        // Appui long sur ▶
        boutonNext.addEventListener('mousedown', () => {
            this.timeout_navigation = setTimeout(() => {
                this.interval_navigation = setInterval(() => {
                    this.naviguerGraphique('suivant');
                }, 200);
            }, 500);
        });

        boutonNext.addEventListener('mouseup', () => {
            this.arreterAppuiLong();
        });

        boutonNext.addEventListener('mouseleave', () => {
            this.arreterAppuiLong();
        });
    }

    // Arrêter l'appui long
    arreterAppuiLong() {
        if (this.timeout_navigation) {
            clearTimeout(this.timeout_navigation);
            this.timeout_navigation = null;
        }
        if (this.interval_navigation) {
            clearInterval(this.interval_navigation);
            this.interval_navigation = null;
        }
    }

    // Mettre à jour l'affichage du contrôleur
    mettreAJourAffichageControleur() {
        const element_mode = document.getElementById('data-mode');
        const selecteur_controleur = document.getElementById('controller-select');
        
        if (selecteur_controleur && selecteur_controleur.value !== this.type_controleur) {
            selecteur_controleur.value = this.type_controleur;
        }
        
        switch(this.type_controleur) {
            case 'none':
                element_mode.textContent = 'Boucle ouverte';
                break;
            case 'pi':
                element_mode.textContent = 'Contrôleur PI';
                break;
            case 'pid':
                element_mode.textContent = 'Contrôleur PID';
                break;
            case 'custom':
                element_mode.textContent = 'Contrôleur Personnalisé';
                break;
            default:
                this.type_controleur = 'none';
                element_mode.textContent = 'Boucle ouverte';
                if (selecteur_controleur) {
                    selecteur_controleur.value = 'none';
                }
        }
        
        this.mettreAJourAffichageParametresControleur();
        this.mettreAJourLegende();
    }

    // Mettre à jour l'affichage des paramètres
    mettreAJourAffichageParametresControleur() {
        const conteneur_parametres = document.getElementById('parametres-controleur');
        const parametres_pi = document.getElementById('parametres-pi');
        const parametres_pid = document.getElementById('parametres-pid');
        const bouton_appliquer = document.getElementById('appliquer-parametres');
        const consigne_card = document.getElementById('consigne');

        parametres_pi.style.display = 'none';
        parametres_pid.style.display = 'none';
        conteneur_parametres.style.display = 'none';
        bouton_appliquer.style.display = 'none';

        switch(this.type_controleur) {
            case 'pi':
                conteneur_parametres.style.display = 'block';
                parametres_pi.style.display = 'block';
                bouton_appliquer.style.display = 'block';
                
                document.getElementById('kp-pi').value = this.parametres_controleur.pi.kp;
                document.getElementById('ki-pi').value = this.parametres_controleur.pi.ki;
                break;
                
            case 'pid':
                conteneur_parametres.style.display = 'block';
                parametres_pid.style.display = 'block';
                bouton_appliquer.style.display = 'block';
                
                document.getElementById('kp-pid').value = this.parametres_controleur.pid.kp;
                document.getElementById('ki-pid').value = this.parametres_controleur.pid.ki;
                document.getElementById('kd-pid').value = this.parametres_controleur.pid.kd;
                break;
                
            case 'custom':
                // Pour le mode personnalisé, cacher les paramètres
                conteneur_parametres.style.display = 'none';
                if (consigne_card) {
                    consigne_card.style.display = 'block';
                }
                break;
        }
    }

    // Appliquer les paramètres du contrôleur
    async appliquerParametresControleur() {
        let parametres = {};
        
        switch(this.type_controleur) {
            case 'pi':
                parametres = {
                    kp: parseFloat(document.getElementById('kp-pi').value),
                    ki: parseFloat(document.getElementById('ki-pi').value)
                };
                break;
                
            case 'pid':
                parametres = {
                    kp: parseFloat(document.getElementById('kp-pid').value),
                    ki: parseFloat(document.getElementById('ki-pid').value),
                    kd: parseFloat(document.getElementById('kd-pid').value)
                };
                break;
                
            case 'none':
            case 'custom':
                this.afficherMessage('Aucun paramètre à appliquer', 'info');
                return;
        }

        if (Object.values(parametres).some(valeur => isNaN(valeur) || valeur < 0)) {
            this.afficherMessage('Paramètres invalides', 'error');
            return;
        }
        
        this.parametres_controleur[this.type_controleur] = parametres;
        localStorage.setItem('parametresControleurArduino', JSON.stringify(this.parametres_controleur));
        
        if (this.est_connecte && this.id_connexion) {
            await this.envoyerParametresControleur();
        }
        
        this.afficherMessage('Paramètres appliqués', 'success');
    }

    // Envoyer le mode de contrôleur
    async envoyerModeControleur() {
        if (!this.est_connecte || !this.id_connexion) return;
        
        try {
            // Pour le mode custom, on envoie aussi le type de code (pi/pid/mpc)
            let controllerTypeToSend = this.type_controleur;
            let codeType = null;
            
            if (this.type_controleur === 'custom') {
                controllerTypeToSend = 'custom';
                codeType = this.code_personnalise_type || 'pi'; // Valeur par défaut
            }
            
            const reponse = await fetch('/api/set_controller_mode', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    connection_id: this.id_connexion,
                    controller_type: controllerTypeToSend,
                    custom_code_type: codeType
                })
            });

            const resultat = await reponse.json();
            
            if (resultat.success) {
                console.log(`Mode contrôleur envoyé: ${this.type_controleur}`);
                this.afficherMessage(`Mode ${this.type_controleur} activé`, 'success');
            } else {
                console.error('Erreur mode contrôleur:', resultat.message);
                this.afficherMessage(resultat.message, 'error');
            }
        } catch (erreur) {
            console.error('Erreur envoi mode contrôleur:', erreur);
            this.afficherMessage('Erreur envoi du mode', 'error');
        }
    }

    // Envoyer les paramètres du contrôleur
    async envoyerParametresControleur() {
        if (!this.est_connecte || !this.id_connexion) return;
        
        try {
            const parametres = this.parametres_controleur[this.type_controleur];
            const reponse = await fetch('/api/set_controller_params', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    connection_id: this.id_connexion,
                    controller_type: this.type_controleur,
                    parameters: parametres
                })
            });

            const resultat = await reponse.json();
            
            if (resultat.success) {
                console.log(`Paramètres envoyés:`, parametres);
                this.afficherMessage('Paramètres du contrôleur appliqués', 'success');
            } else {
                this.afficherMessage('Erreur envoi paramètres: ' + resultat.message, 'error');
            }
        } catch (erreur) {
            this.afficherMessage('Erreur envoi des paramètres', 'error');
        }
    }

    // Exporter les données en CSV
    async exporterDonneesCSV(exportType = 'complet') {
        if (!this.est_connecte || !this.id_connexion) {
            this.afficherMessage('Veuillez d\'abord vous connecter', 'warning');
            return;
        }

        try {
            this.afficherMessage('Génération du fichier CSV...', 'info');
            
            const reponse = await fetch('/api/export_data', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    connection_id: this.id_connexion,
                    export_type: exportType
                })
            });

            if (!reponse.ok) {
                throw new Error('Erreur lors de l\'export');
            }

            const blob = await reponse.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.style.display = 'none';
            a.href = url;
            
            const date = new Date().toISOString().slice(0, 19).replace(/:/g, '-');
            const typeLabel = exportType === 'complet' ? 'historique_complet' : 'donnees_actuelles';
            a.download = `${typeLabel}_temperature_${date}.csv`;
            
            document.body.appendChild(a);
            a.click();
            window.URL.revokeObjectURL(url);
            document.body.removeChild(a);
            
            this.afficherMessage('Données exportées avec succès', 'success');
            
        } catch (erreur) {
            console.error('Erreur export CSV:', erreur);
            this.afficherMessage('Erreur lors de l\'export', 'error');
        }
    }

    // Afficher le pop-up de confirmation avant déconnexion
    afficherPopupExportAvantDeconnexion() {
        const popup = document.createElement('div');
        popup.className = 'export-popup-overlay';
        
        popup.innerHTML = `
            <div class="export-popup-content">
                <h3 class="export-popup-title">Exporter les données</h3>
                <p class="export-popup-message">
                    Souhaitez-vous exporter vos données avant de vous déconnecter ?
                </p>
                <div class="export-popup-buttons">
                    <button id="export-complet" class="export-popup-btn export-popup-btn-complet">
                        Exporter l'historique complet
                    </button>
                    <button id="export-resume" class="export-popup-btn export-popup-btn-resume">
                        Exporter les données actuelles
                    </button>
                    <button id="deconnecter-sans-export" class="export-popup-btn export-popup-btn-deconnecter">
                        Déconnecter sans exporter
                    </button>
                    <button id="annuler-deconnexion" class="export-popup-btn export-popup-btn-annuler">
                        Annuler
                    </button>
                </div>
            </div>
        `;

        document.body.appendChild(popup);

        document.getElementById('export-complet').addEventListener('click', async () => {
            await this.exporterDonneesCSV('complet');
            this.fermerPopupEtDeconnecter(popup);
        });

        document.getElementById('export-resume').addEventListener('click', async () => {
            await this.exporterDonneesCSV('resume');
            this.fermerPopupEtDeconnecter(popup);
        });

        document.getElementById('deconnecter-sans-export').addEventListener('click', () => {
            this.fermerPopupEtDeconnecter(popup);
        });

        document.getElementById('annuler-deconnexion').addEventListener('click', () => {
            document.body.removeChild(popup);
        });
    }

    // Fermer le pop-up et déconnecter
    fermerPopupEtDeconnecter(popup) {
        if (popup && popup.parentNode) {
            document.body.removeChild(popup);
        }
        this.deconnecterArduinoDirect();
    }

    // Déconnexion avec pop-up
    async deconnecterArduino() {
        if (!this.id_connexion) return;
        this.afficherPopupExportAvantDeconnexion();
    }

    // Déconnexion directe
    async deconnecterArduinoDirect(raison = 'manuelle') {
        if (!this.id_connexion) return;

        try {
            await fetch('/api/disconnect', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    connection_id: this.id_connexion,
                    reason: raison
                })
            });
        } catch (erreur) {
            console.error('Erreur déconnexion:', erreur);
        } finally {
            this.est_connecte = false;
            this.surveillance_active = false;
            this.id_connexion = null;
            this.code_personnalise_actif = false;
            this.code_personnalise_type = null;
            this.code_personnalise_hash = null;
            
            this.arreterSurveillanceDonnees();
            this.arreterVerificationServeur();
            this.effacerEtatConnexion();
            this.mettreAJourStatutConnexion(false, 'Déconnecté');
            this.basculerBoutonsConnexion(false);
            this.afficherMessage('Déconnecté', 'info');
            
            setTimeout(() => {
                this.utilisateur_interagit_ports = false;
                this.chargerPorts();
                this.demarrerRafraichissementAutoPorts();
                this.initialiserCurseurTemperature();
            }, 500);
        }
    }

    // Récupérer les statistiques des données
    async recupererStatistiquesDonnees() {
        if (!this.est_connecte || !this.id_connexion) return;

        try {
            const reponse = await fetch(`/api/data_stats?connection_id=${this.id_connexion}`);
            const stats = await reponse.json();
            
            console.log(`Statistiques: ${stats.total_points} points - ${stats.periode}`);
            this.afficherCompteurDonnees(stats.total_points);
            
        } catch (erreur) {
            console.error('Erreur statistiques:', erreur);
        }
    }

    // Afficher le compteur de données
    afficherCompteurDonnees(totalPoints) {
        let compteur = document.getElementById('data-counter');
        if (!compteur) {
            compteur = document.createElement('div');
            compteur.id = 'data-counter';
            compteur.style.cssText = `
                position: fixed;
                bottom: 20px;
                right: 20px;
                background: #4a55ff;
                color: white;
                padding: 10px 15px;
                border-radius: 20px;
                font-size: 0.8rem;
                font-weight: 500;
                box-shadow: 0 4px 12px rgba(74, 85, 255, 0.3);
                z-index: 1000;
                font-family: 'Poppins', sans-serif;
            `;
            document.body.appendChild(compteur);
        }
        
        compteur.textContent = `${totalPoints} points enregistrés`;
        compteur.title = 'Nombre total de points de données enregistrés';
    }

    // Tester l'enregistrement
    async testerEnregistrement() {
        if (!this.est_connecte || !this.id_connexion) {
            console.log('Non connecté');
            return;
        }

        try {
            const reponse = await fetch(`/api/debug_data?connection_id=${this.id_connexion}`);
            const debug = await reponse.json();
            console.log('🔍 DEBUG Données:', debug);
            
            if (debug.donnees_temps_reel.total_points > 0) {
                this.afficherMessage(`✅ ${debug.donnees_temps_reel.total_points} points enregistrés`, 'success');
            } else {
                this.afficherMessage('Aucune donnée enregistrée', 'error');
            }
        } catch (erreur) {
            console.error('Erreur test:', erreur);
        }
    }

    // NAVIGATION DU GRAPHIQUE
    naviguerGraphique(direction) {
        if (this.donnees.etiquettes.length === 0) {
            console.log('Aucune donnée à afficher');
            return;
        }
        
        const totalPoints = this.donnees.etiquettes.length;
        const pasNavigation = 10;
        
        if (direction === 'precedent') {
            this.index_debut_graphique = Math.max(0, this.index_debut_graphique - pasNavigation);
            console.log(`◀ Navigation: index ${this.index_debut_graphique}/${totalPoints}`);
        } else if (direction === 'suivant') {
            const maxIndex = Math.max(0, totalPoints - this.points_visibles_graphique);
            this.index_debut_graphique = Math.min(maxIndex, this.index_debut_graphique + pasNavigation);
            console.log(`▶ Navigation: index ${this.index_debut_graphique}/${totalPoints}`);
        }
        
        this.mettreAJourVueGraphique();
    }

    // Aller au début des données
    allerDebutDonnees() {
        if (this.donnees.etiquettes.length === 0) return;
        
        this.index_debut_graphique = 0;
        console.log('Aller au début des données');
        this.mettreAJourVueGraphique();
    }

    // Aller à la fin des données
    allerFinDonnees() {
        if (this.donnees.etiquettes.length === 0) return;
        
        const totalPoints = this.donnees.etiquettes.length;
        this.index_debut_graphique = Math.max(0, totalPoints - this.points_visibles_graphique);
        console.log('Aller à la fin des données');
        this.mettreAJourVueGraphique();
    }

    // Zoom du graphique
    zoomerGraphique(direction) {
        if (direction === 'agrandir' && this.points_visibles_graphique > 10) {
            this.points_visibles_graphique = Math.max(10, this.points_visibles_graphique - 10);
        } else if (direction === 'reduire' && this.points_visibles_graphique < 100) {
            this.points_visibles_graphique = Math.min(100, this.points_visibles_graphique + 10);
        }
        
        const totalPoints = this.donnees.etiquettes.length;
        if (this.index_debut_graphique > totalPoints - this.points_visibles_graphique) {
            this.index_debut_graphique = Math.max(0, totalPoints - this.points_visibles_graphique);
        }
        
        console.log(`Zoom ${direction}: ${this.points_visibles_graphique} points visibles`);
        this.mettreAJourVueGraphique();
    }

    // Réinitialiser la vue du graphique
    reinitialiserVueGraphique() {
        if (this.donnees.etiquettes.length === 0) {
            console.log('Aucune donnée pour réinitialiser la vue');
            return;
        }
        
        if (this.surveillance_active) {
            this.allerFinDonnees();
        }
        
        console.log(`Réinitialisation: surveillance=${this.surveillance_active}`);
    }

    // Mettre à jour l'affichage du graphique
    mettreAJourVueGraphique() {
        if (this.donnees.etiquettes.length === 0) {
            console.log('Aucune donnée à afficher');
            return;
        }
        
        const totalPoints = this.donnees.etiquettes.length;
        const index_debut = Math.min(this.index_debut_graphique, totalPoints - 1);
        const index_fin = Math.min(index_debut + this.points_visibles_graphique, totalPoints);
        
        if (index_debut >= index_fin && totalPoints > 0) {
            this.index_debut_graphique = Math.max(0, totalPoints - this.points_visibles_graphique);
            return this.mettreAJourVueGraphique();
        }
        
        const etiquettes_visibles = this.donnees.etiquettes.slice(index_debut, index_fin);
        const temperatures_visibles = this.donnees.temperatures.slice(index_debut, index_fin);
        const consignes_visibles = this.donnees.consignes.slice(index_debut, index_fin);
        const erreurs_visibles = this.donnees.erreurs.slice(index_debut, index_fin);
        const sorties_visibles = this.donnees.sorties.slice(index_debut, index_fin);
        
        console.log(`Affichage: points ${index_debut + 1} à ${index_fin} sur ${totalPoints} (surveillance: ${this.surveillance_active})`);
        
        if (this.graphique) {
            this.graphique.data.labels = etiquettes_visibles;
            this.graphique.data.datasets[0].data = temperatures_visibles;
            this.graphique.data.datasets[1].data = consignes_visibles;
            this.graphique.data.datasets[2].data = erreurs_visibles;
            this.graphique.data.datasets[3].data = sorties_visibles;
            this.graphique.update('none');
        }
        
        this.mettreAJourEtatBoutonsNavigation();
    }

    // Mettre à jour l'état des boutons de navigation
    mettreAJourEtatBoutonsNavigation() {
        const totalPoints = this.donnees.etiquettes.length;
        const boutonPrev = document.getElementById('chart-prev');
        const boutonNext = document.getElementById('chart-next');
        const boutonFirst = document.getElementById('chart-first');
        const boutonLast = document.getElementById('chart-last');
        
        if (totalPoints === 0) {
            if (boutonPrev) boutonPrev.disabled = true;
            if (boutonNext) boutonNext.disabled = true;
            if (boutonFirst) boutonFirst.disabled = true;
            if (boutonLast) boutonLast.disabled = true;
            return;
        }
        
        if (boutonPrev) {
            boutonPrev.disabled = this.index_debut_graphique === 0;
        }
        
        if (boutonNext) {
            const peutAllerDroite = this.index_debut_graphique < totalPoints - this.points_visibles_graphique;
            boutonNext.disabled = !peutAllerDroite;
        }
        
        if (boutonFirst) {
            boutonFirst.disabled = this.index_debut_graphique === 0;
        }
        
        if (boutonLast) {
            const estALaFin = this.index_debut_graphique >= totalPoints - this.points_visibles_graphique;
            boutonLast.disabled = estALaFin;
        }
    }

    // Démarrer la surveillance
    async demarrerSurveillance() {
        if (!this.est_connecte || !this.id_connexion) {
            this.afficherMessage('Veuillez d\'abord vous connecter', 'warning');
            return;
        }

        try {
            const reponse = await fetch('/api/control_monitoring', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    connection_id: this.id_connexion,
                    action: 'start'
                })
            });

            const resultat = await reponse.json();

            if (resultat.success) {
                this.surveillance_active = true;
                this.basculerBoutonsSurveillance(true);
                this.afficherMessage('Surveillance démarrée', 'success');
                this.sauvegarderEtatConnexion();
                this.demarrerSurveillanceDonnees();
                this.allerFinDonnees();
            } else {
                this.afficherMessage(resultat.message, 'error');
            }
        } catch (erreur) {
            console.error('Erreur démarrage surveillance:', erreur);
            this.afficherMessage('Erreur de démarrage', 'error');
        }
    }

    // Arrêter la surveillance
    async arreterSurveillance() {
        if (!this.est_connecte || !this.id_connexion) return;

        try {
            const reponse = await fetch('/api/control_monitoring', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    connection_id: this.id_connexion,
                    action: 'stop'
                })
            });

            const resultat = await reponse.json();

            if (resultat.success) {
                this.surveillance_active = false;
                this.basculerBoutonsSurveillance(false);
                this.afficherMessage('Surveillance arrêtée', 'info');
                this.sauvegarderEtatConnexion();
                this.arreterSurveillanceDonnees();
                console.log('Navigation libre activée');
            } else {
                this.afficherMessage(resultat.message, 'error');
            }
        } catch (erreur) {
            console.error('Erreur arrêt surveillance:', erreur);
            this.afficherMessage('Erreur d\'arrêt', 'error');
        }
    }

    // Démarrer la surveillance des données
    demarrerSurveillanceDonnees() {
        this.arreterSurveillanceDonnees();
        
        this.boucle_donnees_active = true;
        this._bouclerSurveillanceDonnees();
        
        this.intervalle_statistiques = setInterval(() => {
            this.recupererStatistiquesDonnees();
        }, 30000);
        
        this.recupererStatistiquesDonnees();
        
        setTimeout(() => {
            this.testerEnregistrement();
        }, 5000);
    }

    async _bouclerSurveillanceDonnees() {
        if (!this.boucle_donnees_active) return;
        
        await this.recupererDonnees();
        
        if (!this.boucle_donnees_active) return;
        
        // Intervalle adapté à la latence observée (base 1s)
        const delai = this.estimateurReseau.intervalleRecommande(1000, 200);
        this.intervalle_surveillance = setTimeout(() => this._bouclerSurveillanceDonnees(), delai);
    }

    // Arrêter la surveillance des données
    arreterSurveillanceDonnees() {
        this.boucle_donnees_active = false;
        if (this.intervalle_surveillance) {
            clearTimeout(this.intervalle_surveillance);
            this.intervalle_surveillance = null;
        }
        
        if (this.intervalle_statistiques) {
            clearInterval(this.intervalle_statistiques);
            this.intervalle_statistiques = null;
        }
        
        const compteur = document.getElementById('data-counter');
        if (compteur) {
            compteur.remove();
        }
    }

    // Récupérer les données
    async recupererDonnees() {
        if (!this.id_connexion || !this.surveillance_active) {
            return;
        }

        const debut = performance.now();
        try {
            const controller = new AbortController();
            const delaiMax = this.estimateurReseau.timeoutRecommande(5000, 25000);
            const timeoutId = setTimeout(() => controller.abort(), delaiMax);
            
            const reponse = await fetch(`/api/data?connection_id=${this.id_connexion}`, {
                signal: controller.signal
            });
            clearTimeout(timeoutId);
            
            const donnees = await reponse.json();
            
            // Requête réussie (même si données par défaut) : la latence
            // réseau elle-même était correcte
            this.estimateurReseau.enregistrerSucces(performance.now() - debut);
            
            if (donnees.temperature === 0 && donnees.consigne === 25) {
                console.warn('Données par défaut reçues - possible déconnexion');
                this.verifierEtatConnexion('donnees_par_defaut_recues');
                return;
            }
            
            this.mettreAJourAffichage(donnees);
        } catch (erreur) {
            console.error('Erreur récupération données:', erreur);
            
            if (erreur.name === 'AbortError' || !navigator.onLine) {
                this.verifierEtatConnexion('recuperation_donnees_' + (erreur.name === 'AbortError' ? 'timeout' : 'hors_ligne'));
            }
        }
    }

    // Vérifier l'état de la connexion
    async verifierEtatConnexion(raisonAppel = 'non spécifiée') {
        if (!this.id_connexion) return;
        
        const debut = performance.now();
        try {
            const controller = new AbortController();
            const delaiMax = this.estimateurReseau.timeoutRecommande(5000, 25000);
            const timeoutId = setTimeout(() => controller.abort(), delaiMax);
            
            const reponse = await fetch(`/api/check_connection?connection_id=${this.id_connexion}`, {
                signal: controller.signal
            });
            clearTimeout(timeoutId);
            
            const resultat = await reponse.json();
            this.estimateurReseau.enregistrerSucces(performance.now() - debut);
            
            if (!resultat.active) {
                this.echecs_consecutifs_connexion = (this.echecs_consecutifs_connexion || 0) + 1;
                console.warn(`Connexion inactive (${this.echecs_consecutifs_connexion}/3) - raison: ${raisonAppel}`);
                if (this.echecs_consecutifs_connexion >= 3) {
                    this.gererConnexionPerdue('check_connection_inactive (déclenché par: ' + raisonAppel + ')');
                }
            } else {
                this.echecs_consecutifs_connexion = 0;
            }
        } catch (erreur) {
            this.echecs_consecutifs_connexion = (this.echecs_consecutifs_connexion || 0) + 1;
            console.warn(`Erreur vérification connexion (${this.echecs_consecutifs_connexion}/3) - délai actuel: ${Math.round(this.estimateurReseau.timeoutRecommande(5000, 25000))}ms:`, erreur);
            // Sur internet lent, un timeout isolé est normal - on ne coupe
            // qu'après plusieurs échecs d'affilée.
            if (this.echecs_consecutifs_connexion >= 3) {
                this.gererConnexionPerdue('check_connection_exception:' + erreur.message + ' (déclenché par: ' + raisonAppel + ')');
            }
        }
    }

    // Mettre à jour l'affichage
    mettreAJourAffichage(donnees) {
        if (!this.surveillance_active) {
            return;
        }

        const maintenant = new Date().toLocaleTimeString();

        if (donnees.temperature === 0 && donnees.consigne === 25) {
            console.warn('Données par défaut reçues - ignorées');
            return;
        }

        // Ajouter les nouvelles données
        this.donnees.etiquettes.push(maintenant);
        this.donnees.temperatures.push(donnees.temperature);
        this.donnees.consignes.push(donnees.consigne);
        
        // Calculer l'erreur
        const erreur = donnees.consigne - donnees.temperature;
        this.donnees.erreurs.push(erreur);

        // Si des données de contrôleur sont disponibles, les ajouter
        if (donnees.controller_data) {
            this.donnees.sorties.push(donnees.controller_data.output);
        } else {
            // Sinon, ajouter une valeur par défaut
            this.donnees.sorties.push(0);
        }

        // Limiter le nombre de points
        if (this.donnees.etiquettes.length > this.nombre_max_points) {
            this.donnees.etiquettes.shift();
            this.donnees.temperatures.shift();
            this.donnees.consignes.shift();
            this.donnees.erreurs.shift();
            this.donnees.sorties.shift();
        }

        if (this.surveillance_active) {
            this.index_debut_graphique = Math.max(0, this.donnees.etiquettes.length - this.points_visibles_graphique);
        }
        
        this.mettreAJourVueGraphique();

        document.getElementById('current-temp').textContent = `${donnees.temperature.toFixed(1)}°C`;
        document.getElementById('data-temp-actuelle').textContent = `${donnees.temperature.toFixed(1)}°C`;
        document.getElementById('data-temp-cible').textContent = `${donnees.consigne.toFixed(1)}°C`;
        
        document.getElementById('data-erreur').textContent = `${erreur.toFixed(1)}°C`;

        this.mettreAJourThermometre(donnees.temperature);
        
        // Afficher les données du contrôleur si disponibles
        if (donnees.controller_data) {
            this.afficherDonneesControleur(donnees.controller_data);
        }
    }

    // Afficher les données du contrôleur
    afficherDonneesControleur(controller_data) {
        const typeControleur = controller_data.type;
        
        if (typeControleur === 'pi') {
            document.getElementById('data-mode').textContent = `PI (Sortie: ${controller_data.output.toFixed(1)}%)`;
        } else if (typeControleur === 'pid') {
            document.getElementById('data-mode').textContent = `PID (Sortie: ${controller_data.output.toFixed(1)}%)`;
        } else if (typeControleur === 'custom') {
            document.getElementById('data-mode').textContent = `Personnalisé (Sortie: ${controller_data.output.toFixed(1)}%)`;
        }
    }

    // Mettre à jour le thermomètre
    mettreAJourThermometre(temperature) {
        const thermometre = document.getElementById('thermometer-bar');
        const hauteur = Math.min(Math.max((temperature / 100) * 100, 0), 100);
        thermometre.style.height = `${hauteur}%`;
    }

    // Mettre à jour le statut de connexion
    mettreAJourStatutConnexion(connecte, message) {
        const cercle_statut = document.getElementById('connection-status');
        const texte_statut = document.getElementById('connection-text');
        
        if (connecte) {
            cercle_statut.className = 'status-circle connected';
            texte_statut.textContent = message;
            texte_statut.style.color = '#38a169';
        } else {
            cercle_statut.className = 'status-circle disconnected';
            texte_statut.textContent = message;
            texte_statut.style.color = '#e53e3e';
        }
    }

    // Basculer les boutons de connexion
    basculerBoutonsConnexion(connecte) {
        document.getElementById('start-btn').disabled = connecte;
        document.getElementById('stop-monitoring-btn').disabled = !connecte;
        document.getElementById('disconnect-btn').disabled = !connecte;
    }

    // Basculer les boutons de surveillance
    basculerBoutonsSurveillance(surveillance) {
        const boutonStop = document.getElementById('stop-monitoring-btn');
        const boutonPlay = document.getElementById('chart-play');
        
        if (boutonStop) {
            boutonStop.disabled = !surveillance;
        }
        
        if (boutonPlay) {
            boutonPlay.disabled = surveillance;
            boutonPlay.title = surveillance ? 'Surveillance en cours' : 'Reprendre le monitoring';
        }
    }

    // Mettre à jour la consigne
    async mettreAJourConsigne() {
        const curseur_temperature = document.getElementById('temp-slider');
        const nouvelle_consigne = parseFloat(curseur_temperature.value);
        
        if (!this.est_connecte || !this.id_connexion) {
            this.afficherMessage('Veuillez d\'abord vous connecter', 'warning');
            return;
        }

        if (isNaN(nouvelle_consigne) || nouvelle_consigne < 0 || nouvelle_consigne > 100) {
            this.afficherMessage('Consigne invalide (0-100°C)', 'error');
            return;
        }

        try {
            const reponse = await fetch('/api/update_consigne', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    connection_id: this.id_connexion,
                    consigne: nouvelle_consigne,
                    controller_type: this.type_controleur
                })
            });

            const resultat = await reponse.json();

            if (resultat.success) {
                this.consigne_actuelle = nouvelle_consigne;
                localStorage.setItem('consigneActuelleArduino', this.consigne_actuelle.toString());
                this.afficherMessage(resultat.message, 'success');
                document.getElementById('data-temp-cible').textContent = `${nouvelle_consigne.toFixed(1)}°C`;
            } else {
                this.afficherMessage(resultat.message, 'error');
            }
        } catch (erreur) {
            console.error('Erreur mise à jour consigne:', erreur);
            this.afficherMessage('Erreur de mise à jour', 'error');
        }
    }

    // Connecter l'Arduino
    async connecterArduino() {
        const port = document.getElementById('port-select').value;

        if (!port) {
            this.afficherMessage('Veuillez sélectionner un port', 'warning');
            return;
        }

        this.arreterRafraichissementAutoPorts();
        this.utilisateur_interagit_ports = true;

        this.afficherMessage(`Connexion à ${port}...`, 'info');
        this.mettreAJourStatutConnexion(false, 'Connexion en cours...');

        try {
            const reponse = await fetch('/api/connect', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    port: port
                })
            });

            const resultat = await reponse.json();

            if (resultat.success) {
                this.id_connexion = resultat.connection_id;
                this.est_connecte = true;
                this.surveillance_active = true;
                this.echecs_consecutifs_serveur = 0;
                this.echecs_consecutifs_connexion = 0;
                
                this.sauvegarderEtatConnexion();
                this.mettreAJourStatutConnexion(true, resultat.message);
                this.demarrerSurveillanceDonnees();
                this.basculerBoutonsConnexion(true);
                this.afficherMessage(resultat.message, 'success');
                
                // Envoyer le mode contrôleur après connexion
                await this.envoyerModeControleur();
                
                await this.chargerDonneesHistoriques();
                
                setTimeout(() => {
                    this.chargerPorts();
                    this.demarrerRafraichissementAutoPorts();
                }, 1000);
                
                this.demarrerVerificationServeur();
                
                // Vérifier l'état du code personnalisé
                if (this.type_controleur === 'custom') {
                    await this.verifierCodePersonnaliseActif();
                }
            } else {
                this.mettreAJourStatutConnexion(false, 'Échec connexion');
                this.afficherMessage(resultat.message, 'error');
                
                setTimeout(() => {
                    this.utilisateur_interagit_ports = false;
                    this.chargerPorts();
                    this.demarrerRafraichissementAutoPorts();
                }, 3000);
            }
        } catch (erreur) {
            console.error('Erreur connexion:', erreur);
            this.mettreAJourStatutConnexion(false, 'Erreur réseau');
            this.afficherMessage('Erreur de connexion', 'error');
            
            setTimeout(() => {
                this.utilisateur_interagit_ports = false;
                this.chargerPorts();
                this.demarrerRafraichissementAutoPorts();
            }, 3000);
        }
    }

    // Afficher des messages
    afficherMessage(message, type = 'info') {
        const notification = document.createElement('div');
        notification.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            padding: 15px 20px;
            border-radius: 5px;
            color: white;
            font-weight: 500;
            z-index: 1000;
            max-width: 300px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
            font-family: 'Poppins', sans-serif;
        `;
        
        const couleurs = {
            success: '#38a169',
            error: '#e53e3e',
            warning: '#d69e2e',
            info: '#3182ce'
        };
        
        notification.style.backgroundColor = couleurs[type] || couleurs.info;
        notification.textContent = message;
        
        document.body.appendChild(notification);
        
        setTimeout(() => {
            if (notification.parentNode) {
                document.body.removeChild(notification);
            }
        }, 4000);
    }

    // ============================================================
    // GESTION DU CODE PERSONNALISÉ (AMÉLIORÉE)
    // ============================================================

    // Synchroniser l'état du code personnalisé
    async synchroniserEtatCodePersonnalise(typeControleur, estActif = false, codeHash = null) {
        if (estActif) {
            // Activer le mode personnalisé dans l'interface
            this.type_controleur = 'custom';
            this.code_personnalise_actif = true;
            this.code_personnalise_type = typeControleur; // 'pi', 'pid', ou 'mpc'
            this.code_personnalise_hash = codeHash;
            
            localStorage.setItem('typeControleurArduino', 'custom');
            localStorage.setItem('codePersonnaliseActif', 'true');
            localStorage.setItem('codePersonnaliseType', typeControleur);
            if (codeHash) {
                localStorage.setItem('codePersonnaliseHash', codeHash);
            }
            
            // Mettre à jour la liste déroulante
            const selecteur_controleur = document.getElementById('controller-select');
            if (selecteur_controleur) {
                selecteur_controleur.value = 'custom';
            }
            
            // Mettre à jour l'affichage
            this.mettreAJourAffichageControleur();
            
            // Envoyer le mode au serveur
            if (this.est_connecte && this.id_connexion) {
                await this.envoyerModeControleur();
            }
            
            console.log(`Mode personnalisé activé (${typeControleur}) dans l'interface`);
            
            // Mettre à jour l'affichage
            this.afficherMessage(`Code ${typeControleur.toUpperCase()} personnalisé activé`, 'success');
        }
    }

    // Vérifier si un code personnalisé est actif
    async verifierCodePersonnaliseActif() {
        if (!this.id_connexion) {
            // Essayer depuis le localStorage si pas connecté
            const estActifLocal = localStorage.getItem('codePersonnaliseActif') === 'true';
            const typeLocal = localStorage.getItem('codePersonnaliseType');
            
            if (estActifLocal && typeLocal) {
                this.code_personnalise_actif = true;
                this.code_personnalise_type = typeLocal;
                return true;
            }
            return false;
        }
        
        try {
            // Vérifier pour tous les types de contrôleurs
            const types = ['pi', 'pid', 'mpc'];
            
            for (const typeControleur of types) {
                try {
                    const reponse = await fetch(`/api/custom_code/status?connection_id=${this.id_connexion}&code_type=${typeControleur}`);
                    const resultat = await reponse.json();
                    
                    if (resultat.success && resultat.is_active) {
                        // Mettre à jour l'état local
                        this.code_personnalise_actif = true;
                        this.code_personnalise_type = typeControleur;
                        this.code_personnalise_hash = resultat.code_hash;
                        
                        // Mettre à jour le localStorage
                        localStorage.setItem('codePersonnaliseActif', 'true');
                        localStorage.setItem('codePersonnaliseType', typeControleur);
                        if (resultat.code_hash) {
                            localStorage.setItem('codePersonnaliseHash', resultat.code_hash);
                        }
                        
                        return true;
                    }
                } catch (erreur) {
                    console.error(`Erreur vérification ${typeControleur}:`, erreur);
                }
            }
        } catch (erreur) {
            console.error('Erreur vérification code actif:', erreur);
        }
        
        this.code_personnalise_actif = false;
        this.code_personnalise_type = null;
        this.code_personnalise_hash = null;
        return false;
    }

    // Récupérer le code personnalisé depuis le serveur
    async recupererCodePersonnaliseDepuisServeur(typeControleur = null) {
        if (!this.id_connexion) {
            console.log("Pas d'ID de connexion pour récupérer le code");
            return null;
        }
        
        const type = typeControleur || this.code_personnalise_type || 'pi';
        
        try {
            const reponse = await fetch(`/api/custom_code/get?connection_id=${this.id_connexion}&code_type=${type}`);
            const resultat = await reponse.json();
            
            if (resultat.success && resultat.code) {
                console.log(`Code ${type} récupéré depuis le serveur`);
                
                // Mettre à jour l'état local
                this.code_personnalise_type = type;
                this.code_personnalise_hash = resultat.code_hash;
                
                // Sauvegarder dans le localStorage comme backup
                localStorage.setItem(`codePersonnalise_${type}`, resultat.code);
                localStorage.setItem(`codePersonnaliseHash_${type}`, resultat.code_hash);
                
                return {
                    code: resultat.code,
                    hash: resultat.code_hash,
                    is_active: resultat.is_active,
                    type: type
                };
            }
        } catch (erreur) {
            console.error('Erreur récupération code:', erreur);
        }
        
        return null;
    }

    // Récupérer le code depuis le localStorage comme fallback
    recupererCodePersonnaliseDepuisLocalStorage(typeControleur = null) {
        const type = typeControleur || this.code_personnalise_type || 'pi';
        
        try {
            const codeLocal = localStorage.getItem(`codePersonnalise_${type}`);
            const hashLocal = localStorage.getItem(`codePersonnaliseHash_${type}`);
            
            if (codeLocal) {
                console.log(`Code ${type} récupéré depuis localStorage`);
                return {
                    code: codeLocal,
                    hash: hashLocal,
                    type: type
                };
            }
        } catch (erreur) {
            console.error('Erreur récupération localStorage:', erreur);
        }
        
        return null;
    }

    // Activer le code personnalisé
    async activerCodePersonnalise() {
        const typeControleur = this.recupererTypeControleurActif();
        
        if (!this.id_connexion) {
            this.afficherMessage('Veuillez d\'abord vous connecter', 'warning');
            return;
        }
        
        try {
            const reponse = await fetch('/api/custom_code/activate', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    connection_id: this.id_connexion,
                    code_type: typeControleur
                })
            });
            
            const resultat = await reponse.json();
            
            if (resultat.success) {
                this.afficherMessage(`Code ${typeControleur.toUpperCase()} activé`, 'success');
                
                // SYNCHRONISER L'ÉTAT DANS L'INTERFACE PRINCIPALE
                await this.synchroniserEtatCodePersonnalise(typeControleur, true, resultat.code_hash);
                
                // Mettre à jour l'interface de l'éditeur si elle existe
                if (typeof window.mettreAJourEtatCode === 'function') {
                    window.mettreAJourEtatCode(typeControleur, true, resultat.code_hash || 'N/A', true);
                }
                
                // Sauvegarder dans le localStorage
                localStorage.setItem('codePersonnaliseActif', 'true');
                localStorage.setItem('codePersonnaliseType', typeControleur);
                if (resultat.code_hash) {
                    localStorage.setItem('codePersonnaliseHash', resultat.code_hash);
                }
            } else {
                this.afficherMessage(resultat.message, 'error');
            }
        } catch (erreur) {
            console.error('Erreur activation code:', erreur);
            this.afficherMessage('Erreur d\'activation', 'error');
        }
    }

    // Sauvegarder le code personnalisé
    async sauvegarderCodePersonnalise() {
        const code = this.recupererCodePersonnalise();
        if (!code) return;
        
        const typeControleur = this.recupererTypeControleurActif();
        
        if (!this.id_connexion) {
            this.afficherMessage('Veuillez d\'abord vous connecter à un Arduino', 'warning');
            return;
        }
    
        try {
            const reponse = await fetch('/api/custom_code/save', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    connection_id: this.id_connexion,
                    code_type: typeControleur,
                    code: code,
                    name: `Code ${typeControleur.toUpperCase()} personnalisé`,
                    description: 'Code écrit dans l\'éditeur personnalisé'
                })
            });
        
            const resultat = await reponse.json();
        
            if (resultat.success) {
                this.afficherMessage('Code sauvegardé avec succès', 'success');
                console.log(`Code ${typeControleur} sauvegardé, hash: ${resultat.code_hash}`);
            
                // Mettre à jour l'état local
                this.code_personnalise_type = typeControleur;
                this.code_personnalise_hash = resultat.code_hash;
                
                // Sauvegarder dans le localStorage comme backup
                localStorage.setItem(`codePersonnalise_${typeControleur}`, code);
                localStorage.setItem(`codePersonnaliseHash_${typeControleur}`, resultat.code_hash);
            
                // Mettre à jour l'interface
                if (typeof window.mettreAJourEtatCode === 'function') {
                    window.mettreAJourEtatCode(typeControleur, true, resultat.code_hash, false);
                }
            } else {
                this.afficherMessage(resultat.message, 'error');
            }
        } catch (erreur) {
            console.error('Erreur sauvegarde code:', erreur);
            this.afficherMessage('Erreur de sauvegarde', 'error');
        }
    }

    // Récupérer le code depuis l'éditeur
    recupererCodePersonnalise() {
        if (typeof window.recupererCodeEditeur !== 'function') {
            console.error("La fonction recupererCodeEditeur n'est pas disponible");
            return '';
        }
        
        const code = window.recupererCodeEditeur();
        if (!code || code.trim() === '') {
            if (typeof window.afficherMessageCode === 'function') {
                window.afficherMessageCode('Le code ne peut pas être vide', 'error');
            } else {
                this.afficherMessage('Le code ne peut pas être vide', 'error');
            }
            return '';
        }
        
        return code;
    }

    // Récupérer le type de contrôleur actif
    recupererTypeControleurActif() {
        if (typeof document !== 'undefined') {
            const boutonActif = document.querySelector('.btn-exemple.actif');
            if (boutonActif) {
                return boutonActif.textContent.trim().toLowerCase();
            }
        }
        return 'pi'; // Valeur par défaut
    }

    // Mettre à jour l'état du code personnalisé
    mettreAJourEtatCodePersonnalise(typeControleur, aCodePersonnalise = false, codeHash = null, estActif = false) {
        if (typeof document === 'undefined') return;
        
        const badge = document.querySelector('.entete-carte span[class*="badge-"]');
        const etatBox = document.querySelector('.boite-info-etat');
    
        if (!badge || !etatBox) return;
        
        if (aCodePersonnalise && codeHash) {
            if (estActif) {
                badge.textContent = 'Actif';
                badge.className = 'badge-actif';
                etatBox.innerHTML = `
                    <p><strong>✅ Code ${typeControleur.toUpperCase()} personnalisé actif</strong></p>
                    <p class="texte-gris">Utilise votre algorithme personnalisé.</p>
                    <p class="texte-gris">Hash: ${codeHash.slice(0, 6)}...</p>
                `;
            } else {
                badge.textContent = 'Personnalisé';
                badge.className = 'badge-personnalise';
                etatBox.innerHTML = `
                    <p><strong>⚡ Code ${typeControleur.toUpperCase()} personnalisé</strong></p>
                    <p class="texte-gris">Hash: ${codeHash.slice(0, 6)}...</p>
                    <p class="texte-gris">Prêt à être activé.</p>
                `;
            }
        } else {
            badge.textContent = 'Inactif';
            badge.className = 'badge-inactif';
            etatBox.innerHTML = `
                <p><strong>ⓘ Aucun code actif</strong></p>
                <p class="texte-gris">Utilise le contrôleur par défaut.</p>
            `;
        }
    }

    // Vérifier l'état du code personnalisé
    async verifierEtatCodePersonnalise() {
        if (!this.id_connexion) return;
        
        try {
            const typeControleur = this.recupererTypeControleurActif();
            const reponse = await fetch(`/api/custom_code/status?connection_id=${this.id_connexion}&code_type=${typeControleur}`);
            const resultat = await reponse.json();
            
            if (resultat.success) {
                this.mettreAJourEtatCodePersonnalise(
                    typeControleur,
                    resultat.is_custom,
                    resultat.code_hash,
                    resultat.is_active
                );
                
                // Si actif, synchroniser avec l'interface principale
                if (resultat.is_active) {
                    this.synchroniserEtatCodePersonnalise(typeControleur, true, resultat.code_hash);
                }
            }
        } catch (erreur) {
            console.error('Erreur vérification état code:', erreur);
        }
    }

    // Initialiser la gestion du code personnalisé
    initialiserCodePersonnalise() {
        // Charger les exemples
        this.chargerExemplesCode();
        
        // Vérifier l'état du code si connecté
        if (this.id_connexion) {
            setTimeout(() => {
                this.verifierEtatCodePersonnalise();
            }, 1000);
        }
        
        // Vérifier l'état depuis le localStorage
        const estActifLocal = localStorage.getItem('codePersonnaliseActif') === 'true';
        const typeLocal = localStorage.getItem('codePersonnaliseType');
        
        if (estActifLocal && typeLocal) {
            this.code_personnalise_actif = true;
            this.code_personnalise_type = typeLocal;
            
            // Si nous sommes en mode custom, vérifier que nous avons les bonnes données
            if (this.type_controleur === 'custom' && !this.id_connexion) {
                console.log('Mode personnalisé restauré depuis localStorage');
            }
        }
    }

    // Charger les exemples de code
    async chargerExemplesCode() {
        try {
            const reponse = await fetch('/api/custom_code/default_examples');
            const resultat = await reponse.json();
        
            if (resultat.success) {
                // Mettre à jour les exemples dans l'interface
                this.exemplesCode = resultat.examples;
                console.log('Exemples chargés:', Object.keys(this.exemplesCode));
                
                return true;
            }
        } catch (erreur) {
            console.error('Erreur chargement exemples:', erreur);
        }
        return false;
    }
}

// Initialiser l'application
document.addEventListener('DOMContentLoaded', function() {
    new SurveillanceTemperature();
});