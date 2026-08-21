/**
 * dialogs.js
 * ------------------------------------------------------------------
 * Boîtes de dialogue stylisées pour remplacer les window.confirm()
 * et window.alert() natifs du navigateur (qui s'affichent dans la
 * barre du navigateur et cassent la charte graphique de l'appli).
 *
 * Utilisation :
 *   const ok = await appConfirm('Supprimer ce TP ?', {
 *       title: 'Confirmer la suppression',
 *       confirmLabel: 'Supprimer',
 *       cancelLabel: 'Annuler',
 *       danger: true
 *   });
 *   if (ok) { ... }
 *
 *   await appAlert('Enregistrement effectué avec succès.', { type: 'success' });
 * ------------------------------------------------------------------
 */
(function () {
    'use strict';

    function ensureStyles() {
        if (document.getElementById('app-dialogs-styles')) return;
        const style = document.createElement('style');
        style.id = 'app-dialogs-styles';
        style.textContent = `
        .app-dialog-overlay {
            position: fixed; inset: 0; background: rgba(15, 23, 42, 0.55);
            display: flex; align-items: center; justify-content: center;
            z-index: 100000; padding: 20px; opacity: 0; transition: opacity .18s ease-out;
            backdrop-filter: blur(2px);
        }
        .app-dialog-overlay.show { opacity: 1; }
        .app-dialog-box {
            background: #ffffff; border-radius: 14px; max-width: 420px; width: 100%;
            box-shadow: 0 20px 60px rgba(0,0,0,0.25); overflow: hidden;
            transform: translateY(10px) scale(.98); transition: transform .18s ease-out;
            font-family: 'Poppins', 'Segoe UI', Arial, sans-serif;
        }
        .app-dialog-overlay.show .app-dialog-box { transform: translateY(0) scale(1); }
        .app-dialog-header {
            display: flex; align-items: center; gap: 12px; padding: 20px 22px 0 22px;
        }
        .app-dialog-icon {
            width: 42px; height: 42px; border-radius: 50%; display: flex;
            align-items: center; justify-content: center; flex-shrink: 0; font-size: 1.2rem;
        }
        .app-dialog-icon.info { background: #e3f2fd; color: #1565c0; }
        .app-dialog-icon.success { background: #e8f5e9; color: #2e7d32; }
        .app-dialog-icon.warning { background: #fff8e1; color: #ef6c00; }
        .app-dialog-icon.danger { background: #fdecea; color: #c62828; }
        .app-dialog-title { font-size: 1.05rem; font-weight: 600; color: #1a237e; margin: 0; }
        .app-dialog-body { padding: 14px 22px 6px 22px; color: #37474f; font-size: 0.92rem; line-height: 1.5; white-space: pre-line; }
        .app-dialog-footer { display: flex; justify-content: flex-end; gap: 10px; padding: 18px 22px 22px 22px; }
        .app-dialog-btn {
            border: none; border-radius: 8px; padding: 10px 18px; font-size: 0.88rem;
            font-weight: 500; cursor: pointer; transition: filter .15s, transform .05s;
        }
        .app-dialog-btn:active { transform: scale(0.97); }
        .app-dialog-btn.secondary { background: #eceff1; color: #37474f; }
        .app-dialog-btn.secondary:hover { filter: brightness(0.95); }
        .app-dialog-btn.primary { background: #1a237e; color: #fff; }
        .app-dialog-btn.primary:hover { filter: brightness(1.1); }
        .app-dialog-btn.primary.danger { background: #c62828; }
        .app-dialog-btn.primary.success { background: #2e7d32; }
        `;
        document.head.appendChild(style);
    }

    function iconFor(type) {
        switch (type) {
            case 'success': return 'fa-circle-check';
            case 'warning': return 'fa-triangle-exclamation';
            case 'danger': return 'fa-circle-exclamation';
            default: return 'fa-circle-info';
        }
    }

    function buildOverlay() {
        const overlay = document.createElement('div');
        overlay.className = 'app-dialog-overlay';
        const box = document.createElement('div');
        box.className = 'app-dialog-box';
        overlay.appendChild(box);
        document.body.appendChild(overlay);
        requestAnimationFrame(() => overlay.classList.add('show'));
        return { overlay, box };
    }

    function closeOverlay(overlay) {
        overlay.classList.remove('show');
        setTimeout(() => overlay.remove(), 180);
    }

    const esc = (s) => (window.escapeHtml ? window.escapeHtml(s) : String(s));

    /**
     * Affiche une boîte de confirmation stylisée.
     * @returns {Promise<boolean>} true si l'utilisateur confirme
     */
    window.appConfirm = function (message, options) {
        options = options || {};
        ensureStyles();
        const type = options.danger ? 'danger' : (options.type || 'warning');
        return new Promise((resolve) => {
            const { overlay, box } = buildOverlay();
            box.innerHTML = `
                <div class="app-dialog-header">
                    <div class="app-dialog-icon ${type}"><i class="fas ${iconFor(type)}"></i></div>
                    <h3 class="app-dialog-title">${esc(options.title || 'Confirmation')}</h3>
                </div>
                <div class="app-dialog-body">${esc(message)}</div>
                <div class="app-dialog-footer">
                    <button type="button" class="app-dialog-btn secondary" data-action="cancel">${esc(options.cancelLabel || 'Annuler')}</button>
                    <button type="button" class="app-dialog-btn primary ${type === 'danger' ? 'danger' : ''}" data-action="confirm">${esc(options.confirmLabel || 'Confirmer')}</button>
                </div>
            `;

            function finish(result) {
                document.removeEventListener('keydown', onKeydown);
                closeOverlay(overlay);
                resolve(result);
            }
            function onKeydown(e) {
                if (e.key === 'Escape') finish(false);
                if (e.key === 'Enter') finish(true);
            }

            box.querySelector('[data-action="cancel"]').addEventListener('click', () => finish(false));
            box.querySelector('[data-action="confirm"]').addEventListener('click', () => finish(true));
            overlay.addEventListener('click', (e) => { if (e.target === overlay) finish(false); });
            document.addEventListener('keydown', onKeydown);
            box.querySelector('[data-action="confirm"]').focus();
        });
    };

    /**
     * Affiche une boîte d'alerte/information stylisée (remplace window.alert).
     * @returns {Promise<void>} résolue à la fermeture de la boîte
     */
    window.appAlert = function (message, options) {
        options = options || {};
        ensureStyles();
        const type = options.type || 'info';
        return new Promise((resolve) => {
            const { overlay, box } = buildOverlay();
            box.innerHTML = `
                <div class="app-dialog-header">
                    <div class="app-dialog-icon ${type}"><i class="fas ${iconFor(type)}"></i></div>
                    <h3 class="app-dialog-title">${esc(options.title || (type === 'success' ? 'Succès' : type === 'danger' ? 'Erreur' : 'Information'))}</h3>
                </div>
                <div class="app-dialog-body">${esc(message)}</div>
                <div class="app-dialog-footer">
                    <button type="button" class="app-dialog-btn primary ${type}" data-action="ok">${esc(options.okLabel || 'OK')}</button>
                </div>
            `;
            function finish() {
                document.removeEventListener('keydown', onKeydown);
                closeOverlay(overlay);
                resolve();
            }
            function onKeydown(e) {
                if (e.key === 'Escape' || e.key === 'Enter') finish();
            }
            box.querySelector('[data-action="ok"]').addEventListener('click', finish);
            overlay.addEventListener('click', (e) => { if (e.target === overlay) finish(); });
            document.addEventListener('keydown', onKeydown);
            box.querySelector('[data-action="ok"]').focus();
        });
    };
})();
