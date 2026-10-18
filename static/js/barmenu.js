// barmenu.js - Système complet de notifications avec API réelle

let notifications = [];
let isLoadingNotifications = false;
let notificationSoundEnabled = true;

// Mettre à jour le compteur de notifications
function updateNotificationCount() {
    const unreadCount = notifications.filter(n => !n.lue).length;
    const notificationCount = document.getElementById('notificationCount');
    
    if (unreadCount > 0) {
        notificationCount.textContent = unreadCount > 99 ? '99+' : unreadCount;
        notificationCount.style.display = 'flex';
    } else {
        notificationCount.textContent = '';
        notificationCount.style.display = 'none';
    }
    
    const bell = document.querySelector('.notification-bell');
    if (unreadCount > 0) {
        bell.classList.add('has-notifications');
    } else {
        bell.classList.remove('has-notifications');
    }
}

// Charger les notifications depuis l'API
async function loadNotificationsFromAPI() {
    if (isLoadingNotifications) return;
    
    isLoadingNotifications = true;
    
    try {
        const response = await fetch('/api/notifications');
        const data = await response.json();
        
        if (data.success) {
            const oldUnreadCount = notifications.filter(n => !n.lue).length;
            notifications = data.notifications;
            updateNotificationCount();
            
            // Vérifier s'il y a de NOUVELLES notifications non lues
            const newUnreadCount = notifications.filter(n => !n.lue).length;
            if (newUnreadCount > oldUnreadCount && notificationSoundEnabled) {
                // Jouer un son de notification
                playNotificationSound();
                
                // Afficher une notification toast pour les nouvelles
                const newNotifications = notifications.filter(n => !n.lue).slice(0, 3);
                if (newNotifications.length > 0) {
                    showNewNotificationsToast(newNotifications);
                }
            }
            
            return data;
        }
    } catch (error) {
        console.error('Erreur chargement notifications:', error);
        // En cas d'erreur, afficher des notifications locales
        showLocalNotifications();
    } finally {
        isLoadingNotifications = false;
    }
}

// Basculer l'affichage des notifications
async function toggleNotifications(event) {
    event.stopPropagation();
    const dropdown = document.getElementById('notificationDropdown');
    const isShowing = dropdown.classList.contains('show');
    
    // Fermer tous les dropdowns d'abord
    document.querySelectorAll('.notification-dropdown.show').forEach(d => {
        d.classList.remove('show');
    });
    
    // Ouvrir/fermer ce dropdown
    if (!isShowing) {
        await loadNotificationsFromAPI();
        loadNotifications();
        dropdown.classList.add('show');
        positionDropdown();
        
        // Désactiver le son temporairement pour éviter de jouer quand on ouvre
        notificationSoundEnabled = false;
        setTimeout(() => {
            notificationSoundEnabled = true;
        }, 2000);
    }
}

// Positionner le dropdown de notifications
function positionDropdown() {
    const dropdown = document.getElementById('notificationDropdown');
    const bell = document.querySelector('.notification-bell');
    
    if (bell && dropdown) {
        const bellRect = bell.getBoundingClientRect();
        dropdown.style.position = 'fixed';
        
        // Positionner à droite de la cloche
        dropdown.style.left = (bellRect.left + window.scrollX) + 'px';
        dropdown.style.top = (bellRect.bottom + window.scrollY) + 'px';
        
        // S'assurer qu'il ne dépasse pas de l'écran
        const dropdownWidth = dropdown.offsetWidth;
        const windowWidth = window.innerWidth;
        
        if (bellRect.left + dropdownWidth > windowWidth - 20) {
            dropdown.style.left = (windowWidth - dropdownWidth - 20) + 'px';
        }
    }
}

// Charger les notifications dans la liste
function loadNotifications() {
    const notificationList = document.getElementById('notificationList');
    notificationList.innerHTML = '';
    
    if (notifications.length === 0) {
        notificationList.innerHTML = `
            <div class="notification-empty">
                <i class="fas fa-bell-slash" style="font-size: 2rem; margin-bottom: 10px; opacity: 0.5;"></i>
                <p>Aucune notification</p>
                <p class="small-text" style="font-size: 0.8rem; margin-top: 5px;">
                    Vous recevrez des alertes pour les nouveaux TP
                </p>
            </div>`;
        return;
    }
    
    notifications.forEach(notification => {
        const notificationItem = document.createElement('div');
        notificationItem.className = `notification-item ${notification.lue ? 'read' : 'unread'}`;
        notificationItem.setAttribute('data-id', notification.id);
        notificationItem.onclick = () => showNotificationDetail(notification.id);
        
        // Formater le temps écoulé
        const timeAgo = formatTimeAgo(notification.date_creation);
        
        notificationItem.innerHTML = `
            <div class="notification-item-icon">
                ${getNotificationIcon(notification.type)}
            </div>
            <div class="notification-item-content">
                <div class="notification-item-title">${escapeHtml(notification.titre)}</div>
                <div class="notification-item-preview">${escapeHtml(notification.message.substring(0, 60))}...</div>
                <div class="notification-item-date">${timeAgo}</div>
            </div>
            ${!notification.lue ? '<div class="notification-unread-dot"></div>' : ''}
        `;
        
        notificationList.appendChild(notificationItem);
    });
}

