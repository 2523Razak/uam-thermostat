/**
 * security.js
 * ------------------------------------------------------------------
 * 1) Injecte automatiquement l'en-tête X-CSRFToken dans toutes les
 *    requêtes fetch() same-origin qui modifient des données
 *    (POST/PUT/PATCH/DELETE), en lisant le jeton depuis la balise
 *    <meta name="csrf-token"> injectée dans le <head> de chaque page.
 *    Cela évite d'avoir à modifier individuellement chaque appel
 *    fetch() existant dans l'application.
 *
 * 2) Fournit un échappement HTML minimal réutilisable par les autres
 *    scripts pour éviter les failles XSS lors de l'insertion de
 *    contenu utilisateur via innerHTML.
 * ------------------------------------------------------------------
 */
(function () {
    'use strict';

    function getCsrfToken() {
        const meta = document.querySelector('meta[name="csrf-token"]');
        return meta ? meta.getAttribute('content') : null;
    }

    const MUTATING_METHODS = new Set(['POST', 'PUT', 'PATCH', 'DELETE']);

    const originalFetch = window.fetch ? window.fetch.bind(window) : null;

    if (originalFetch) {
        window.fetch = function (input, init) {
            try {
                let url = typeof input === 'string' ? input : (input && input.url) || '';
                const isRelative = url.startsWith('/') && !url.startsWith('//');
                const isSameOrigin = isRelative || url.startsWith(window.location.origin);

                let method = 'GET';
                if (init && init.method) {
                    method = init.method.toUpperCase();
                } else if (input && input.method) {
                    method = input.method.toUpperCase();
                }

                if (isSameOrigin && MUTATING_METHODS.has(method)) {
                    const token = getCsrfToken();
                    if (token) {
                        init = init ? Object.assign({}, init) : {};
                        const headers = new Headers(init.headers || (input && input.headers) || {});
                        if (!headers.has('X-CSRFToken')) {
                            headers.set('X-CSRFToken', token);
                        }
                        init.headers = headers;
                    }
                }
            } catch (e) {
                // En cas d'erreur d'introspection, on n'empêche jamais la requête :
                // on retombe simplement sur le comportement fetch() natif.
                console.warn('security.js: impossible d\'ajouter le jeton CSRF automatiquement', e);
            }
            return originalFetch(input, init);
        };
    }

    // Petit utilitaire d'échappement HTML partagé (protection XSS) -----
    window.escapeHtml = window.escapeHtml || function (value) {
        if (value === null || value === undefined) return '';
        return String(value).replace(/[&<>"']/g, function (m) {
            return {
                '&': '&amp;',
                '<': '&lt;',
                '>': '&gt;',
                '"': '&quot;',
                "'": '&#39;'
            }[m];
        });
    };
})();