// Obtenir l'icône correspondant au type de notification
function getNotificationIcon(type) {
    const icons = {
        'nouveau_tp': '<i class="fas fa-flask" style="color: #4CAF50;"></i>',
        'tp_modifie': '<i class="fas fa-edit" style="color: #2196F3;"></i>',
        'tp_complet': '<i class="fas fa-check-circle" style="color: #4CAF50;"></i>',
        'rappel_tp': '<i class="fas fa-clock" style="color: #FF9800;"></i>',
        'systeme': '<i class="fas fa-cogs" style="color: #9C27B0;"></i>',
        'default': '<i class="fas fa-info-circle" style="color: #607D8B;"></i>'
    };
    return icons[type] || icons['default'];
}

// Formater le temps écoulé
function formatTimeAgo(dateString) {
    const date = new Date(dateString);
    const now = new Date();
    const diffMs = now - date;
    const diffSec = Math.floor(diffMs / 1000);
    const diffMin = Math.floor(diffSec / 60);
    const diffHour = Math.floor(diffMin / 60);
    const diffDay = Math.floor(diffHour / 24);
    
    if (diffSec < 60) {
        return 'À l\'instant';
    } else if (diffMin < 60) {
        return `Il y a ${diffMin} min`;
    } else if (diffHour < 24) {
        return `Il y a ${diffHour} h`;
    } else if (diffDay < 7) {
        return `Il y a ${diffDay} j`;
    } else {
        return date.toLocaleDateString('fr-FR', { 
            day: 'numeric', 
            month: 'short' 
        });
    }
}

// Afficher le détail d'une notification
async function showNotificationDetail(notificationId) {
    const notification = notifications.find(n => n.id === notificationId);
    if (!notification) return;
    
    // Marquer comme lue
    if (!notification.lue) {
        try {
            await fetch(`/api/notifications/${notificationId}/read`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                }
            });
            
            notification.lue = true;
            updateNotificationCount();
            loadNotifications(); // Recharger la liste
        } catch (error) {
            console.error('Erreur marquage comme lu:', error);
        }
    }
    
    document.getElementById('notificationDetailTitle').textContent = notification.titre;
    const detailBody = document.getElementById('notificationDetailBody');
    detailBody.textContent = notification.message;
    detailBody.style.whiteSpace = 'pre-line';
    //document.getElementById('notificationDetailBody').textContent = notification.message;
    document.getElementById('notificationDetailDate').textContent = formatTimeAgo(notification.date_creation);
    
    const markBtn = document.getElementById('markAsReadBtn');
    markBtn.style.display = 'none'; // Déjà marqué comme lu
    
    // Vérifier si c'est une notification de TP
    if (notification.type === 'nouveau_tp' || notification.type === 'tp_modifie' || notification.type === 'tp_complet') {
        try {
            const donnees = JSON.parse(notification.donnees || '{}');
            if (donnees.tp_id) {
                // Ajouter un bouton pour accéder au TP
                const detailFooter = document.querySelector('.notification-detail-footer');
                const tpButton = document.createElement('button');
                tpButton.className = 'btn-mark-read';
                tpButton.style.marginLeft = '10px';
                tpButton.innerHTML = '<i class="fas fa-external-link-alt"></i> Voir le TP';
                tpButton.onclick = () => {
                    window.location.href = `/tp/${donnees.tp_id}/details`;
                };
                detailFooter.appendChild(tpButton);
            }
        } catch (e) {
            console.log('Données TP non disponibles');
        }
    }
    
    document.getElementById('notificationDetailPopup').classList.add('show');
    document.getElementById('notificationDropdown').classList.remove('show');
}

// Fermer le popup de détail de notification
function closeNotificationDetail() {
    document.getElementById('notificationDetailPopup').classList.remove('show');
    
    // Nettoyer les boutons ajoutés dynamiquement
    const detailFooter = document.querySelector('.notification-detail-footer');
    const extraButtons = detailFooter.querySelectorAll('button:not(#markAsReadBtn)');
    extraButtons.forEach(btn => btn.remove());
}

// Marquer toutes les notifications comme lues
async function markAllAsRead() {
    try {
        const response = await fetch('/api/notifications/read_all', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        });
        
        const data = await response.json();
        
        if (data.success) {
            // Mettre à jour localement
            notifications.forEach(n => n.lue = true);
            updateNotificationCount();
            loadNotifications();
            
            // Afficher un message
            showToast(data.message, 'success');
            
            // Fermer le dropdown
            document.getElementById('notificationDropdown').classList.remove('show');
        }
    } catch (error) {
        console.error('Erreur marquage toutes comme lues:', error);
        showToast('Erreur lors du marquage', 'error');
    }
}

// Fonction pour jouer un son de notification
function playNotificationSound() {
    try {
        // Créer un contexte audio
        const audioContext = new (window.AudioContext || window.webkitAudioContext)();
        
        // Créer un oscillateur (bip sonore)
        const oscillator = audioContext.createOscillator();
        const gainNode = audioContext.createGain();
        
        oscillator.connect(gainNode);
        gainNode.connect(audioContext.destination);
        
        // Configurer le son
        oscillator.frequency.value = 800;
        oscillator.type = 'sine';
        
        // Configurer l'enveloppe du son
        gainNode.gain.setValueAtTime(0, audioContext.currentTime);
        gainNode.gain.linearRampToValueAtTime(0.1, audioContext.currentTime + 0.1);
        gainNode.gain.exponentialRampToValueAtTime(0.001, audioContext.currentTime + 0.3);
        
        // Jouer le son
        oscillator.start(audioContext.currentTime);
        oscillator.stop(audioContext.currentTime + 0.3);
        
    } catch (e) {
        console.log("Son de notification non disponible:", e);
    }
}

// Afficher un toast pour les nouvelles notifications
function showNewNotificationsToast(newNotifications) {
    const toast = document.createElement('div');
    toast.className = 'notification-toast';
    toast.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        background: #fff;
        border-left: 4px solid #4a55ff;
        box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        border-radius: 8px;
        padding: 15px;
        width: 300px;
        z-index: 9999;
        animation: slideInRight 0.3s ease;
        cursor: pointer;
    `;
    
    if (newNotifications.length === 1) {
        toast.innerHTML = `
            <div style="display: flex; align-items: center; margin-bottom: 8px;">
                <i class="fas fa-bell" style="color: #4a55ff; margin-right: 10px;"></i>
                <strong style="flex: 1;">Nouvelle notification</strong>
                <i class="fas fa-times" onclick="this.parentElement.parentElement.remove()" 
                   style="cursor: pointer; opacity: 0.5;"></i>
            </div>
            <div style="font-size: 0.9rem; color: #333;">${escapeHtml(newNotifications[0].titre)}</div>
            <div style="font-size: 0.8rem; color: #666; margin-top: 5px;">${escapeHtml(newNotifications[0].message.substring(0, 50))}...</div>
        `;
    } else {
        toast.innerHTML = `
            <div style="display: flex; align-items: center; margin-bottom: 8px;">
                <i class="fas fa-bell" style="color: #4a55ff; margin-right: 10px;"></i>
                <strong style="flex: 1;">${newNotifications.length} nouvelles notifications</strong>
                <i class="fas fa-times" onclick="this.parentElement.parentElement.remove()" 
                   style="cursor: pointer; opacity: 0.5;"></i>
            </div>
            <div style="font-size: 0.9rem; color: #333;">Vous avez ${newNotifications.length} nouvelles notifications</div>
        `;
    }
    
    toast.onclick = function() {
        toggleNotifications({ stopPropagation: function() {} });
        this.remove();
    };
    
    document.body.appendChild(toast);
    
    // Supprimer automatiquement après 5 secondes
    setTimeout(() => {
        if (toast.parentNode) {
            toast.style.animation = 'slideOutRight 0.3s ease';
            setTimeout(() => {
                if (toast.parentNode) {
                    toast.remove();
                }
            }, 300);
        }
    }, 5000);
}

// Fonction toast simple
function showToast(message, type = 'info') {
    // Créer un toast si non existant
    let toast = document.getElementById('global-toast');
    if (!toast) {
        toast = document.createElement('div');
        toast.id = 'global-toast';
        toast.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            padding: 12px 24px;
            border-radius: 8px;
            color: white;
            font-weight: 500;
            z-index: 9999;
            display: none;
            transition: opacity 0.3s;
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
            font-family: 'Poppins', sans-serif;
        `;
        document.body.appendChild(toast);
    }
    
    // Définir la couleur selon le type
    const colors = {
        'success': '#4CAF50',
        'error': '#F44336',
        'info': '#2196F3',
        'warning': '#FF9800'
    };
    
    toast.style.backgroundColor = colors[type] || colors['info'];
    toast.textContent = message;
    toast.style.display = 'block';
    toast.style.opacity = '1';
    
    // Cacher après 3 secondes
    setTimeout(() => {
        toast.style.opacity = '0';
        setTimeout(() => {
            toast.style.display = 'none';
            toast.style.opacity = '1';
        }, 300);
    }, 3000);
}

// Fonction de secours pour afficher des notifications locales
function showLocalNotifications() {
    if (notifications.length === 0) {
        // Ajouter une notification d'exemple
        notifications = [{
            id: 1,
            type: 'systeme',
            titre: 'Système de notifications',
            message: 'Le système de notifications est maintenant actif. Vous recevrez des alertes pour les nouveaux TP.',
            lue: true,
            date_creation: new Date().toISOString(),
            date_creation_formatted: 'Maintenant'
        }];
        updateNotificationCount();
    }
}

// Échapper le HTML pour la sécurité
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Vérifier périodiquement les nouvelles notifications
async function checkForNewNotifications() {
    try {
        const response = await fetch('/api/notifications/count');
        const data = await response.json();
        
        if (data.success) {
            const oldUnreadCount = notifications.filter(n => !n.lue).length;
            
            if (data.count > oldUnreadCount) {
                // Recharger les notifications
                await loadNotificationsFromAPI();
                
                // Si le dropdown est ouvert, recharger la liste
                const dropdown = document.getElementById('notificationDropdown');
                if (dropdown.classList.contains('show')) {
                    loadNotifications();
                }
            }
        }
    } catch (error) {
        console.error('Erreur vérification nouvelles notifications:', error);
    }
}

// Initialisation du système de notifications
function initializeNotificationSystem() {
    // Charger les notifications au démarrage
    loadNotificationsFromAPI();
    
    // Fermer le dropdown quand on clique en dehors
    document.addEventListener('click', function(event) {
        const dropdown = document.getElementById('notificationDropdown');
        const bell = document.querySelector('.notification-bell');
        const detailPopup = document.getElementById('notificationDetailPopup');
        const detailContent = document.querySelector('.notification-detail-content');
        
        if (dropdown && dropdown.classList.contains('show') && 
            !dropdown.contains(event.target) && 
            !bell.contains(event.target)) {
            dropdown.classList.remove('show');
        }
        
        if (detailPopup && detailPopup.classList.contains('show') && 
            detailContent && !detailContent.contains(event.target)) {
            closeNotificationDetail();
        }
    });
    
    // Repositionner le dropdown quand la fenêtre est redimensionnée
    window.addEventListener('resize', function() {
        const dropdown = document.getElementById('notificationDropdown');
        if (dropdown && dropdown.classList.contains('show')) {
            positionDropdown();
        }
    });
    
    // Vérifier les nouvelles notifications toutes les 30 secondes
    setInterval(checkForNewNotifications, 30000);
    
    // Vérifier aussi quand la page devient visible
    document.addEventListener('visibilitychange', function() {
        if (!document.hidden) {
            checkForNewNotifications();
        }
    });
    
    // Ajouter des styles CSS dynamiquement
    const styles = `
        @keyframes slideInRight {
            from {
                transform: translateX(100%);
                opacity: 0;
            }
            to {
                transform: translateX(0);
                opacity: 1;
            }
        }
        
        @keyframes slideOutRight {
            from {
                transform: translateX(0);
                opacity: 1;
            }
            to {
                transform: translateX(100%);
                opacity: 0;
            }
        }
        
        .notification-toast {
            transition: all 0.3s ease;
        }
        
        .small-text {
            font-size: 0.8rem;
            color: #888;
        }
    `;
    
    const styleSheet = document.createElement('style');
    styleSheet.textContent = styles;
    document.head.appendChild(styleSheet);
}

// Initialiser le système quand le DOM est chargé
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initializeNotificationSystem);
} else {
    initializeNotificationSystem();
}

// Exporter les fonctions principales pour un accès global
window.toggleNotifications = toggleNotifications;
window.showNotificationDetail = showNotificationDetail;
window.closeNotificationDetail = closeNotificationDetail;
window.markAllAsRead = markAllAsRead;